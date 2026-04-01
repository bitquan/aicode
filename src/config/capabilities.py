from pathlib import Path
import json


def load_capabilities(config_path: str | None = None) -> dict:
    if config_path:
        path = Path(config_path)
    else:
        path = Path(__file__).with_name("capabilities.json")
    return json.loads(path.read_text(encoding="utf-8"))
