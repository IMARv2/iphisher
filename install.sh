#!/usr/bin/env bash
set -e

if [ "$EUID" -ne 0 ]; then
    echo "[!] Please run as root: sudo ./install.sh"
    exit 1
fi

echo "[*] Installing system dependencies..."
apt-get update -qq
apt-get install -y \
    aircrack-ng \
    hostapd \
    dnsmasq \
    reaver \
    bully \
    hcxdumptool \
    hcxtools \
    hashcat \
    python3-pip \
    python3-dev \
    libpcap-dev \
    net-tools \
    iw \
    wireless-tools

echo "[*] Installing Python dependencies..."
pip3 install -r requirements.txt

chmod +x iphisher.py

echo ""
echo "[+] iPhisher installation complete."
echo "    Run with: sudo python3 iphisher.py"
