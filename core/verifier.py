import os
import subprocess
import tempfile
import time
from typing import Optional


WPA_CONF_TEMPLATE = """\
ctrl_interface=/var/run/wpa_supplicant
network={{
    ssid="{ssid}"
    psk="{password}"
    key_mgmt=WPA-PSK
}}
"""


def verify_password(iface: str, ssid: str, bssid: str, password: str,
                    timeout: int = 15) -> bool:
    """
    Test a WPA2-PSK password against the real AP using wpa_supplicant.
    Returns True if the password is correct.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        conf_path = os.path.join(tmpdir, "wpa.conf")
        ctrl_path = os.path.join(tmpdir, "ctrl")
        os.makedirs(ctrl_path, exist_ok=True)

        with open(conf_path, "w") as f:
            f.write(WPA_CONF_TEMPLATE.format(ssid=ssid, password=password))

        proc = subprocess.Popen(
            [
                "wpa_supplicant",
                "-i", iface,
                "-c", conf_path,
                "-D", "nl80211,wext",
                "-C", ctrl_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        result = False
        deadline = time.time() + timeout
        try:
            while time.time() < deadline:
                line = proc.stdout.readline() if proc.stdout else ""
                if not line:
                    break
                if "CTRL-EVENT-CONNECTED" in line or "WPA: Key negotiation completed" in line:
                    result = True
                    break
                if "CTRL-EVENT-ASSOC-REJECT" in line or "CTRL-EVENT-AUTH-REJECT" in line:
                    break
                if "4-Way Handshake failed" in line or "WPA: EAPOL-Key Msg 3/4" in line:
                    # Allow a moment for completion
                    pass
        finally:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                proc.kill()
            # Bring interface back to managed state
            subprocess.run(["ip", "link", "set", iface, "up"],
                           capture_output=True, timeout=5)

    return result


def fast_verify(iface: str, ssid: str, bssid: str, password: str) -> Optional[bool]:
    """
    Quick PMK-based local verification using the captured handshake.
    Returns True/False/None (None = no handshake available yet).
    """
    try:
        from scapy.all import rdpcap, EAPOL
    except ImportError:
        return None

    handshake_file = f"/tmp/iphisher_{bssid.replace(':', '')}.cap"
    if not os.path.exists(handshake_file):
        return None

    result = subprocess.run(
        ["aircrack-ng", "-w", "-", "-b", bssid, handshake_file],
        input=password,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if "KEY FOUND" in result.stdout:
        return True
    if "not in dictionary" in result.stdout:
        return False
    return None
