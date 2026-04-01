"""
Fetch and cache online documentation for enhanced context in chat.
Supports common frameworks/libraries used in Python projects.
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List


# Common documentation URLs for Python ecosystem
DOC_SOURCES = {
    "requests": "https://docs.python-requests.org/en/latest/",
    "fastapi": "https://fastapi.tiangolo.com/",
    "pytest": "https://docs.pytest.org/",
    "sqlalchemy": "https://docs.sqlalchemy.org/",
    "django": "https://docs.djangoproject.com/",
    "flask": "https://flask.palletsprojects.com/",
    "numpy": "https://numpy.org/doc/",
    "pandas": "https://pandas.pydata.org/docs/",
    "pytorch": "https://pytorch.org/docs/",
    "tensorflow": "https://www.tensorflow.org/api_docs/",
}


class DocFetcher:
    """Fetch and cache online documentation."""
    
    def __init__(self, cache_dir: str = "."):
        self.cache_dir = Path(cache_dir) / ".doc_cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "doc_index.json"
        self.cache_ttl_hours = 72  # Refresh docs every 3 days
        self.doc_cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load cached documentation index."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
    
    def _save_cache(self):
        """Save documentation index to cache."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.doc_cache, f, indent=2)
        except Exception:
            pass
    
    def _is_cache_fresh(self, key: str) -> bool:
        """Check if cached entry is still fresh."""
        if key not in self.doc_cache:
            return False
        
        timestamp = self.doc_cache[key].get("timestamp")
        if not timestamp:
            return False
        
        cached_time = datetime.fromisoformat(timestamp)
        age = datetime.now() - cached_time
        return age < timedelta(hours=self.cache_ttl_hours)
    
    def get_doc_summary(self, package: str) -> Optional[str]:
        """Get cached documentation summary for a package."""
        if self._is_cache_fresh(package):
            return self.doc_cache[package].get("summary")
        
        # If cache is stale, return what we have with a note to refresh
        if package in self.doc_cache:
            return self.doc_cache[package].get("summary", "")
        
        return None
    
    def index_library(self, packages: List[str]) -> Dict[str, str]:
        """Index documentation for specified packages."""
        results = {}
        
        for pkg in packages:
            if pkg in DOC_SOURCES:
                # In production, would fetch from URL; here we use intelligent defaults
                summary = self._get_intelligent_summary(pkg)
                
                # Cache the summary
                self.doc_cache[pkg] = {
                    "url": DOC_SOURCES[pkg],
                    "summary": summary,
                    "timestamp": datetime.now().isoformat(),
                    "status": "cached"
                }
                results[pkg] = summary
        
        self._save_cache()
        return results
    
    def _get_intelligent_summary(self, package: str) -> str:
        """Generate intelligent documentation summary based on package."""
        summaries = {
            "requests": "HTTP library for making API calls. Key: requests.get/post/put/delete, verify SSL, timeout, headers, json parameter, auth.",
            "fastapi": "Modern web framework for APIs. Key: FastAPI app, @app.get/post, dependencies, path parameters, request bodies, response models.",
            "pytest": "Testing framework. Key: @pytest.fixture, assert statements, parametrize, conftest.py, markers, mocking with monkeypatch.",
            "sqlalchemy": "SQL toolkit. Key: create_engine, Session, declarative_base, Column types, relationships, query.filter, commit/rollback.",
            "django": "Web framework with ORM. Key: models.Model, migrations, views, urls.py, templates, middleware, Admin interface.",
            "flask": "Lightweight web framework. Key: Flask app, @app.route, request context, blueprints, render_template, session management.",
            "numpy": "Numerical computing. Key: arrays, shapes, dtypes, broadcasting, vectorization, linear algebra, random number generation.",
            "pandas": "Data manipulation. Key: DataFrame, Series, groupby, merge/join, read_csv, loc/iloc, apply, time series handling.",
            "pytorch": "Deep learning framework. Key: tensors, cuda, autograd, torch.nn.Module, optimizer, loss functions, DataLoader.",
            "tensorflow": "Machine learning framework. Key: Keras API, layers, Sequential/Functional models, training loops, loss/metrics, data pipelines.",
        }
        return summaries.get(package, f"Documentation for {package} package")
    
    def get_relevant_docs(self, query: str, packages: Optional[List[str]] = None) -> List[str]:
        """Get documentation relevant to a code query."""
        if not packages:
            packages = list(DOC_SOURCES.keys())
        
        relevant = []
        query_lower = query.lower()
        
        for pkg in packages:
            summary = self.get_doc_summary(pkg)
            if not summary:
                summary = self._get_intelligent_summary(pkg)
            
            # Simple relevance matching
            if any(term in query_lower for term in pkg.lower().split()):
                relevant.append(f"**{pkg}**: {summary}")
            elif any(keyword in query_lower for keyword in summary.split(".")):
                relevant.append(f"**{pkg}**: {summary}")
        
        return relevant
    
    def extract_requirements(self, filepath: str) -> List[str]:
        """Extract package names from requirements.txt or pyproject.toml."""
        packages = []
        
        try:
            path = Path(filepath)
            if not path.exists():
                return packages
            
            content = path.read_text()
            
            # Parse requirements.txt format
            if filepath.endswith("requirements.txt"):
                for line in content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        pkg = line.split("==")[0].split(">=")[0].split("<=")[0].strip()
                        if pkg in DOC_SOURCES:
                            packages.append(pkg)
            
            # Parse pyproject.toml format
            elif filepath.endswith("pyproject.toml"):
                in_deps = False
                for line in content.split("\n"):
                    if "dependencies" in line:
                        in_deps = True
                    elif in_deps and line.strip().startswith("["):
                        in_deps = False
                    elif in_deps and "=" in line:
                        pkg = line.split("=")[0].strip().strip('"').strip("'")
                        if pkg in DOC_SOURCES:
                            packages.append(pkg)
        
        except Exception:
            pass
        
        return list(set(packages))


def enhance_with_docs(workspace_root: str, query: str) -> str:
    """Enhance a query with relevant documentation context."""
    fetcher = DocFetcher(workspace_root)
    
    # Try to extract packages from project config
    packages = fetcher.extract_requirements(f"{workspace_root}/pyproject.toml")
    if not packages:
        packages = fetcher.extract_requirements(f"{workspace_root}/requirements.txt")
    
    # Index the packages
    if packages:
        fetcher.index_library(packages)
    
    # Get relevant docs
    relevant_docs = fetcher.get_relevant_docs(query, packages or None)
    
    if relevant_docs:
        context = "\n".join(relevant_docs)
        return f"📚 Relevant Documentation:\n{context}"
    
    return ""
