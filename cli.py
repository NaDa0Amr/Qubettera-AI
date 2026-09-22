"""Deprecated launcher; use the installed ``qubettera`` command."""

import sys
from pathlib import Path
from warnings import warn

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from qubettera.cli import main

warn("python cli.py is deprecated; use 'qubettera'", DeprecationWarning)
raise SystemExit(main())
