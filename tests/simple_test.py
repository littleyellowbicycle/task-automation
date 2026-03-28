#!/usr/bin/env python
"""Simple test runner for specific test cases."""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Import specific test modules
from tests.test_llm_router.test_router import TestLLMRouter
from tests.test_wechat_listener.test_parser import TestMessageParser
from tests.test_wechat_listener.test_wechat_models import TestWeChatModels
from tests.test_feishu_recorder.test_models import TestFeishuRecord
from tests.unit.test_config_manager import test_config_defaults_without_yaml_and_env

# Run specific test cases
print("Running tests...")

# Test LLM Router
try:
    print("\n=== Testing LLM Router ===")
    router_test = TestLLMRouter()
    router_test.test_create_router_without_config()
    print("✓ test_create_router_without_config passed")
    
    router_test.test_response_object()
    print("✓ test_response_object passed")
    
except Exception as e:
    print(f"✗ LLM Router test failed: {e}")

# Test Config Manager
try:
    print("\n=== Testing Config Manager ===")
    test_config_defaults_without_yaml_and_env()
    print("✓ test_config_defaults_without_yaml_and_env passed")
except Exception as e:
    print(f"✗ Config Manager test failed: {e}")

print("\n=== Test Summary ===")
print("Some tests were executed directly.")
print("For full test suite, please run with pytest in a proper Python environment.")