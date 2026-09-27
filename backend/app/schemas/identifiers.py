from typing import Annotated
from fastapi import Path

# IDs become filenames; disallow separators and traversal components.
DiscussionId = Annotated[str, Path(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")]
