from jinja2 import Environment, FileSystemLoader

from qubettera.paths import PROMPTS_DIR

_env = Environment(loader=FileSystemLoader(str(PROMPTS_DIR)))

def load_prompt(name: str, **kwargs) -> str:
    template = _env.get_template(name)
    kwargs.setdefault("memory_summary", "")
    # Outside a discussion there is no later round, so the prompt is final.
    kwargs.setdefault("final_round", True)
    # Absent means "the KB round is still available", the pre-ladder default.
    kwargs.setdefault("kb_exhausted", False)
    return template.render(**kwargs)
