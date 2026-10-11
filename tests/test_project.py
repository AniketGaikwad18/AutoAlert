import unittest
import subprocess
import sys

class TestProjectSetup(unittest.TestCase):
    def test_imports(self):
        """Verify that core packages can be imported."""
        try:
            import src
            import src.core
            import src.core.main
        except ImportError:
            self.fail("Failed to import src packages")

    def test_main_execution(self):
        """Verify that the main entry point runs successfully."""
        result = subprocess.run(
            [sys.executable, "-m", "src.core.main"],
            capture_output=True,
            text=True,
            cwd="."
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("AutoAlert", result.stdout)

if __name__ == '__main__':
    unittest.main()
