"""
Regression test — Audit Finding: Bottom Imports (Code Quality Smell).

Before fix:
    scheduler/queue.py imported Event and time at the very bottom of the file
    (lines 168-169) to circumvent a presumed circular dependency.

After fix:
    Event and time are imported at the top of scheduler/queue.py according to PEP 8.
    There are no bottom imports, and the module imports cleanly without circular dependencies.

Bug: Architecture Audit Finding #9 (Bottom Imports)
"""

import ast
from pathlib import Path
import unittest


class TestNoBottomImportsInQueue(unittest.TestCase):
    """Verify that scheduler/queue.py does not have imports at the bottom of the module."""

    def test_imports_are_at_top_of_file(self):
        queue_path = Path(__file__).resolve().parent.parent / "scheduler" / "queue.py"
        source = queue_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        # Find the line of the class definition
        class_line = None
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == "DispatchQueue":
                class_line = node.lineno
                break

        self.assertIsNotNone(class_line, "DispatchQueue class definition must be found.")

        # Ensure no Import or ImportFrom statements occur after the DispatchQueue class definition
        bottom_imports = []
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)) and node.lineno > class_line:
                bottom_imports.append((node.lineno, ast.unparse(node)))

        self.assertEqual(
            bottom_imports,
            [],
            f"No imports should appear after class definition in scheduler/queue.py. Found: {bottom_imports}",
        )

    def test_queue_imports_cleanly(self):
        import scheduler.queue as q
        self.assertTrue(hasattr(q, "DispatchQueue"))
        self.assertTrue(hasattr(q, "Event"))


if __name__ == "__main__":
    unittest.main()
