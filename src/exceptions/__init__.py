"""Custom exceptions for WeChat Task Automation System."""


class WeChatAutomationError(Exception):
    """Base exception for all WeChat automation errors."""
    pass


# Configuration errors
class ConfigurationError(WeChatAutomationError):
    """Raised when there's a configuration problem."""
    pass


class ConfigFileNotFoundError(ConfigurationError):
    """Raised when config file is not found."""
    pass


class ConfigValidationError(ConfigurationError):
    """Raised when config validation fails."""
    pass


# WeChat listener errors
class WeChatListenerError(WeChatAutomationError):
    """Base exception for WeChat listener errors."""
    pass


class WeChatConnectionError(WeChatListenerError):
    """Raised when connection to WeChat fails."""
    pass


class WeChatAuthenticationError(WeChatListenerError):
    """Raised when authentication with WeChat fails."""
    pass


class WeChatMessageError(WeChatListenerError):
    """Raised when message processing fails."""
    pass


# LLM errors
class LLMError(WeChatAutomationError):
    """Base exception for LLM-related errors."""
    pass


class LLMConnectionError(LLMError):
    """Raised when connection to LLM service fails."""
    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM request times out."""
    pass


class LLMResponseError(LLMError):
    """Raised when LLM returns an invalid or unexpected response."""
    pass


class LLMRoutingError(LLMError):
    """Raised when LLM routing fails."""
    pass


# OpenCode executor errors
class CodeExecutorError(WeChatAutomationError):
    """Base exception for code executor errors."""
    pass


class OpenCodeConnectionError(CodeExecutorError):
    """Raised when connection to OpenCode fails."""
    pass


class CodeExecutionError(CodeExecutorError):
    """Raised when code execution fails."""
    pass


class CodeTimeoutError(CodeExecutorError):
    """Raised when code execution times out."""
    pass


class SecurityViolationError(CodeExecutorError):
    """Raised when a security check fails (forbidden path, command, etc.)."""
    pass


# Feishu recorder errors
class FeishuError(WeChatAutomationError):
    """Base exception for Feishu-related errors."""
    pass


class FeishuAuthError(FeishuError):
    """Raised when Feishu authentication fails."""
    pass


class FeishuAPIError(FeishuError):
    """Raised when Feishu API returns an error."""
    pass


class FeishuRecordNotFoundError(FeishuError):
    """Raised when a Feishu record is not found."""
    pass


# Workflow errors
class WorkflowError(WeChatAutomationError):
    """Base exception for workflow errors."""
    pass


class WorkflowStateError(WorkflowError):
    """Raised when an invalid state transition is attempted."""
    pass


class ConfirmationTimeoutError(WorkflowError):
    """Raised when user confirmation times out."""
    pass


class TaskFilterError(WorkflowError):
    """Raised when task filtering fails."""
    pass
