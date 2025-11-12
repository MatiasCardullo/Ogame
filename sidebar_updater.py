
"""Backward-compatibility shim: re-export the JS script constants.

This used to be `sidebar_updater.py`. The JS extraction scripts live now in
`js_scripts.py` — import them from here for any older code that still
imports `sidebar_updater`.
"""

from js_scripts import *

__all__ = [
    "extract_meta_script",
    "extract_resources_script",
    "extract_queue_script",
    "extract_auction_script",
]

