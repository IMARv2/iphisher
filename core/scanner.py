import subprocess
import re
import time
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class AccessPoint:
    ssid: str
    bssid: str
    channel: int
    signal: int
    encryption: str
    wps: bool = False
    clients: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        wps_tag = " [WPS]" if self.wps else ""
        return f"{self.ssid} ({self.bssid}) CH:{self.channel} {self.encryption}{wps_tag}"


def scan_networks(iface: str, duration: int = 10) -> list[AccessPoint]:
    """Scan for nearby WiFi networks using iw or airodump-ng."""
    networks = _scan_iw(iface) or _scan_airodump(iface, duration)
    _detect_wps(iface, networks)
    return networks


def _scan_iw(iface: str) -> list[AccessPoint]:
    networks: list[AccessPoint] = []
    seen: set[str] = set()
    try:
        result = subprocess.run(
            ["iw", iface, "scan"], capture_output=True, text=True, timeout=20
        )
        if result.returncode != 0:
            return []
        blocks = re.split(r"BSS ([0-9a-f:]{17})", result.stdout)
        i = 1
        while i < len(blocks) - 1:
            bssid = blocks[i].strip()
            block = blocks[i + 1]
            i += 2
            if bssid in seen:
                continue
            seen.add(bssid)
            ssid_match = re.search(r'SSID: (.+)', block)
            ch_match = re.search(r'DS Parameter set: channel (\d+)', block)
            sig_match = re.search(r'signal: ([-\d.]+) dBm', block)
            rsn_match = re.search(r'RSN:', block)
            wpa_match = re.search(r'WPA:', block)
            ssid = ssid_match.group(1).strip() if ssid_match else "<hidden>"
            channel = int(ch_match.group(1)) if ch_match else 0
            signal = int(float(sig_match.group(1))) if sig_match else -100
            if rsn_match:
                enc = "WPA2"
            elif wpa_match:
                enc = "WPA"
            else:
                enc = "OPEN"
            networks.append(AccessPoint(ssid=ssid, bssid=bssid, channel=channel,
                                        signal=signal, encryption=enc))
    except Exception:
        return []
    return networks


def _scan_airodump(iface: str, duration: int) -> list[AccessPoint]:
    """Fallback scan using airodump-ng with CSV output."""
    import tempfile, os
    networks: list[AccessPoint] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        prefix = os.path.join(tmpdir, "scan")
        proc = subprocess.Popen(
            ["airodump-ng", "--output-format", "csv", "-w", prefix, iface],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(duration)
        proc.terminate()
        proc.wait(timeout=5)
        csv_file = prefix + "-01.csv"
        if not os.path.exists(csv_file):
            return networks
        with open(csv_file, errors="ignore") as f:
            content = f.read()
        ap_section = content.split("Station MAC")[0]
        for line in ap_section.splitlines()[2:]:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 14:
                continue
            bssid = parts[0]
            if not re.match(r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", bssid):
                continue
            try:
                channel = int(parts[3])
                signal = int(parts[8])
            except ValueError:
                channel, signal = 0, -100
            enc = parts[5].strip() or "OPEN"
            ssid = parts[13].strip() or "<hidden>"
            networks.append(AccessPoint(ssid=ssid, bssid=bssid, channel=channel,
                                        signal=signal, encryption=enc))
    return networks


def _detect_wps(iface: str, networks: list[AccessPoint]) -> None:
    """Use wash to detect WPS-enabled APs."""
    try:
        bssids = {ap.bssid: ap for ap in networks}
        result = subprocess.run(
            ["wash", "-i", iface, "--scan", "-s"],
            capture_output=True, text=True, timeout=15
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 1 and re.match(r"([0-9A-Fa-f]{2}:){5}", parts[0]):
                mac = parts[0].lower()
                if mac in bssids:
                    bssids[mac].wps = True
    except Exception:
        pass
