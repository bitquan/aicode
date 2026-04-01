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

    def generate_from_file(self, file_path: str, http_method: str = "POST") -> dict[str, Any]:
        """Emit FastAPI route stubs for all non-private functions in *file_path*."""
        path = self._resolve(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}", "routes": []}

        source = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return {"error": str(exc), "routes": []}

        routes: list[dict] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    routes.append(self._build_route(node, http_method))

        module_name = path.stem
        header = self._build_router_header(module_name)
        return {
            "file": str(path.relative_to(self.workspace_root)),
            "route_count": len(routes),
            "router_header": header,
            "routes": routes,
            "full_code": header + "\n\n" + "\n\n".join(r["code"] for r in routes),
        }

    def generate_from_function(self, func_name: str, params: list[dict],
                                return_type: str = "dict",
                                http_method: str = "POST") -> dict[str, Any]:
        """Generate a single FastAPI route stub from explicit metadata."""
        endpoint = func_name.lower().replace("_", "-")
        method = http_method.upper()

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
        )

        header = (
            "from fastapi import APIRouter\n"
            "from pydantic import BaseModel\n"
            "from typing import Any\n\n"
            "router = APIRouter()\n"
        )
        return {
            "function": func_name,
            "endpoint": f"/{endpoint}",
            "method": method,
            "code": header + "\n" + (model_code + "\n" if model_code else "") + route_func,
        }

    # ── Internals ─────────────────────────────────────────────────────────────

    def _build_route(self, node: ast.FunctionDef | ast.AsyncFunctionDef,
                     http_method: str) -> dict:
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
            params=params,
        )
        return {"name": node.name, "endpoint": endpoint, "method": http_method.upper(), "code": code}

    def _render_route(self, func_name: str, endpoint: str, method: str,
                      model_name: str | None, return_type: str,
                      params: list[dict] | None = None) -> str:
        decorator = f'@router.{method.lower()}("{endpoint}")'
        if model_name:
            sig = f"payload: {model_name}"
        elif params:
            sig = ", ".join(f"{p['name']}: {p['type']}" for p in params)
        else:
            sig = ""

        return textwrap.dedent(f"""\
            {decorator}
            async def {func_name}({sig}) -> {return_type}:
                \"\"\"Auto-generated endpoint for {func_name}.\"\"\"
                # TODO: implement
                raise NotImplementedError("{func_name} not implemented")
        """)

    def _build_router_header(self, module_name: str) -> str:
        return textwrap.dedent(f"""\
            # Auto-generated FastAPI router for {module_name}
            from fastapi import APIRouter
            from pydantic import BaseModel
            from typing import Any

            router = APIRouter(prefix="/{module_name}", tags=["{module_name}"])
        """)

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        return p if p.is_absolute() else (self.workspace_root / p).resolve()
