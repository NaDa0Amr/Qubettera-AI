"""Web configuration shares the CLI's resources, environment and outputs."""
import os
from pathlib import Path
from dotenv import load_dotenv
from qubettera.paths import PROJECT_ROOT, CONFIGS_DIR, PERSONAS_DIR, OUTPUTS_DIR

load_dotenv(PROJECT_ROOT / ".env", override=False)


def _path_env(name: str, default: Path) -> Path:
    path = Path(os.getenv(name) or default).expanduser()
    return (PROJECT_ROOT / path).resolve() if not path.is_absolute() else path.resolve()


WEEK3_OUTPUT_DIR = _path_env("WEEK3_OUTPUT_DIR", OUTPUTS_DIR / "discussions")
ANALYTICS_OUT_DIR = _path_env("ANALYTICS_OUT_DIR", OUTPUTS_DIR / "analytics")
ANALYTICS_VISUALS_DIR = ANALYTICS_OUT_DIR / "visuals"
DEFAULT_GRAPH_PATH = CONFIGS_DIR / "agent_graph.json"
DEFAULT_PERSONAS_PATH = PERSONAS_DIR / "personas.json"
ALLOWED_ORIGINS = [v.strip() for v in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if v.strip()]


def repo_status() -> dict:
    return {
        "qubettera": {"path": str(PROJECT_ROOT / "src" / "qubettera"),
                      "found": (PROJECT_ROOT / "src" / "qubettera").is_dir()},
        "personas": {"path": str(DEFAULT_PERSONAS_PATH),
                     "found": DEFAULT_PERSONAS_PATH.is_file()},
    }
