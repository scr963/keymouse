#!/usr/bin/env bash
# Keymouse launcher.
#
# This script ONLY finds a Python with tkinter and runs the app. It does
# NOT run pip, sudo or any other command that could block or grab the
# system: the app itself installs its own missing dependency (pynput) on
# non-Windows machines, so there is no fragile install step here.
set -euo pipefail
cd "$(dirname "$0")"

echo "============================================================"
echo "  Keymouse - mouse look from your keyboard"
echo "============================================================"
echo

# ---------------------------------------------------------------
#  Find a Python that has tkinter (needed for the GUI).
#  This is read-only - no installs happen here.
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

for candidate in python3 python; do
    if find_python "$candidate"; then
        break
    fi
done

if [ -z "$PYCMD" ]; then
    echo "[!] No Python with tkinter found. Install Python 3 with tkinter,"
    echo "    then run this script again."
    exit 1
fi

# ---------------------------------------------------------------
#  Run Keymouse. The app self-installs any missing dependency and
#  never blocks the desktop.
# ---------------------------------------------------------------
echo "[+] Python ready. Starting Keymouse..."
echo
"$PYCMD" keymouse.py
RC=$?
if [ "$RC" -ne 0 ]; then
    echo
    echo "[!] Keymouse did not start (see output above)."
    read -rp "Press Enter to exit..."
fi
exit "$RC"
