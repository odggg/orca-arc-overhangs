"""Expose the canonical engine regressions to unittest discovery."""
from pathlib import Path
import runpy
_suite = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tests.py'), run_name='engine_regressions')
Tests = _suite['Tests']
fixture = _suite['fixture']
ring = _suite['ring']
