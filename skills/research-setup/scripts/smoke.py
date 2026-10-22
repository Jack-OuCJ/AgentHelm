#!/usr/bin/env python3
"""Run the workspace-only offline integration suite."""
from pathlib import Path
import os
import subprocess
import sys
root = Path(__file__).resolve().parents[3]
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
raise SystemExit(subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(root / 'tests'), '-v'], cwd=root, env=env).returncode)
