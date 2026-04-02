"""
API Generator — transform plain Python functions into FastAPI route stubs.
Analyses function signatures and docstrings to emit ready-to-use endpoint code.
"""

import ast
import textwrap
from pathlib import Path
from typing import Any


# ─── Type-hint map ────────────────────────────────────────────────────────────

_PY_TO_JSON = {
    "str": "str",
    "int": "int",
    "float": "float",
    "bool": "bool",
    "list": "list",
    "dict": "dict",
    "bytes": "bytes",
    "None": "None",
}

_VALID_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
_VALID_GENERATION_MODES = {"passthrough", "mock", "stub"}


def _annotation_name(ann: ast.expr | None) -> str:
    if ann is None:
        return "Any"
    if isinstance(ann, ast.Name):
        return ann.id
    if isinstance(ann, ast.Attribute):
        return ann.attr
    if isinstance(ann, ast.Subscript):
        return ast.unparse(ann)
    return "Any"


# ─── API Generator ────────────────────────────────────────────────────────────

class APIGenerator:
    """Transform Python functions into FastAPI route stubs."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_from_file(
        self,
        file_path: str,
        http_method: str = "POST",
        generation_mode: str = "passthrough",
    ) -> dict[str, Any]:
        """Emit FastAPI route stubs for all non-private functions in *file_path*."""
        path = self._resolve(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}", "routes": []}

        method = http_method.upper()
        mode = generation_mode.lower()
        if method not in _VALID_HTTP_METHODS:
            return {
                "error": f"Unsupported HTTP method: {http_method}",
                "routes": [],
            }
        if mode not in _VALID_GENERATION_MODES:
            return {
                "error": f"Unsupported generation mode: {generation_mode}",
                "routes": [],
            }

        source = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return {"error": str(exc), "routes": []}

        routes: list[dict] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    routes.append(self._build_route(node, method, mode))

        module_name = path.stem
        header = self._build_router_header(module_name, str(path), mode)
        return {
            "file": str(path.relative_to(self.workspace_root)),
            "route_count": len(routes),
            "generation_mode": mode,
            "router_header": header,
            "routes": routes,
            "full_code": header + "\n\n" + "\n\n".join(r["code"] for r in routes),
        }

    def generate_from_function(
        self,
        func_name: str,
        params: list[dict],
        return_type: str = "dict",
        http_method: str = "POST",
        generation_mode: str = "passthrough",
    ) -> dict[str, Any]:
        """Generate a single FastAPI route stub from explicit metadata."""
        endpoint = func_name.lower().replace("_", "-")
        method = http_method.upper()
        mode = generation_mode.lower()

        if method not in _VALID_HTTP_METHODS:
            return {"error": f"Unsupported HTTP method: {http_method}"}
        if mode not in _VALID_GENERATION_MODES:
            return {"error": f"Unsupported generation mode: {generation_mode}"}

        # Build Pydantic model if there are body params
        model_code = ""
        param_names = [p["name"] for p in params if p["name"] not in ("self", "cls")]
        if param_names and method in ("POST", "PUT", "PATCH"):
            fields = "\n".join(
                f"    {p['name']}: {p.get('type', 'str')}" for p in params
                if p["name"] not in ("self", "cls")
            )
            model_name = f"{func_name.title().replace('_', '')}Request"
            model_code = f"class {model_name}(BaseModel):\n{fields}\n"
        else:
            model_name = None

        route_func = self._render_route(
            func_name=func_name,
            endpoint=f"/{endpoint}",
            method=method,
            model_name=model_name,
            return_type=return_type,
            generation_mode=mode,
        )

        header = self._build_router_header("generated", None, mode, include_prefix=False)
        return {
            "function": func_name,
            "endpoint": f"/{endpoint}",
            "method": method,
            "generation_mode": mode,
            "code": header + "\n" + (model_code + "\n" if model_code else "") + route_func,
        }

    # ── Internals ─────────────────────────────────────────────────────────────

    def _build_route(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        http_method: str,
        generation_mode: str,
    ) -> dict:
        endpoint = f"/{node.name.lower().replace('_', '-')}"
        ret = _annotation_name(node.returns)
        params = [
            {"name": a.arg, "type": _annotation_name(a.annotation)}
            for a in node.args.args
            if a.arg not in ("self", "cls")
        ]
        code = self._render_route(
            func_name=node.name,
            endpoint=endpoint,
            method=http_method.upper(),
            model_name=None,
            return_type=ret,
            generation_mode=generation_mode,
            params=params,
        )
        return {
            "name": node.name,
            "endpoint": endpoint,
            "method": http_method.upper(),
            "generation_mode": generation_mode,
            "code": code,
        }

    def _render_route(
        self,
        func_name: str,
        endpoint: str,
        method: str,
        model_name: str | None,
        return_type: str,
        generation_mode: str,
        params: list[dict] | None = None,
    ) -> str:
        decorator = f'@router.{method.lower()}("{endpoint}")'
        if model_name:
            sig = f"payload: {model_name}"
        elif params:
            sig = ", ".join(f"{p['name']}: {p['type']}" for p in params)
        else:
            sig = ""

        if model_name:
            input_payload_expr = "payload.model_dump()"
        elif params:
            input_payload_expr = "{" + ", ".join(
                f'"{p["name"]}": {p["name"]}' for p in params
            ) + "}"
        else:
            input_payload_expr = "{}"

        if generation_mode == "passthrough":
            body = (
                f'input_payload = {input_payload_expr}\n'
                f'    return _invoke_impl("{func_name}", input_payload)'
            )
        elif generation_mode == "mock":
            body = (
                f'input_payload = {input_payload_expr}\n'
                f'    return _mock_response("{func_name}", input_payload)'
            )
        else:
            body = (
                "raise HTTPException(\n"
                "        status_code=501,\n"
                f'        detail="{func_name} route generated in stub mode; implement handler",\n'
                "    )"
            )

        return textwrap.dedent(f"""\
            {decorator}
            async def {func_name}({sig}) -> {return_type}:
                \"\"\"Auto-generated endpoint for {func_name}.\"\"\"
                {body}
        """)

    def _build_router_header(
        self,
        module_name: str,
        source_path: str | None,
        generation_mode: str,
        include_prefix: bool = True,
    ) -> str:
        prefix_expr = f'prefix="/{module_name}", tags=["{module_name}"]' if include_prefix else ""
        router_line = f"router = APIRouter({prefix_expr})" if prefix_expr else "router = APIRouter()"
        source_literal = repr(source_path) if source_path else "None"

        helpers = textwrap.dedent(f"""\
            _GENERATION_MODE = {generation_mode!r}
            _SOURCE_FILE = {source_literal}

            def _load_source_module() -> Any:
                if not _SOURCE_FILE:
                    return None
                spec = importlib.util.spec_from_file_location("generated_source_module", _SOURCE_FILE)
                if spec is None or spec.loader is None:
                    return None
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module

            _SOURCE_MODULE = _load_source_module()

            def _invoke_impl(function_name: str, payload: dict[str, Any]) -> Any:
                if _SOURCE_MODULE is None:
                    return _mock_response(function_name, payload)
                target = getattr(_SOURCE_MODULE, function_name, None)
                if target is None:
                    return _mock_response(function_name, payload)
                try:
                    return target(**payload)
                except TypeError as exc:
                    raise HTTPException(status_code=400, detail=f"Invalid payload for {{function_name}}: {{exc}}") from exc
                except Exception as exc:
                    raise HTTPException(status_code=500, detail=f"Handler {{function_name}} failed: {{exc}}") from exc

            def _mock_response(function_name: str, payload: dict[str, Any]) -> dict[str, Any]:
                return {{
                    "status": "mock",
                    "handler": function_name,
                    "input": payload,
                }}
        """)

        return textwrap.dedent(f"""\
            # Auto-generated FastAPI router for {module_name}
            import importlib.util
            from fastapi import APIRouter
            from fastapi import HTTPException
            from pydantic import BaseModel
            from typing import Any

            {router_line}

            {helpers}
        """).strip()

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        return p if p.is_absolute() else (self.workspace_root / p).resolve()
