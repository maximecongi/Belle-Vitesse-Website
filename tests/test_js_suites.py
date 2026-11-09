"""
Exécute les suites jsdom de tests/js (éditeur des rapports d'équipe, module de la fiche projet).
Ignoré si Node.js ou les dépendances (cd tests/js && npm install) ne sont pas disponibles.
"""
import shutil
import subprocess
import unittest
from pathlib import Path

JS_DIR = Path(__file__).parent / "js"


@unittest.skipUnless(shutil.which("node"), "Node.js non installé")
@unittest.skipUnless((JS_DIR / "node_modules" / "jsdom").exists(), "jsdom absent : cd tests/js && npm install")
class JsSuitesTest(unittest.TestCase):
    def test_jsdom_suites(self):
        result = subprocess.run(
            ["node", str(JS_DIR / "run.js")], capture_output=True, text=True, timeout=180
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
