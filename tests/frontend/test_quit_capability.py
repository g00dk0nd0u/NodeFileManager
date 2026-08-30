"""Contracts for capability-based application shutdown UI."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class QuitCapabilityTestCase(unittest.TestCase):
    def test_quit_visibility_uses_explicit_health_capability(self) -> None:
        app = (ROOT / "frontend/js/app.js").read_text(encoding="utf-8")
        self.assertIn("if (health.quitEnabled)", app)
        self.assertNotIn("if (health.packaged)", app)


if __name__ == "__main__":
    unittest.main()
