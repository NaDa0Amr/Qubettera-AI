"""Source identity validation; this does not establish claim entailment."""
import re

from qubettera.agents.agent.budget import clip

CITATION = re.compile(r"\[Source: ([^\]\n]+)\]")
RULES = (
    "Cite only current evidence using exact [Source: URL] citations. "
    "Historical opinions, citations and summaries are discussion context, not fresh evidence. "
    "If no current citable evidence is available, explicitly say 'No supporting evidence is available'. "
    "Never invent sources. Keep the response within 6000 characters."
)


def citation_errors(text, evidence):
    allowed = {item.url for item in evidence if item.url}
    cited = CITATION.findall(text)
    errors = []
    if any(url not in allowed for url in cited):
        errors.append("citation refers to a source outside current evidence")
    if text.count("[Source:") != len(cited):
        errors.append("malformed source citation")
    if allowed and not any(url in allowed for url in cited):
        errors.append("missing exact current-evidence citation")
    if not allowed and "no supporting evidence is available" not in text.lower():
        errors.append("missing acknowledgement of unsupported evidence")
    return tuple(errors)


def flag_answer(text, warnings):
    text = re.sub(r"\n\n\[Validation warning: [^\]]*\]$", "", text)
    suffix = "\n\n[Validation warning: " + "; ".join(warnings) + "]" if warnings else ""
    return clip(text, 6000 - len(suffix)) + suffix
