#!/usr/bin/env bash
# ==============================================================================
# NovaFlix Sovereign Media Server - Universal Quick Install Script
# Works on Debian, Ubuntu, Linux Mint, Fedora, RHEL, CentOS, Arch, Alpine & macOS
#
# Usage:
#   curl -fsSL https://novaflix.ertechlab.com/install.sh | bash
# ==============================================================================

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
AMBER='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
cat << 'EOF'
    _   __                 ______ _ _      
   / | / /___ _   ______ _/ ____/| (_)  __ 
  /  |/ / __ \ | / / __ `/ /_   | | | |/_/ 
 / /|  / /_/ / |/ / /_/ / __/   | | |>  <  
/_/ |_/\____/|___/\__,_/_/      |_|_/_/|_|  
     SOVEREIGN OPEN-SOURCE MEDIA SERVER
EOF
echo -e "${NC}"

echo -e "${AMBER}[*] Detecting Operating System & Architecture...${NC}"

OS="$(uname -s)"
ARCH="$(uname -m)"

if [ "$OS" = "Linux" ]; then
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO=$ID
    else
        DISTRO="linux"
    fi
elif [ "$OS" = "Darwin" ]; then
    DISTRO="macos"
else
    echo -e "${RED}[!] Unsupported OS: $OS. On Windows, please run: irm https://novaflix.ertechlab.com/install.ps1 | iex${NC}"
    exit 1
fi

echo -e "${GREEN}[✓] Detected: $OS ($DISTRO - $ARCH)${NC}"

# Check for root or sudo
SUDO=""
if [ "$(id -u)" != "0" ]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    else
        echo -e "${RED}[!] Please run as root or install sudo.${NC}"
        exit 1
    fi
fi

# 1. Install prerequisites
echo -e "${AMBER}[*] Installing dependencies (Python 3, FFmpeg, curl, git)...${NC}"
case "$DISTRO" in
    ubuntu|debian|linuxmint|pop|raspbian)
        $SUDO apt-get update -qq
        $SUDO apt-get install -y -qq python3 python3-pip python3-venv ffmpeg curl git zip unzip
        ;;
    fedora|rhel|centos|rocky|alma)
        $SUDO dnf install -y python3 python3-pip ffmpeg curl git zip unzip 2>/dev/null || $SUDO yum install -y python3 python3-pip ffmpeg curl git zip unzip
        ;;
    arch|manjaro)
        $SUDO pacman -Sy --noconfirm python python-pip ffmpeg curl git zip unzip
        ;;
    alpine)
        $SUDO apk add --no-cache python3 py3-pip ffmpeg curl git bash
        ;;
    macos)
        if ! command -v brew >/dev/null 2>&1; then
            echo -e "${AMBER}[*] Homebrew not detected. Installing Homebrew...${NC}"
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        brew install python ffmpeg git curl
        ;;
    *)
        if command -v apt-get >/dev/null 2>&1; then
            $SUDO apt-get update -qq && $SUDO apt-get install -y python3 python3-pip python3-venv ffmpeg curl git
        elif command -v dnf >/dev/null 2>&1; then
            $SUDO dnf install -y python3 python3-pip ffmpeg curl git
        fi
        ;;
esac

# 2. Deploy NovaFlix Server
INSTALL_DIR="/opt/novaflix"
if [ "$DISTRO" = "macos" ]; then
    INSTALL_DIR="$HOME/Applications/NovaFlix"
    mkdir -p "$INSTALL_DIR"
else
    $SUDO mkdir -p "$INSTALL_DIR"
    $SUDO chown -R "$(id -u):$(id -g)" "$INSTALL_DIR"
fi

echo -e "${AMBER}[*] Fetching NovaFlix Server codebase...${NC}"
if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR" && git pull --quiet
else
    git clone --depth 1 https://github.com/digdast/novaflix.git "$INSTALL_DIR" 2>/dev/null || {
        echo -e "${AMBER}[*] Downloading release archive from NovaFlix hub...${NC}"
        curl -fsSL "https://novaflix.ertechlab.com/downloads/novaflix-linux-x64.tar.gz" -o /tmp/novaflix.tar.gz
        tar -xzf /tmp/novaflix.tar.gz -C /opt/
    }
fi

cd "$INSTALL_DIR"

# 3. Setup Virtual Environment
echo -e "${AMBER}[*] Setting up Python virtual environment...${NC}"
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip --quiet
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet

# 4. Systemd service setup (Linux)
if [ "$DISTRO" != "macos" ] && command -v systemctl >/dev/null 2>&1; then
    echo -e "${AMBER}[*] Configuring systemd background service...${NC}"
    $SUDO tee /etc/systemd/system/novaflix.service > /dev/null << SERVICE_EOF
[Unit]
Description=NovaFlix Sovereign Media Server
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/uvicorn novaflix.main:app --host 0.0.0.0 --port 8096
Restart=always
RestartSec=5
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
SERVICE_EOF

    $SUDO systemctl daemon-reload
    $SUDO systemctl enable novaflix.service
    $SUDO systemctl restart novaflix.service
    echo -e "${GREEN}[✓] NovaFlix systemd service enabled and started!${NC}"
else
    echo -e "${AMBER}[*] Starting NovaFlix in background...${NC}"
    nohup "$INSTALL_DIR/venv/bin/uvicorn" novaflix.main:app --host 0.0.0.0 --port 8096 > "$INSTALL_DIR/novaflix.log" 2>&1 &
fi

SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$SERVER_IP" ]; then
    SERVER_IP="localhost"
fi

echo -e "${GREEN}"
echo "=========================================================================="
echo "  🎉 NOVAFLIX SOVEREIGN MEDIA SERVER INSTALLED SUCCESSFULLY!"
echo "=========================================================================="
echo -e "${NC}"
echo -e "Access your sovereign media server now:"
echo -e "  🎬 Local Web Cinema:  ${CYAN}http://${SERVER_IP}:8096${NC}"
echo -e "  📥 Downloads Portal:  ${CYAN}http://${SERVER_IP}:8096/portal${NC}"
echo ""
echo -e "Service Commands:"
echo -e "  systemctl status novaflix"
echo -e "  systemctl restart novaflix"
echo "=========================================================================="
