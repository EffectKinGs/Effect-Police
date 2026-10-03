from __future__ import annotations

import os
import runpy
import sys


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BOT_ROOT = os.path.join(PROJECT_ROOT, "police_bot")
if BOT_ROOT not in sys.path:
    sys.path.insert(0, BOT_ROOT)

runpy.run_path(os.path.join(BOT_ROOT, "main.py"), run_name="__main__")
