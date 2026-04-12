"""Factory for creating message listeners based on configuration."""

from typing import Optional, List, Any, Dict

from .base import BaseListener, ListenerType, Platform
from .listeners import NtWorkListener, WebhookListener, UIAutomationListener, OCRListener
from ..utils import get_logger
from ..exceptions import ConfigurationError

logger = get_logger("wechat_listener.factory")


class ListenerFactory:
    """
    Factory class for creating message listeners.
    
    This factory creates the appropriate listener implementation based on
    the configuration, supporting multiple platforms and listener types.
    """
    
    _registry: Dict[ListenerType, type] = {
        ListenerType.NTWORK: NtWorkListener,
        ListenerType.WEBHOOK: WebhookListener,
        ListenerType.UIAUTOMATION: UIAutomationListener,
        ListenerType.OCR: OCRListener,
    }
    
    @classmethod
    def create(
        cls,
        listener_type: ListenerType = ListenerType.UIAUTOMATION,
        platform: Platform = Platform.WEWORK,
        keywords: Optional[List[str]] = None,
        regex_patterns: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> BaseListener:
        """
        Create a listener instance based on the specified type.
        
        Args:
            listener_type: Type of listener to create
            platform: Target chat platform
            keywords: Keywords for task filtering
            regex_patterns: Regex patterns for task filtering
            **kwargs: Additional arguments passed to the listener constructor
            
        Returns:
            Configured listener instance
            
        Raises:
            ConfigurationError: If the listener type is not supported
        """
        listener_class = cls._registry.get(listener_type)
        
        if not listener_class:
            raise ConfigurationError(
                f"Unsupported listener type: {listener_type}. "
                f"Available types: {list(cls._registry.keys())}"
            )
        
        logger.info(f"Creating {listener_type.value} listener for {platform.value}")
        
        return listener_class(
            platform=platform,
            keywords=keywords,
            regex_patterns=regex_patterns,
            **kwargs,
        )
    
    @classmethod
    def create_from_config(cls, config: Dict[str, Any]) -> BaseListener:
        """
        Create a listener instance from a configuration dictionary.
        
        Args:
            config: Configuration dictionary with listener settings
            
        Returns:
            Configured listener instance
            
        Example config:
            {
                "listener_type": "uiautomation",
                "platform": "wework",
                "keywords": ["项目发布", "需求"],
                "regex_patterns": [],
                "ntwork": {
                    "device_id": "",
                    "ip": "127.0.0.1",
                    "port": 5037,
                    "smart_mode": True
                },
                "webhook": {
                    "host": "0.0.0.0",
                    "port": 8080,
                    "token": "",
                    "path": "/webhook/wechat"
                },
                "uiautomation": {
                    "poll_interval": 0.5,
                    "max_history": 100
                }
            }
        """
        listener_type_str = config.get("listener_type", "uiautomation")
        try:
            listener_type = ListenerType(listener_type_str)
        except ValueError:
            raise ConfigurationError(
                f"Invalid listener_type: {listener_type_str}. "
                f"Valid types: {[t.value for t in ListenerType]}"
            )
        
        platform_str = config.get("platform", "wework")
        try:
            platform = Platform(platform_str)
        except ValueError:
            raise ConfigurationError(
                f"Invalid platform: {platform_str}. "
                f"Valid platforms: {[p.value for p in Platform]}"
            )
        
        keywords = config.get("keywords", [])
        regex_patterns = config.get("regex_patterns", [])
        
        type_specific_config = config.get(listener_type_str, {})
        
        return cls.create(
            listener_type=listener_type,
            platform=platform,
            keywords=keywords,
            regex_patterns=regex_patterns,
            **type_specific_config,
        )
    
    @classmethod
    def register_listener(cls, listener_type: ListenerType, listener_class: type) -> None:
        """
        Register a custom listener implementation.
        
        Args:
            listener_type: Type identifier for the listener
            listener_class: Listener class (must inherit from BaseListener)
        """
        if not issubclass(listener_class, BaseListener):
            raise ConfigurationError(
                "Listener class must inherit from BaseListener"
            )
        
        cls._registry[listener_type] = listener_class
        logger.info(f"Registered custom listener: {listener_type.value}")
    
    @classmethod
    def available_types(cls) -> List[str]:
        """Get list of available listener types."""
        return [t.value for t in cls._registry.keys()]
    
    @classmethod
    def available_platforms(cls) -> List[str]:
        """Get list of available platforms."""
        return [p.value for p in Platform]
