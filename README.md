<div align="center">

```
  _ ____  _     _     _
 (_)  _ \| |__ (_)___| |__   ___ _ __
 | || |_) | '_ \| / __| '_ \ / _ \ '__|
 | ||  __/| | | | \__ \ | | |  __/ |
 |_||_|   |_| |_|_|___/_| |_|\___|_|
```

# iPhisher

### Advanced WiFi Credential Harvester for Penetration Testers

*Capture WPA2-PSK credentials through OS-native prompts — no fake website required.*

<br>

![Platform](https://img.shields.io/badge/Platform-Kali%20Linux-557C94?style=flat-square&logo=kalilinux&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Adapters](https://img.shields.io/badge/Adapters-2%2B%20required-orange?style=flat-square)
![Status](https://img.shields.io/badge/Status-v1.0.0-blueviolet?style=flat-square)

![Evil Twin](https://img.shields.io/badge/Evil%20Twin-✓-red?style=flat-square)
![WPS Pixie Dust](https://img.shields.io/badge/WPS%20Pixie%20Dust-✓-red?style=flat-square)
![PMKID](https://img.shields.io/badge/PMKID%20Attack-✓-red?style=flat-square)
![Live Verify](https://img.shields.io/badge/Live%20Verification-✓-red?style=flat-square)

</div>

---

## ✨ Overview

**iPhisher** captures WPA2-PSK credentials through a multi-adapter attack combining deauthentication, an evil-twin access point, and **OS-native captive portals** — without relying on a visible web browser redirect.

The key difference from tools like `wifiphisher`: instead of a fake website, iPhisher triggers the **operating system's own network sign-in prompt** and serves a portal that visually matches the victim's OS (iOS / Android / Windows). It then **verifies** the captured password against the real router in real time using a dedicated adapter.

---

## 🔄 How It Works

```
┌──────────────────────────────────────────────────────────────┐
│                        Attack Flow                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   📡 Adapter 1 (Monitor)  ──►  Deauth loop vs. real AP       │
│   📶 Adapter 2 (AP mode)  ──►  Evil Twin clones the SSID      │
│   🔑 Adapter 3 (Managed)  ──►  Verifies password on real AP  │
│                                                              │
│   ┌────────┐   deauth    ┌──────────┐   joins   ┌─────────┐ │
│   │ Victim │ ──────────► │ Kicked   │ ────────► │  Evil   │ │
│   │        │             │   off    │           │  Twin   │ │
│   └────────┘             └──────────┘           └────┬────┘ │
│                                                      │      │
│              ┌───────────────────────────────────────┘      │
│              ▼                                              │
│   OS shows native sign-in prompt  ──►  Password captured    │
│              │                                              │
│              ▼                                              │
│   Verified against real router  ──►  ✓ Confirmed valid     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## ⚔️ Attack Modes

| Mode | Description | Speed | Requirements |
|------|-------------|-------|--------------|
| 🎯 **WPS Pixie Dust** | Attacks WPS-enabled routers directly | ⚡ Seconds | WPS enabled on target |
| 👯 **Evil Twin + Portal** | OS-native prompt triggered after client connects | 🕐 Victim-dependent | 3 WiFi adapters |
| 🔓 **PMKID + Crack** | Clientless PMKID capture + hashcat | 🕐 Wordlist-dependent | hcxdumptool + hashcat |

---

## 🎨 OS-Aware Captive Portals

iPhisher fingerprints the victim's operating system via `User-Agent` and serves a pixel-matched portal:

<div align="center">

| 🍎 iOS | 🤖 Android | 🪟 Windows |
|:------:|:----------:|:----------:|
| Apple native WiFi sign-in sheet | Material Design 3 dialog | Fluent Design auth dialog |
| SF Pro font · blue "Join" | Roboto · outlined fields | Segoe UI · system dialog |

</div>

These portals are auto-triggered by the OS — Captive Network Assistant on iOS/Android, Network Sign-In on Windows — so the victim **never sees a browser**, only what looks like the system's own password request.

---

## 🧰 Requirements

### Hardware

> ⚠️ **Minimum 2 WiFi adapters** (3 recommended for live verification)

| Role | Capability needed |
|------|-------------------|
| Deauth | Monitor mode + packet injection |
| Evil Twin | AP mode (hostapd) |
| Verification | Managed mode |

**Tested adapters:** Alfa AWUS036ACH · Alfa AWUS036NHA · TP-Link TL-WN722N v1

### Software
- Kali Linux (recommended) or any Debian-based distro
- Python 3.10+
- Root privileges

---

## 📦 Installation

```bash
git clone https://github.com/IMARv2/iphisher.git
cd iphisher
sudo chmod +x install.sh
sudo ./install.sh
```

<details>
<summary><b>Manual dependency install</b></summary>

```bash
sudo apt-get install aircrack-ng hostapd dnsmasq reaver bully \
    hcxdumptool hcxtools hashcat python3-pip
pip3 install -r requirements.txt
```
</details>

---

## 🚀 Usage

```bash
sudo python3 iphisher.py
```

**Interactive flow:**

1. 🔌 **Adapter assignment** — assign each adapter a role (deauth / AP / verify)
2. 📡 **Network scan** — discovers nearby networks with WPS detection
3. 🎯 **Target selection** — pick your target from the table
4. ⚔️ **Attack selection** — WPS Pixie Dust (if available) or Evil Twin
5. 🔑 **Results** — credentials displayed and saved to `/tmp/iphisher_results.txt`

---

## 🗂️ Project Structure

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

## 🆚 Differences from wifiphisher

| Feature | wifiphisher | **iPhisher** |
|---------|:-----------:|:------------:|
| Captive portal | Browser redirect | **OS-native prompt** |
| WPS attack | Limited | **Pixie Dust + PIN** |
| OS detection | Template-based | **User-Agent → matched UI** |
| Credential verification | ❌ | **✓ Live on real AP** |
| PMKID attack | ❌ | **✓ Clientless** |

---

## ⚖️ Legal Disclaimer

> [!WARNING]
> **iPhisher is intended for authorized penetration testing and security research only.**
> Using this tool against networks you do not own or lack **explicit written permission** to test is illegal in most jurisdictions. The authors assume **no liability** for misuse.

---

## 📄 License

Released under the [MIT License](LICENSE).

<div align="center">
<br>
<sub>Built for the penetration testing community · For authorized use only</sub>
</div>
