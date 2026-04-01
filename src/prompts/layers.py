from pathlib import Path


def _read_optional(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def load_prompt_layers(prompts_dir: Path) -> dict:
    return {
        "system": _read_optional(prompts_dir / "system_prompt.txt"),
        "developer": _read_optional(prompts_dir / "developer_prompt.txt"),
        "tool": _read_optional(prompts_dir / "tool_prompt.txt"),
    }


def build_layered_prompt(user_prompt: str, layers: dict, context: str = "") -> str:
    parts = []
    if layers.get("system"):
        parts.append(f"[SYSTEM]\n{layers['system']}")
    if layers.get("developer"):
        parts.append(f"[DEVELOPER]\n{layers['developer']}")
    if layers.get("tool"):
        parts.append(f"[TOOLS]\n{layers['tool']}")
    if context:
        parts.append(f"[CONTEXT]\n{context}")
    parts.append(f"[USER]\n{user_prompt}")
    return "\n\n".join(parts)
