# iPhisher

> Advanced WiFi Credential Harvester for Penetration Testers

iPhisher is a Kali Linux tool that captures WPA2-PSK credentials through a multi-adapter attack combining deauthentication, evil twin access points, and OS-native captive portals — without requiring a visible web browser redirect.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    Attack Flow                              │
│                                                             │
│  Adapter 1 (Monitor)  →  Deauth loop against real AP       │
│  Adapter 2 (AP mode)  →  Evil Twin broadcasts same SSID     │
│  Adapter 3 (Managed)  →  Verifies captured password        │
│                                                             │
│  Client disconnects → Joins Evil Twin → OS shows native    │
│  auth prompt → Password captured → Verified on real AP     │
└─────────────────────────────────────────────────────────────┘
```

### Attack Modes

| Mode | Description | Requirements |
|------|-------------|--------------|
| **WPS Pixie Dust** | Attacks WPS-enabled routers directly (seconds) | WPS enabled on target |
| **Evil Twin + Portal** | OS-native captive portal triggered after client connects | 3 WiFi adapters |
| **PMKID + Crack** | Clientless PMKID capture + hashcat | hcxdumptool + hashcat + wordlist |

### OS-Aware Captive Portals

iPhisher detects the victim's operating system via User-Agent and serves a matching portal:

- **iOS** — Mimics Apple's native WiFi sign-in sheet (white card, SF Pro font, blue "Join" button)
- **Android** — Material Design 3 authentication dialog
- **Windows** — Fluent Design "Network Authentication Required" dialog

These portals are automatically triggered by the OS (Captive Network Assistant on iOS/Android, Network Sign-In on Windows) — no browser interaction required from the victim.

---

## Requirements

### Hardware
- **Minimum 2 WiFi adapters** (3 recommended)
  - One must support **monitor mode + packet injection**
  - One must support **AP mode** (hostapd)
  - One for managed mode (password verification)

### Tested Adapters
- Alfa AWUS036ACH (recommended — all modes)
- Alfa AWUS036NHA
- TP-Link TL-WN722N v1

### Software
- Kali Linux (recommended) or any Debian-based distro
- Python 3.10+
- Root privileges

---

## Installation

```bash
git clone https://github.com/IMARv2/iphisher.git
cd iphisher
sudo ./install.sh
```

### Manual dependency install

```bash
sudo apt-get install aircrack-ng hostapd dnsmasq reaver bully \
    hcxdumptool hcxtools hashcat python3-pip
pip3 install -r requirements.txt
```

---

## Usage

```bash
sudo python3 iphisher.py
```

### Interactive flow

1. **Adapter assignment** — assign each adapter a role (deauth / AP / verify)
2. **Network scan** — discovers nearby WiFi networks with WPS detection
3. **Target selection** — pick your target from the table
4. **Attack selection** — WPS Pixie Dust (if available) or Evil Twin
5. **Results** — captured credentials displayed and saved to `/tmp/iphisher_results.txt`

---

## Project Structure

```
iphisher/
├── iphisher.py              # Entry point + TUI
├── core/
│   ├── scanner.py           # WiFi network discovery
│   ├── deauth.py            # Continuous deauthentication attack
│   ├── evil_twin.py         # Fake AP (hostapd + dnsmasq)
│   ├── captive_portal.py    # OS-aware credential portal (Flask)
│   ├── wps_attack.py        # WPS Pixie Dust / PIN attack
│   ├── pmkid.py             # PMKID capture + hashcat cracking
│   └── verifier.py          # Password verification via wpa_supplicant
├── templates/
│   ├── ios/                 # iOS-style portal pages
│   ├── android/             # Android Material Design pages
│   └── windows/             # Windows Fluent Design pages
├── utils/
│   ├── interface.py         # Adapter mode management + iptables
│   └── logger.py            # Logging
├── requirements.txt
└── install.sh
```

---

## Differences from wifiphisher

| Feature | wifiphisher | iPhisher |
|---------|-------------|----------|
| Captive portal | Browser redirect | OS-native prompt (auto-triggered) |
| WPS attack | Limited | Pixie Dust + PIN brute-force |
| OS detection | Template-based | User-Agent → matching native UI |
| Credential verification | No | Yes — Adapter 3 tests against real AP |
| PMKID attack | No | Yes (clientless) |

---

## Legal Disclaimer

> **iPhisher is intended for authorized penetration testing and security research only.**
> Using this tool against networks you do not own or have explicit written permission to test is illegal in most jurisdictions.
> The authors assume no liability for misuse.

---

## License

MIT License — see [LICENSE](LICENSE)
