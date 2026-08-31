#requires -Version 5.1
<#
  Keymouse - mouse look from your keyboard
  Cross-platform launcher (Windows / Linux / macOS) using PowerShell Core.
  On Windows PowerShell 5.1 this runs the batch logic; the same script works
  under pwsh (PowerShell 6+) on any platform.
#>

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

function Write-Banner {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host "  Keymouse - mouse look from your keyboard"
    Write-Host "============================================================"
    Write-Host ""
}

# Locate a Python that has tkinter. Returns $null if none found.
function Find-Python {
    $candidates = @("python3", "python")
    if ($env:OS -eq 'Windows_NT') {
        $candidates = @("py", "python", "python3")
    }

    foreach ($c in $candidates) {
        $exe = Get-Command $c -ErrorAction SilentlyContinue
        if ($exe -eq $null) { continue }

        $pyArgs = @()
        if ($c -eq 'py') { $pyArgs = @('-3') }

        & $exe.Source @pyArgs -c "import tkinter" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            return @{ Cmd = $exe.Source; Args = $pyArgs }
        }
    }

    if ($env:OS -eq 'Windows_NT') {
        # Scan common per-user / system install spots.
        $spots = @()
        if ($env:LOCALAPPDATA) {
            $spots += Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*" -Directory -ErrorAction SilentlyContinue
        }
        if ($env:ProgramFiles) {
            $spots += Get-ChildItem "$env:ProgramFiles\Python3*" -Directory -ErrorAction SilentlyContinue
        }
        $pfx86 = $env:'ProgramFiles(x86)'
        if ($pfx86) {
            $spots += Get-ChildItem "$pfx86\Python3*" -Directory -ErrorAction SilentlyContinue
        }
        foreach ($spot in $spots) {
            $exe = Join-Path $spot.FullName "python.exe"
            if (Test-Path -LiteralPath $exe) {
                if ($exe -c "import tkinter" 2>$null | Out-Null) { }
                & $exe -c "import tkinter" 2>$null | Out-Null
                if ($LASTEXITCODE -eq 0) {
                    return @{ Cmd = $exe; Args = @() }
                }
            }
        }
    }

    return $null
}

function Install-PythonOnWindows {
    where.exe winget 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[*] Using winget to install Python 3.12..."
        winget install --id Python.Python.3.12 --exact --silent --accept-package-agreements --accept-source-agreements 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { return }
        Write-Host "[!] winget install failed - falling back to direct download."
    }

    $dlUrl = "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
    $inst   = Join-Path $env:TEMP "python-3.12.8-amd64.exe"
    Write-Host "[*] Downloading the Python installer..."
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $dlUrl -OutFile $inst
    } catch {
        throw "Download failed. Install Python manually from https://www.python.org/downloads/"
    }
    Write-Host "[*] Running the installer silently..."
    $p = Start-Process -FilePath $inst -ArgumentList '/quiet','InstallAllUsers=0','PrependPath=1','Include_tcltk=1','Include_test=0','SimpleInstall=1' -Wait -PassThru
    Remove-Item -LiteralPath $inst -Force -ErrorAction SilentlyContinue
}

function Install-PythonOnUnix {
    foreach ($mgr in @(
        @{ Test = { Get-Command apt-get -ErrorAction SilentlyContinue };  Install = { sudo apt-get update -qq; sudo apt-get install -y python3-tk } ; Name = "apt (Debian/Ubuntu)"; Pkg = "python3-tk" },
        @{ Test = { Get-Command dnf -ErrorAction SilentlyContinue };     Install = { sudo dnf install -y python3-tkinter }; Name = "dnf (Fedora)"; Pkg = "python3-tkinter" },
        @{ Test = { Get-Command pacman -ErrorAction SilentlyContinue };  Install = { sudo pacman -S --noconfirm python tk }; Name = "pacman (Arch)"; Pkg = "python tk" },
        @{ Test = { Get-Command brew -ErrorAction SilentlyContinue };     Install = { brew install python-tk }; Name = "Homebrew (macOS)"; Pkg = "python-tk" },
        @{ Test = { Get-Command apk -ErrorAction SilentlyContinue };      Install = { sudo apk add python3-tkinter }; Name = "apk (Alpine)"; Pkg = "python3-tkinter" }
    )) {
        $found = & $mgr.Test
        if ($found) {
            Write-Host "[*] Detected $($mgr.Name). Installing $($mgr.Pkg)..."
            & $mgr.Install
            return $true
        }
    }
    return $false
}

Write-Banner

# ---------------------------------------------------------------
#  1. Find a working Python that also has tkinter (needed for GUI)
# ---------------------------------------------------------------
$py = Find-Python

# ---------------------------------------------------------------
#  2. No usable Python - install it automatically
# ---------------------------------------------------------------
if ($py -eq $null) {
    Write-Host "[*] Python with tkinter was not found on this machine."
    Write-Host "[*] Installing it now - this can take a minute or two."
    Write-Host ""

    $installed = $false
    if ($env:OS -eq 'Windows_NT') {
        Install-PythonOnWindows
        $installed = $true
    } else {
        $installed = Install-PythonOnUnix
    }

    if (-not $installed) {
        Write-Host "[!] Could not auto-install Python. Please install Python 3 with"
        Write-Host "    tkinter support manually from https://www.python.org/downloads/"
        Write-Host "    then run this script again."
        exit 1
    }

    $py = Find-Python
    if ($py -eq $null) {
        Write-Host "[!] Python was installed but could not be located yet."
        Write-Host "    It will be ready the next time. Run this script again."
        exit 1
    }
}

# ---------------------------------------------------------------
#  3. Run Keymouse
# ---------------------------------------------------------------
if (Test-Path -LiteralPath (Join-Path $PSScriptRoot "requirements.txt")) {
    Write-Host "[*] Installing additional requirements..."
    & $py.Cmd @py.Args -m pip install -r requirements.txt 2>$null | Out-Null
}

Write-Host "[+] Python ready. Starting Keymouse..."
Write-Host ""
& $py.Cmd @py.Args (Join-Path $PSScriptRoot "keymouse.py")
$rc = $LASTEXITCODE
if ($rc -ne 0) {
    Write-Host ""
    Write-Host "[!] Keymouse closed with an error, see the output above."
    Read-Host "Press Enter to exit..." | Out-Null
}
exit $rc
