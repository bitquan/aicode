"""Data Schema Analyzer for SQL table structures."""

import re
from pathlib import Path
from typing import Any


_TABLE_RE = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z0-9_]+)\s*\((.*?)\);", re.IGNORECASE | re.DOTALL)
_FK_RE = re.compile(r"FOREIGN\s+KEY\s*\((.*?)\)\s*REFERENCES\s+([A-Za-z0-9_]+)\s*\((.*?)\)", re.IGNORECASE)


class DataSchemaAnalyzer:
    """Parse SQL DDL and surface schema insights."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()

    def analyze_sql(self, sql_text: str) -> dict[str, Any]:
        """Analyze SQL DDL text with CREATE TABLE statements."""
        tables: list[dict[str, Any]] = []
        relationships: list[dict[str, str]] = []

        for match in _TABLE_RE.finditer(sql_text):
            table_name = match.group(1)
            body = match.group(2)
            lines = [line.strip().rstrip(",") for line in body.splitlines() if line.strip()]
            columns: list[dict[str, str]] = []
            primary_keys: list[str] = []

            for line in lines:
                upper = line.upper()
                if upper.startswith("PRIMARY KEY"):
                    pk_body = line[line.find("(") + 1:line.rfind(")")]
                    primary_keys.extend([part.strip() for part in pk_body.split(",") if part.strip()])
                    continue

                fk_match = _FK_RE.search(line)
                if fk_match:
                    from_col = fk_match.group(1).strip()
                    to_table = fk_match.group(2).strip()
                    to_col = fk_match.group(3).strip()
                    relationships.append({
                        "from_table": table_name,
                        "from_column": from_col,
                        "to_table": to_table,
                        "to_column": to_col,
                    })
                    continue

                if " " in line and not upper.startswith(("CONSTRAINT", "UNIQUE", "INDEX", "KEY")):
                    col_name, col_type = line.split(" ", 1)
                    columns.append({"name": col_name.strip(), "type": col_type.strip()})

            tables.append(
                {
                    "table": table_name,
                    "columns": columns,
                    "column_count": len(columns),
                    "primary_keys": primary_keys,
                }
            )

        recommendations = self._recommendations(tables, relationships)
        return {
            "table_count": len(tables),
            "tables": tables,
            "relationship_count": len(relationships),
            "relationships": relationships,
            "recommendations": recommendations,
            "status": "OK" if tables else "NO_TABLES",
        }

    def analyze_file(self, file_path: str) -> dict[str, Any]:
        """Analyze SQL file relative to workspace root."""
        path = self.workspace_root / file_path
        if not path.exists():
            return {"error": f"File not found: {file_path}"}
        result = self.analyze_sql(path.read_text(encoding="utf-8"))
        result["file"] = file_path
        return result

    def _recommendations(self, tables: list[dict[str, Any]], relationships: list[dict[str, str]]) -> list[str]:
        recs: list[str] = []
        if tables and all(not table.get("primary_keys") for table in tables):
            recs.append("Add explicit PRIMARY KEY constraints for each table.")
        if relationships:
            recs.append("Create indexes on foreign-key columns to speed joins.")
        large_tables = [table["table"] for table in tables if table.get("column_count", 0) > 20]
        if large_tables:
            recs.append(f"Consider normalizing wide tables: {', '.join(large_tables[:3])}.")
        if not recs:
            recs.append("Schema structure looks consistent; validate constraints and indexing strategy.")
        return recs
