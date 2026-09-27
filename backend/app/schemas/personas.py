from __future__ import annotations

from pydantic import BaseModel


class Persona(BaseModel):
    """One entry from Multi-Agent-Collaboration/personas/personas.json.

    Deliberately permissive on the list-typed fields: personas.json is a
    teammate's file and some entries represent e.g. `expertise` as a single
    string rather than a list. extra="allow" also means any field present in
    the JSON that isn't named here still passes through untouched.
    """

    id: str
    name: str
    role: str | None = None
    background: str | None = None
    stance: str | None = None
    style: str | None = None
    expertise: list[str] | str | None = None
    priorities: list[str] | str | None = None
    retrieval_focus: list[str] | str | None = None
    personality_traits: list[str] | str | None = None

    model_config = {"extra": "allow"}