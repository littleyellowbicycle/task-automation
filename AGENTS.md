# AGENTS.md - Agent Coding Guidelines

## Project Overview

This is a **WeChat Task Automation System** that captures enterprise WeChat group messages, analyzes tasks using LLM, executes code generation via OpenCode, and records results to Feishu (Lark) spreadsheets.

**Tech Stack**: Python 3.10+ | Pydantic | loguru | pytest | NtWork | lark-oapi

**Runtime**: Windows (for WeChat API), Python 3.10+

---

## Build, Lint & Test Commands

### Installation
```bash
pip install -r requirements.txt
```

### Running the Application
```bash
# Normal mode
python main.py

# Test mode with mock messages
python main.py --mode test --mock

# Dry run (no actual code execution)
python main.py --dry-run

# Specify custom config
python main.py --config path/to/config.yaml

# Set log level
python main.py --log-level DEBUG
```

### Running Tests
```bash
# Run all tests with verbose output
pytest tests/ -v

# Run a single test file
pytest tests/test_llm_router/test_router.py -v

# Run a single test function
pytest tests/test_llm_router/test_router.py::TestLLMRouter::test_complexity_assessment -v

# Run with coverage report
pytest tests/ -v --cov=src --cov-report=html

# Run tests matching a pattern
pytest -k "test_router" -v

# Run in watch mode (auto-rerun on changes)
pytest tests/ -v --watch
```

### Code Quality
```bash
# Type checking (if mypy installed)
mypy src/

# Linting (if ruff installed)
ruff check src/
```

---

## Code Style Guidelines

### General Principles
- Follow **PEP 8** with **Black** formatting (max line length: 100)
- Use **type hints** everywhere — no `Any` unless absolutely necessary
- Prefer **explicit** over **implicit**
- Keep functions small and focused (max ~50 lines)

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Modules | `snake_case` | `config_manager.py` |
| Classes | `PascalCase` | `LLMRouter`, `WeChatMessage` |
| Functions/Methods | `snake_case` | `get_provider()`, `_assess_complexity()` |
| Variables | `snake_case` | `default_provider`, `task_message` |
| Constants | `SCREAMING_SNAKE_CASE` | `MAX_RETRIES`, `DEFAULT_TIMEOUT` |
| Private Members | Prefix `_` | `_providers`, `_init_providers()` |
| Enum Values | `PascalCase` (as subclasses) | `MessageType.TEXT` |

### Import Order (ISORT)
```python
# 1. Standard library
import asyncio
import re
from pathlib import Path
from typing import Dict, List, Optional

# 2. Third-party packages
import yaml
from pydantic import ValidationError
from loguru import logger

# 3. Local application imports (relative)
from .providers import LLMProvider
from ..utils import get_logger
from ..exceptions import LLMRoutingError

# 4. Local application imports (absolute - when needed)
from src.config.config_manager import ConfigManager
```

### Type Annotations
```python
# Use typing module for complex types
from typing import Dict, List, Optional, Any, Callable

# Good: Explicit types on function signatures
def get_provider(self, name: Optional[str] = None) -> LLMProvider:
    ...

# Good: Complex type hints
async def chat(self, messages: List[Message], provider: Optional[str] = None, **kwargs) -> LLMResponse:
    ...

# Good: Property returns typed
@property
def available_providers(self) -> List[str]:
    return list(self._providers.keys())

# Avoid: Using Any unless truly necessary
# Bad: def process(data: Any) -> Any:
# Good: def process(data: dict) -> dict:
```

### Data Classes & Models
```python
# Use @dataclass for simple data containers
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"

@dataclass
class WeChatMessage:
    msg_id: str
    msg_type: MessageType
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    raw_data: Optional[Dict[str, Any]] = None
```

### Async/Await
```python
# Use async for I/O-bound operations
async def complete(self, prompt: str, provider: Optional[str] = None) -> LLMResponse:
    # Always handle exceptions in async code
    try:
        return await provider.complete(prompt)
    except Exception as e:
        logger.warning(f"Provider failed: {e}")
        raise

# Entry point uses asyncio.run()
def main():
    args = parse_args()
    asyncio.run(main_async(args))
```

### Error Handling
```python
# Use custom exception hierarchy
class WeChatAutomationError(Exception):
    """Base exception for all system errors."""
    pass

class LLMConnectionError(WeChatAutomationError):
    """Raised when LLM connection fails."""
    pass

# Specific exceptions first, general last
try:
    result = await provider.complete(prompt)
except LLMConnectionError as e:
    logger.error(f"LLM connection failed: {e}")
    raise
except WeChatAutomationError as e:
    logger.error(f"Automation error: {e}")
    raise
except Exception as e:
    logger.exception("Unexpected error")
    raise

# Never swallow exceptions silently
# Bad: except Exception: pass
```

### Logging
```python
# Use loguru via utils module
from src.utils import get_logger

logger = get_logger("module_name")

# Use appropriate log levels
logger.debug("Detailed debug info")
logger.info("Normal operation info")
logger.warning("Something unexpected but handled")
logger.error("Error occurred")
logger.exception("Error with traceback")

# Include context in log messages
# Good: logger.info(f"Task {task_id} completed with status {status}")
# Bad: logger.info("Task completed")
```

### Configuration
```python
# Use Pydantic for config validation
from pydantic import BaseModel, Field

class WeChatConfig(BaseModel):
    device_id: str
    ip: str = "127.0.0.1"
    port: int = Field(default=5037, ge=1, le=65535)

# Config loaded via ConfigManager
config = ConfigManager()
wechat_device = config.wechat.device_id
```

### Testing Guidelines
```python
# Use pytest fixtures (define in tests/conftest.py)
@pytest.fixture
def sample_config():
    return AppConfig(wechat=WeChatConfig(device_id="test"))

# Test class naming: Test<ClassName>
class TestLLMRouter:
    def test_complexity_assessment(self):
        router = LLMRouter()
        result = router._assess_complexity("simple test")
        assert result == "low"

# Use descriptive test names
# Good: test_get_provider_returns_ollama_when_available
# Bad: test_provider()
```

### Security Constraints
- **NEVER** modify `/etc`, `/root`, `/sys`, `/proc`
- **NEVER** execute dangerous system commands
- Use **allowlist** for permitted operations (see `config.yaml`)
- Validate all user inputs
- Never log sensitive data (API keys, passwords)

---

## Project Structure

```
.
├── src/
│   ├── config/           # Configuration management
│   ├── wechat_listener/   # WeChat message capture
│   ├── llm_router/       # LLM provider routing
│   ├── task_analyzer/    # Task analysis
│   ├── code_executor/    # OpenCode execution
│   ├── feishu_recorder/  # Feishu recording
│   ├── decision_manager/ # User confirmation
│   ├── workflow_orchestrator/  # Main workflow
│   ├── exceptions/       # Custom exceptions
│   └── utils/            # Utilities
├── config/
│   └── config.yaml       # Main configuration
├── tests/                # Test suite
└── main.py              # Entry point
```

---

## Key Configuration

Environment variables (see `.env.example`):
- `WECHAT_DEVICE_ID`: WeChat device ID
- `OLLAMA_BASE_URL`: Local LLM server (default: http://localhost:11434)
- `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`: Cloud LLM keys
- `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `FEISHU_TABLE_ID`: Feishu config
- `LOG_LEVEL`: DEBUG, INFO, WARNING, ERROR (default: INFO)

---

## Common Workflows

### Adding a New LLM Provider
1. Create provider class in `src/llm_router/`
2. Inherit from `LLMProvider` abstract base class
3. Implement `complete()`, `chat()`, `health_check()` methods
4. Register in `LLMRouter._init_providers()`

### Adding a New Task Filter
1. Add keyword/regex to `config/config.yaml` under `task_filters`
2. Or modify `src/wechat_listener/parser.py` for custom logic

### Adding New Exception
1. Add to `src/exceptions/__init__.py`
2. Follow hierarchy: `WeChatAutomationError` → category-specific → specific
