"""Stable project paths shared by all Qubettera subsystems."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESOURCES_DIR = PROJECT_ROOT / "resources"
PERSONAS_DIR = RESOURCES_DIR / "personas"
PROMPTS_DIR = RESOURCES_DIR / "prompts"
CONFIGS_DIR = RESOURCES_DIR / "configs"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

