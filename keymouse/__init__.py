"""Keymouse - keyboard-driven mouse look (Windows, Linux, macOS).

This package is organized into focused modules so that the math, the
configuration, the OS input layer and the UI can be reasoned about and
tested independently. The input layer auto-selects a backend (native
Win32 on Windows, pynput on Linux/macOS) behind one uniform interface.
"""

__version__ = "2.1.0"
