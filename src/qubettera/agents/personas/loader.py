"""Validated persona loader.

Ported from project/Intelligent-Agent-Framework/src/personas.py and
N/week2-agent/src/personas.py, merged to support the base repo's persona schema.

Each persona lives in its own JSON file under personas/. The file name
(without .json) is the persona ID.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from qubettera.paths import PERSONAS_DIR, PROJECT_ROOT

try:
    import jsonschema
except ImportError:
    jsonschema = None

SCHEMA_PATH = PERSONAS_DIR / "schema.json"

REQUIRED_FIELDS = frozenset(
    ["id", "name", "background", "stance", "style", "retrieval_focus", "expertise", "priorities"]
)


class PersonaConfigError(ValueError):
    """Raised when a persona file is missing or has an invalid schema."""


class PersonaConfig(dict):  # type: ignore[type-arg]
    """A validated persona configuration dictionary.

    Behaves like a plain dict so it is drop-in compatible with the existing
    code that accesses persona fields via persona["name"] etc.
    """

    @property
    def id(self) -> str:
        return self["id"]

    @property
    def name(self) -> str:
        return self["name"]

    @property
    def background(self) -> str:
        return self["background"]

    @property
    def stance(self) -> str:
        return self["stance"]

    @property
    def style(self) -> str:
        return self.get("style") or self.get("communication_style", "")

    @property
    def communication_style(self) -> str:
        return self.get("communication_style") or self.get("style", "")

    @property
    def persona_id(self) -> str:
        return self.get("persona_id") or self.get("id", "")

    @property
    def retrieval_focus(self) -> str:
        return self.get("retrieval_focus", "")

    @property
    def expertise(self) -> list[str]:
        return self.get("expertise", [])

    @property
    def priorities(self) -> list[str]:
        v = self.get("priorities", [])
        if isinstance(v, str):
            return [p.strip() for p in v.split(",") if p.strip()]
        return v

    @property
    def skepticism_level(self) -> str:
        return self.get("skepticism_level", "medium")


def _validate(raw: Any) -> PersonaConfig:
    """Validate raw dict against required fields. Returns PersonaConfig."""
    if not isinstance(raw, dict):
        raise PersonaConfigError("Persona must be a JSON object.")

    # Harmonize field aliases between repos
    if "persona_id" in raw and "id" not in raw:
        raw["id"] = raw["persona_id"]
    if "id" in raw and "persona_id" not in raw:
        raw["persona_id"] = raw["id"]
    if "communication_style" in raw and "style" not in raw:
        raw["style"] = raw["communication_style"]
    if "style" in raw and "communication_style" not in raw:
        raw["communication_style"] = raw["style"]
    if "retrieval_focus" not in raw:
        raw["retrieval_focus"] = "evidence and technical trade-offs"
    if "expertise" not in raw or not raw["expertise"]:
        raw["expertise"] = raw.get("priorities") if isinstance(raw.get("priorities"), list) else ["AI Architecture", "Systems"]


    missing = sorted(REQUIRED_FIELDS - raw.keys())
    if missing:
        raise PersonaConfigError(f"Persona missing required fields: {', '.join(missing)}")
    for field in REQUIRED_FIELDS - {"expertise", "priorities"}:
        if not isinstance(raw[field], str) or not raw[field].strip():
            raise PersonaConfigError(f"Persona field {field!r} must be a non-empty string.")
    if not isinstance(raw["expertise"], list) or not raw["expertise"]:
        raise PersonaConfigError("Persona 'expertise' must be a non-empty list.")
    priorities = raw["priorities"]
    if not isinstance(priorities, (list, str)) or not priorities:
        raise PersonaConfigError("Persona 'priorities' must be a non-empty list or string.")
    if jsonschema is not None and SCHEMA_PATH.exists():
        try:
            schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
            jsonschema.validate(instance=raw, schema=schema)
        except jsonschema.ValidationError as exc:
            raise PersonaConfigError(f"Persona schema validation failed: {exc.message}") from exc
    return PersonaConfig(raw)



def load_persona(name_or_path: str) -> PersonaConfig:
    """Load and validate a single persona by ID or file path.

    Args:
        name_or_path: Bare persona ID (e.g. 'dr_aris') or path to a JSON file.

    Returns:
        Validated PersonaConfig.

    Raises:
        PersonaConfigError: If the file is missing, invalid JSON, or fails schema.
    """
    candidate = Path(name_or_path)
    if not candidate.suffix:
        candidate = PERSONAS_DIR / f"{name_or_path}.json"
    elif not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate

    if not candidate.exists():
        available = ", ".join(
            sorted(p.stem for p in PERSONAS_DIR.glob("*.json") if p.stem != "schema")
        )
        raise PersonaConfigError(
            f"Persona {name_or_path!r} not found. Available: {available}"
        )
    try:
        raw = json.loads(candidate.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PersonaConfigError(f"Persona file is not valid JSON: {candidate}") from exc
    if "id" not in raw and "persona_id" not in raw:
        raw["id"] = candidate.stem
    return _validate(raw)



def load_all_personas(directory: Path | str | None = None) -> dict[str, PersonaConfig]:
    """Load all persona JSON files from a directory as an ID -> PersonaConfig dict."""
    target = Path(directory) if directory else PERSONAS_DIR
    personas: dict[str, PersonaConfig] = {}
    for path in sorted(target.glob("*.json")):
        if path.stem in {"schema", "personas", "debate_graph"}:
            continue
        p = load_persona(str(path))
        if p.id in personas:
            raise PersonaConfigError(f"Duplicate persona ID: {p.id!r}")
        personas[p.id] = p
    return personas

