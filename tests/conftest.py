"""
conftest.py
===========
Pytest configuration for the tests/ directory.

Adds the project root to sys.path so that test files can import
top-level modules (e.g. `from main import app`) without needing
to install the package or adjust PYTHONPATH manually.
"""

import sys
import os

# Insert the project root (one level above this file) at the front of sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
