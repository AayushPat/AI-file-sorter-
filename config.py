"""
CONFIGURATION CONSTANTS MODULE

Defines paths, directories, and default values used throughout the application.
"""

from pathlib import Path
from typing import List

# USER HOME DIRECTORY
HOME: Path = Path.home()

# ROOT STRING (kept as str because Interpreter expects a string)
ROOT: str = str(HOME)

# APPLICATION CONFIG DIRECTORY
CONFIG_DIR: Path = HOME / ".ai_file_sorter"
CONFIG_PATH: Path = CONFIG_DIR / "config.json"

# DEFAULT SORT DIRECTORY
DEFAULT_SORTME: Path = HOME / "SortMe"

# DEFAULT ALLOWED ROOT DIRECTORIES (for initial setup)
DEFAULT_ALLOWED_ROOTS: List[Path] = [
    HOME / "Downloads",
    HOME / "Documents",
    DEFAULT_SORTME,
]

# DEFAULT AI MODEL
DEFAULT_AI_MODEL: str = "llama3.1:8b"

# POPULAR AI MODELS (for easy switching)
POPULAR_MODELS: List[str] = [
    "llama3.1:8b",
    "llama3.2:3b",
    "qwen2.5:7b",
    "mistral:7b",
    "llama3.1:70b",
]


def get_ai_model() -> str:
    """
    Get the currently configured AI model from config.json.
    Falls back to DEFAULT_AI_MODEL if not set or if config doesn't exist.
    """
    import json
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text())
            return data.get("ai_model", DEFAULT_AI_MODEL)
        except Exception:
            return DEFAULT_AI_MODEL
    return DEFAULT_AI_MODEL

