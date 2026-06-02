import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Mock weasyprint before importing app
from unittest.mock import MagicMock
mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

suite = unittest.defaultTestLoader.discover('tests')
with open('test_results.txt', 'w') as f:
    runner = unittest.TextTestRunner(stream=f, verbosity=2)
    result = runner.run(suite)
    
    f.write("\n=== DETAILED ERRORS ===\n")
    for err in result.errors:
        f.write(f"\nERROR in {err[0]}:\n{err[1]}\n")
    
    f.write("\n=== DETAILED FAILURES ===\n")
    for fail in result.failures:
        f.write(f"\nFAIL in {fail[0]}:\n{fail[1]}\n")
