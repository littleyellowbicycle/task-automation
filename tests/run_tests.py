#!/usr/bin/env python
"""Simple test runner using unittest."""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Import unittest
import unittest

# Discover and run tests
def run_tests():
    """Discover and run all tests in the tests directory."""
    test_dir = Path(__file__).parent / "tests"
    
    if not test_dir.exists():
        print(f"Error: Tests directory not found at {test_dir}")
        return 1
    
    print(f"Discovering tests in {test_dir}...")
    
    # Create test suite
    test_suite = unittest.defaultTestLoader.discover(
        start_dir=str(test_dir),
        pattern="test_*.py",
        top_level_dir=str(Path(__file__).parent)
    )
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    sys.exit(run_tests())