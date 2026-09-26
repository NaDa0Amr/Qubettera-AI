"""Deterministic, retrieval-first grounded opinion generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from qubettera.agents.llm.factory import get_chat_model
from qubettera.agents.personas.loader import PROJECT_ROOT, PersonaConfig, load_persona
from qubettera.agents.tools.retrieval_tool import knowledge_retrieval
from qubettera.paths import PROMPTS_DIR

retrieve_knowledge_base = knowledge_retrieval
RetrievedDocument = dict[str, Any]


class OpinionGenerationError(RuntimeError):
    """Raised when a grounded opinion cannot be produced safely."""


def build_retrieval_query(persona: PersonaConfig, topic: str) -> str:
    topic = topic.strip()
    if not topic:
        raise ValueError("topic must not be blank")
    query = f"{topic} Evidence focus: {persona['retrieval_focus']}"
    return query[:512]


def _parse_documents(tool_output: str) -> list[RetrievedDocument]:
    try:
        payload = json.loads(tool_output)
    except json.JSONDecodeError as exc:
        raise OpinionGenerationError("Retrieval returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise OpinionGenerationError("Retrieval returned an invalid result shape.")
    if payload.get("error"):
        raise OpinionGenerationError(str(payload["error"]))
    documents = payload.get("documents")
    if not isinstance(documents, list) or not documents:
        raise OpinionGenerationError("Retrieval returned no grounding evidence.")
    return documents


def render_opinion_prompt(
    persona: PersonaConfig,
    topic: str,
    documents: list[RetrievedDocument],
    neighbor_opinions: dict[str, str] | None = None,
) -> str:
    environment = Environment(
        loader=FileSystemLoader(PROMPTS_DIR),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return environment.get_template("opinion.jinja").render(
        persona=persona,
        topic=topic,
        task=topic,
        documents=documents,
        retrieved_docs=documents,
        neighbor_opinions=neighbor_opinions or {},
    ).strip()



def _response_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    return json.dumps(content, ensure_ascii=False, default=str).strip()


def generate_opinion(
    persona_id: str,
    topic: str,
    *,
    model: BaseChatModel | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Retrieve first, generate from evidence, validate citations, and persist."""

    persona = load_persona(persona_id)
    query = build_retrieval_query(persona, topic)
    tool_output = str(
        retrieve_knowledge_base.invoke({"query": query, "top_k": 5})
    )
    documents = _parse_documents(tool_output)
    prompt = render_opinion_prompt(persona, topic.strip(), documents)
    response = (model or get_chat_model()).invoke(
        [
            SystemMessage(
                content="Write a grounded technical opinion using only the supplied evidence."
            ),
            HumanMessage(content=prompt),
        ]
    )
    opinion_text = _response_text(response.content)
    if not opinion_text:
        raise OpinionGenerationError("The model returned an empty opinion.")
    exact_citations = [
        document["url"]
        for document in documents
        if document.get("url") and f"[Source: {document['url']}]" in opinion_text
    ]
    if not exact_citations:
        raise OpinionGenerationError(
            "The model did not copy any retrieved URL in the required [Source: URL] format."
        )

    now = datetime.now(timezone.utc)
    result = {
        "persona_id": persona_id,
        "topic": topic.strip(),
        "opinion_text": opinion_text,
        "sources": [
            {
                "url": document["url"],
                "title": document["title"],
                "snippet": document["text"][:300],
            }
            for document in documents
        ],
        "timestamp": now.isoformat(),
    }
    destination = output_dir or PROJECT_ROOT / "outputs" / "opinions"
    destination.mkdir(parents=True, exist_ok=True)
    filename = now.strftime("%Y%m%dT%H%M%S%fZ") + f"-{persona_id}.json"
    (destination / filename).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return result

