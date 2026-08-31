#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "============================================================"
echo "  Keymouse - mouse look from your keyboard"
echo "============================================================"
echo

# ---------------------------------------------------------------
#  1. Find a working Python that also has tkinter (needed for GUI)
# ---------------------------------------------------------------
PYCMD=""

find_python() {
    local cmd="$1"
    if command -v "$cmd" >/dev/null 2>&1; then
        if "$cmd" -c "import tkinter" >/dev/null 2>&1; then
            PYCMD="$cmd"
            return 0
        fi
    fi
    return 1
}

# Try common names in order of preference
for candidate in python3 python; do
    if find_python "$candidate"; then
        break
    fi
done

if [ -z "$PYCMD" ]; then
    # Scan common install paths (Homebrew on macOS, alt installs on Linux)
    for dir in \
        /usr/local/opt/python*/bin \
        /opt/homebrew/opt/python*/bin \
        "$HOME/.local/bin" \
        /usr/bin \
        /usr/local/bin; do
        if [ -d "$dir" ]; then
            for exe in "$dir"/python3 "$dir"/python; do
                if [ -x "$exe" ]; then
                    if "$exe" -c "import tkinter" >/dev/null 2>&1; then
                        PYCMD="$exe"
                        break 2
                    fi
                fi
            done
        fi
    done
fi

# ---------------------------------------------------------------
#  2. No usable Python - try to install it
# ---------------------------------------------------------------
if [ -z "$PYCMD" ]; then
    echo "[*] Python with tkinter was not found on this machine."
    echo "[*] Attempting to install it now..."
    echo

    INSTALLED=false

    if command -v apt-get >/dev/null 2>&1; then
        echo "[*] Detected apt (Debian/Ubuntu). Installing python3-tk..."
        sudo apt-get update -qq && sudo apt-get install -y python3-tk && INSTALLED=true
    elif command -v dnf >/dev/null 2>&1; then
        echo "[*] Detected dnf (Fedora). Installing python3-tkinter..."
        sudo dnf install -y python3-tkinter && INSTALLED=true
    elif command -v pacman >/dev/null 2>&1; then
        echo "[*] Detected pacman (Arch). Installing python tk..."
        sudo pacman -S --noconfirm python tk && INSTALLED=true
    elif command -v brew >/dev/null 2>&1; then
        echo "[*] Detected Homebrew (macOS). Installing python-tk..."
        brew install python-tk && INSTALLED=true
    elif command -v apk >/dev/null 2>&1; then
        echo "[*] Detected apk (Alpine). Installing python3-tkinter..."
        sudo apk add python3-tkinter && INSTALLED=true
    fi

    if [ "$INSTALLED" = false ]; then
        echo "[!] Could not auto-install Python. Please install Python 3 with"
        echo "    tkinter support manually from https://www.python.org/downloads/"
        echo "    then run this script again."
        exit 1
    fi

    # Re-check after install
    for candidate in python3 python; do
        if find_python "$candidate"; then
            break
        fi
    done

    if [ -z "$PYCMD" ]; then
        echo "[!] Python was installed but could not be located yet."
        echo "    It may be ready the next time. Try running this script again."
        exit 1
    fi
fi

# ---------------------------------------------------------------
#  3. Run Keymouse
# ---------------------------------------------------------------
if [ -f requirements.txt ]; then
    echo "[*] Installing additional requirements..."
    "$PYCMD" -m pip install -r requirements.txt >/dev/null 2>&1
fi

echo "[+] Python ready. Starting Keymouse..."
echo
"$PYCMD" keymouse.py
RC=$?
if [ "$RC" -ne 0 ]; then
    echo
    echo "[!] Keymouse closed with an error, see the output above."
    read -rp "Press Enter to exit..."
fi
exit "$RC"
