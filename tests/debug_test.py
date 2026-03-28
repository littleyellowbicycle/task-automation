#!/usr/bin/env python
"""Test runner using debugpy."""

import sys
import os
import subprocess
from pathlib import Path

# Find debugpy path
debugpy_path = "c:\Users\10215\.trae-cn\extensions\ms-python.debugpy-2025.18.0-win32-x64\bundled\debugpy\launcher"

if not Path(debugpy_path).exists():
    print(f"Debugpy not found at {debugpy_path}")
    sys.exit(1)

# Run simple test script
test_script = "simple_test.py"

print(f"Running {test_script} using debugpy...")

result = subprocess.run([
    "python", "-m", "debugpy", "--listen", "0.0.0.0:5678", "--wait-for-client", test_script
], capture_output=True, text=True)

print(f"Return code: {result.returncode}")
print(f"Stdout: {result.stdout}")
print(f"Stderr: {result.stderr}")