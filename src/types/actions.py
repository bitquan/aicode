from dataclasses import dataclass
from enum import Enum
import json
import re


class ActionType(str, Enum):
    GENERATE_CODE = "generate_code"
    EDIT_FILE = "edit_file"
    EXPLAIN = "explain"
    RUN_TESTS = "run_tests"


@dataclass
class AgentAction:
    action: ActionType
    target_path: str
    instruction: str

    @staticmethod
    def from_model_output(text: str) -> "AgentAction":
        block_match = re.search(r"```(?:json)?\n([\s\S]*?)```", text)
        payload = block_match.group(1).strip() if block_match else text.strip()
        data = json.loads(payload)
        return AgentAction(
            action=ActionType(data["action"]),
            target_path=data.get("target_path", ""),
            instruction=data.get("instruction", ""),
        )
