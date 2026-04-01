"""Tests for DataSchemaAnalyzer."""

from src.tools.data_schema_analyzer import DataSchemaAnalyzer


SQL = """
CREATE TABLE users (
  id INTEGER,
  email TEXT,
  PRIMARY KEY (id)
);

CREATE TABLE orders (
  id INTEGER,
  user_id INTEGER,
  amount NUMERIC,
  PRIMARY KEY (id),
  FOREIGN KEY (user_id) REFERENCES users(id)
);
"""


def test_analyze_sql_tables_and_relationships(tmp_path):
    tool = DataSchemaAnalyzer(str(tmp_path))
    result = tool.analyze_sql(SQL)
    assert result["status"] == "OK"
    assert result["table_count"] == 2
    assert result["relationship_count"] == 1


def test_recommendations_present(tmp_path):
    tool = DataSchemaAnalyzer(str(tmp_path))
    result = tool.analyze_sql(SQL)
    assert len(result["recommendations"]) >= 1


def test_analyze_file_missing(tmp_path):
    tool = DataSchemaAnalyzer(str(tmp_path))
    result = tool.analyze_file("schema.sql")
    assert "error" in result


def test_no_tables_status(tmp_path):
    tool = DataSchemaAnalyzer(str(tmp_path))
    result = tool.analyze_sql("-- no ddl")
    assert result["status"] == "NO_TABLES"
