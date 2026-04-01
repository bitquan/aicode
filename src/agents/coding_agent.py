from pathlib import Path
import ast
import re

from src.config.capabilities import load_capabilities
from src.config.settings import load_settings
from src.providers.ollama_provider import OllamaProvider
from src.prompts.layers import build_layered_prompt, load_prompt_layers
from src.tools.code_runner import run_code
from src.types.actions import AgentAction


class CodingAgent:
    def __init__(self, model="qwen2.5-coder:7b", base_url="http://127.0.0.1:11434", timeout=60):
        settings = load_settings()
        self.model = model if model != "qwen2.5-coder:7b" else settings.model
        self.base_url = (base_url if base_url != "http://127.0.0.1:11434" else settings.base_url).rstrip("/")
        self.timeout = timeout if timeout != 60 else settings.timeout
        self.capabilities = load_capabilities()
        self.settings = settings
        self.provider = OllamaProvider(
            model=self.model,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=settings.max_retries,
            retry_backoff_seconds=settings.retry_backoff_seconds,
        )
        prompts_dir = Path(__file__).resolve().parents[1] / "prompts"
        self.prompt_layers = load_prompt_layers(prompts_dir)
        self.system_prompt = self.prompt_layers.get("system", "")

    def _call_ollama(self, prompt):
        return self.provider.generate(prompt=prompt, system_prompt=self.system_prompt)

    def _build_prompt(self, user_prompt, context=""):
        return build_layered_prompt(user_prompt=user_prompt, layers=self.prompt_layers, context=context)

    def _extract_code(self, text):
        block_match = re.search(r"```(?:python)?\n([\s\S]*?)```", text)
        if block_match:
            return block_match.group(1).strip()
        return text.strip()

    def _extract_text_block(self, text):
        block_match = re.search(r"```(?:[a-zA-Z0-9_+-]+)?\n([\s\S]*?)```", text)
        if block_match:
            return block_match.group(1).strip()
        return text.strip()

    def generate_code(self, prompt):
        layered = self._build_prompt(prompt)
        raw = self._call_ollama(layered)
        return self._extract_code(raw)

    def rewrite_file(self, file_path, instruction, current_content):
        task_prompt = (
            "You are editing one file. Return only the complete updated file content. "
            "Do not explain anything.\n\n"
            f"Target file: {file_path}\n"
            f"Instruction: {instruction}\n\n"
            "Current file content:\n"
            "```\n"
            f"{current_content}\n"
            "```"
        )
        layered = self._build_prompt(task_prompt, context=f"target_file={file_path}")
        raw = self._call_ollama(layered)
        return self._extract_text_block(raw)

    def plan_action(self, user_request):
        planner_prompt = (
            "Return only JSON with keys: action, target_path, instruction. "
            "Action must be one of: generate_code, edit_file, explain, run_tests.\n\n"
            f"Request: {user_request}"
        )
        layered = self._build_prompt(planner_prompt)
        raw = self._call_ollama(layered)
        return AgentAction.from_model_output(raw)

    def evaluate_code(self, code):
        report = {
            "syntax_ok": False,
            "execution_ok": False,
            "stdout": "",
            "stderr": "",
            "returncode": None,
            "timed_out": False,
        }

        try:
            ast.parse(code)
            report["syntax_ok"] = True
        except SyntaxError as exc:
            report["stderr"] = str(exc)
            return report

        result = run_code(code, timeout=5)
        report["execution_ok"] = result["success"]
        report["stdout"] = result["stdout"]
        report["stderr"] = result["stderr"]
        report["returncode"] = result["returncode"]
        report["timed_out"] = result["timed_out"]
        return report