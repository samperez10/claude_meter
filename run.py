#!/usr/bin/env python3
import sys

if sys.platform == "win32":
    try:
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            print("WARNING: Not running as Administrator!\n")
    except Exception:
        pass

from claude_meter.__main__ import main
main()
