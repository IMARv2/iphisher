import subprocess
import re
import os
from typing import Optional


def get_wifi_interfaces() -> list[dict]:
    """Return list of wireless interfaces with capabilities."""
    interfaces = []
    try:
        result = subprocess.run(["iw", "dev"], capture_output=True, text=True, timeout=10)
        blocks = re.split(r"Interface\s+", result.stdout)
        for block in blocks[1:]:
            lines = block.strip().splitlines()
            iface = lines[0].strip()
            info = {"name": iface, "monitor": False, "ap": False, "managed": False}
            phy_result = subprocess.run(
                ["iw", "phy"], capture_output=True, text=True, timeout=10
            )
            info["monitor"] = "monitor" in phy_result.stdout
            info["ap"] = "AP" in phy_result.stdout
            info["managed"] = True
            interfaces.append(info)
    except Exception:
        pass

    # Fallback using iwconfig
    if not interfaces:
        try:
            result = subprocess.run(["iwconfig"], capture_output=True, text=True, timeout=10)
            for match in re.finditer(r"^(\w+)\s+IEEE", result.stdout, re.MULTILINE):
                iface = match.group(1)
                interfaces.append({"name": iface, "monitor": True, "ap": True, "managed": True})
        except Exception:
            pass

    return interfaces


def set_monitor_mode(iface: str) -> Optional[str]:
    """Enable monitor mode. Returns new interface name or None on failure."""
    try:
        subprocess.run(["airmon-ng", "check", "kill"], capture_output=True, timeout=10)
        result = subprocess.run(
            ["airmon-ng", "start", iface], capture_output=True, text=True, timeout=15
        )
        match = re.search(r"monitor mode.*on\s+(\w+)", result.stdout, re.IGNORECASE)
        if match:
            return match.group(1)
        mon_iface = iface + "mon"
        result2 = subprocess.run(["iw", "dev"], capture_output=True, text=True, timeout=5)
        if mon_iface in result2.stdout:
            return mon_iface
        return iface
    except Exception:
        return None


def set_managed_mode(iface: str) -> bool:
    """Restore interface to managed mode."""
    try:
        mon_base = iface.replace("mon", "")
        subprocess.run(["airmon-ng", "stop", iface], capture_output=True, timeout=15)
        subprocess.run(
            ["ip", "link", "set", mon_base, "up"], capture_output=True, timeout=5
        )
        return True
    except Exception:
        return False


def configure_ap_interface(iface: str, ip: str = "10.0.0.1", netmask: str = "255.255.255.0") -> bool:
    """Assign IP address to AP interface."""
    try:
        subprocess.run(["ip", "link", "set", iface, "up"], check=True, capture_output=True, timeout=5)
        subprocess.run(
            ["ip", "addr", "flush", "dev", iface], capture_output=True, timeout=5
        )
        subprocess.run(
            ["ip", "addr", "add", f"{ip}/24", "dev", iface],
            check=True, capture_output=True, timeout=5,
        )
        return True
    except Exception:
        return False


def setup_nat(iface_ap: str, iface_wan: str) -> bool:
    """Enable NAT and IP forwarding for internet sharing (not used in evil twin mode)."""
    try:
        with open("/proc/sys/net/ipv4/ip_forward", "w") as f:
            f.write("1")
        subprocess.run(
            ["iptables", "-t", "nat", "-A", "POSTROUTING", "-o", iface_wan, "-j", "MASQUERADE"],
            capture_output=True, timeout=5,
        )
        return True
    except Exception:
        return False


def setup_captive_redirect(iface_ap: str, portal_port: int = 80) -> bool:
    """Redirect all HTTP traffic on AP interface to captive portal."""
    try:
        subprocess.run(
            ["iptables", "-t", "nat", "-A", "PREROUTING", "-i", iface_ap,
             "-p", "tcp", "--dport", "80", "-j", "REDIRECT", "--to-port", str(portal_port)],
            check=True, capture_output=True, timeout=5,
        )
        subprocess.run(
            ["iptables", "-t", "nat", "-A", "PREROUTING", "-i", iface_ap,
             "-p", "tcp", "--dport", "443", "-j", "REDIRECT", "--to-port", str(portal_port)],
            capture_output=True, timeout=5,
        )
        return True
    except Exception:
        return False


def flush_iptables() -> None:
    """Clean up iptables rules added by iPhisher."""
    subprocess.run(["iptables", "-t", "nat", "-F"], capture_output=True, timeout=5)
    subprocess.run(["iptables", "-F"], capture_output=True, timeout=5)
