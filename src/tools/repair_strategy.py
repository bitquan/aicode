def choose_repair_strategy(failure_category: str) -> dict:
    mapping = {
        "syntax": {
            "strategy": "syntax_patch",
            "instructions": "Fix syntax first. Do not refactor beyond what is required to parse and pass tests.",
        },
        "dependency": {
            "strategy": "dependency_patch",
            "instructions": "Fix imports and dependency usage within the file. Avoid adding new external dependencies unless necessary.",
        },
        "assertion": {
            "strategy": "logic_patch",
            "instructions": "Adjust logic to satisfy assertions while preserving intended behavior.",
        },
        "type": {
            "strategy": "type_patch",
            "instructions": "Fix type/signature mismatches and argument handling.",
        },
        "name": {
            "strategy": "name_patch",
            "instructions": "Fix undefined names and scope issues with minimal changes.",
        },
        "runtime": {
            "strategy": "runtime_patch",
            "instructions": "Fix runtime exception path indicated by traceback.",
        },
        "timeout": {
            "strategy": "perf_patch",
            "instructions": "Remove hangs/infinite loops and reduce expensive operations.",
        },
        "unknown": {
            "strategy": "generic_patch",
            "instructions": "Apply smallest safe fix based on failing output.",
        },
    }
    return mapping.get(failure_category, mapping["unknown"])
