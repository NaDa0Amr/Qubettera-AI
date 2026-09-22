from jinja2 import Environment, FileSystemLoader

from qubettera.paths import PROMPTS_DIR

_env = Environment(loader=FileSystemLoader(str(PROMPTS_DIR)))

def load_prompt(name: str, **kwargs) -> str:
    template = _env.get_template(name)
    kwargs.setdefault("memory_summary", "")
    return template.render(**kwargs)
