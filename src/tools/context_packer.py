def pack_context(snippets: list[dict], max_chars: int = 4000) -> str:
    parts = []
    remaining = max_chars

    for item in snippets:
        header = f"FILE: {item.get('path')} (score={item.get('score', 0)})\n"
        body = item.get("snippet", "")
        block = header + body + "\n\n"
        if len(block) <= remaining:
            parts.append(block)
            remaining -= len(block)
        else:
            if remaining > 120:
                parts.append(block[:remaining])
            break

    return "".join(parts).strip()
