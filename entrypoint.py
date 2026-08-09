"""PyInstaller entry point for WindowsAIBackup.exe."""
from __future__ import annotations

import multiprocessing
import sys

from waib.cli import main

if __name__ == "__main__":
    # Required so a frozen executable does not re-launch itself in child processes.
    multiprocessing.freeze_support()
    sys.exit(main())
