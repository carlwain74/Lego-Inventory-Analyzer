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
# Stub out set_handler before any test file imports app.py.
# SetHandler is a class whose __init__ accepts the same args previously passed
# to sheet_handler. Tests control return values via:
#   _sh_stub.set_handler.return_value = {...}
# test_config is an instance method on SetHandler.
# ---------------------------------------------------------------------------
_sh_instance = MagicMock()
_sh_instance.set_handler.return_value = {}

_set_handler_stub = MagicMock()
_set_handler_stub.SetHandler.return_value = _sh_instance
_sh_instance.test_config = MagicMock(return_value=True)

sys.modules['set_handler']     = _set_handler_stub
sys.modules['generate_sheets'] = MagicMock()  # no longer used by app.py but may be imported elsewhere