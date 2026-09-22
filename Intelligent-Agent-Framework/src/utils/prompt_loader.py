from jinja2 import Environment, FileSystemLoader

_env = Environment(loader=FileSystemLoader("prompts"))

def load_prompt(name: str, **kwargs) -> str:
    template = _env.get_template(name)
    kwargs.setdefault("memory_summary", "")
    return template.render(**kwargs)