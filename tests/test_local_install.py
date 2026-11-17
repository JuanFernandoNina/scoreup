"""Protecciones de la distribución local, sin datos ni servicios externos."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LocalDistributionTests(unittest.TestCase):
    def test_docker_includes_both_storage_adapters(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        for filename in ("store.py", "pg_store.py"):
            self.assertIn(filename, dockerfile)
            self.assertIn("!" + filename, ignore)

    def test_templates_do_not_load_remote_assets(self):
        for path in (ROOT / "templates").rglob("*.html"):
            text = path.read_text(encoding="utf-8")
            with self.subTest(template=path.relative_to(ROOT)):
                self.assertIsNone(re.search(
                    r'<(?:script|img|link)\b[^>]*\b(?:src|href)\s*=\s*[\"\'](?:https?:)?//',
                    text, re.IGNORECASE,
                ))

    def test_base_uses_bundled_compiled_styles(self):
        template = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertIn("app-utilities.css", template)
        css = (ROOT / "static" / "app-utilities.css").read_text(encoding="utf-8")
        self.assertIn(".bg-slate-50", css)
        self.assertIn(".min-h-screen", css)
        self.assertNotIn("@import", css)

    def test_local_requirements_do_not_require_cloud_or_model_downloads(self):
        requirements = (ROOT / "requirements-local.txt").read_text(encoding="utf-8")
        self.assertIn("-r requirements.txt", requirements)
        self.assertIn("opencv-python-headless", requirements)
        for dependency in ("psycopg", "torch", "qreader"):
            self.assertNotIn(dependency, requirements.lower())


if __name__ == "__main__":
    unittest.main()
