"""Compatibility shim module.

Keep this file small so older imports continue to work while the codebase
uses `main_window.py` and `popup_window.py`.

Usage:
    from browser_window import BrowserWindow
    win = BrowserWindow(...)
"""

from popup_window import PopupWindow as BrowserWindow

__all__ = ["BrowserWindow"]

