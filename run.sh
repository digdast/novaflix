#!/usr/bin/env bash
# NovaFlix - Linux & macOS Launcher

set -e

echo "========================================================"
echo "  🎬  NovaFlix - Sovereign Next-Gen Media Platform"
echo "  Cinema Web Client: http://localhost:8096"
echo "  Plex-Style Portal: http://localhost:8096/portal"
echo "========================================================"

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 could not be found. Please install Python 3.10+."
    exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo "[*] Ensuring dependencies..."
pip3 install -r requirements.txt --quiet

echo "[*] Launching NovaFlix Server on port 8096..."
export PYTHONPATH="$SCRIPT_DIR"
python3 -m novaflix.main
