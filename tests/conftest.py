"""
conftest.py — shared pytest configuration for the Lego Inventory test suite.

Placed in the project root so pytest discovers tests/ automatically.
"""

import sys
import os
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so `import app` works regardless of
# where pytest is invoked from.
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(__file__)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Stub out generate_sheets before any test file imports app.py.
# This prevents the real Bricklink API client from being initialised during
# testing and avoids needing valid credentials in CI.
#
# Individual tests can override _gs_stub.sheet_handler or _gs_stub.test_config
# to return whatever values they need.
# ---------------------------------------------------------------------------
_gs_stub = MagicMock()
_gs_stub.sheet_handler = MagicMock(return_value=None)
_gs_stub.test_config   = MagicMock(return_value=True)
sys.modules['generate_sheets'] = _gs_stub