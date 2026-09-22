"""Deprecated launcher for the multi-agent discussion demo."""

import sys
from pathlib import Path
from warnings import warn

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from qubettera.cli import main

warn("python demo.py is deprecated; use 'qubettera discuss run'", DeprecationWarning)
raise SystemExit(main(["discuss", "run"]))
