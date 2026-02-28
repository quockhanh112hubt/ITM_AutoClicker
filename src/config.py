"""
Configuration manager for the application
"""
import json
import os
from typing import Any, Dict
from src.logger import AppLogger
from src.constants import (
    DEFAULT_CLICK_DELAY_MS, DEFAULT_PRIORITY_COOLDOWN_MS, 
    DEFAULT_IMAGE_CONFIDENCE, CONFIG_FILE_PATH
)


class Config:
    """Manage application configuration"""
    
    DEFAULT_CONFIG = {
        "click_delay_ms": DEFAULT_CLICK_DELAY_MS,
        "priority_cooldown_ms": DEFAULT_PRIORITY_COOLDOWN_MS,
        "image_confidence": DEFAULT_IMAGE_CONFIDENCE,
        "auto_save": True,
        "last_script": None
    }
    
    def __init__(self, config_file: str = CONFIG_FILE_PATH) -> None:
        # Convert to absolute path if relative
        if not os.path.isabs(config_file):
            config_file = os.path.join(os.path.dirname(__file__), "..", config_file)
            config_file = os.path.normpath(config_file)
        
        self.config_file = config_file
        self.settings: Dict[str, Any] = self.DEFAULT_CONFIG.copy()
        self.load()
    
    def load(self) -> None:
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.settings.update(loaded)
        except Exception as e:
            AppLogger.error(f"Error loading config: {e}")
            self.settings = self.DEFAULT_CONFIG.copy()
    
    def save(self) -> None:
        """Save configuration to file"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            AppLogger.error(f"Error saving config: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
            
        Raises:
            ValueError: If key is None or empty
        """
        if not key:
            raise ValueError("key cannot be None or empty")
        if not isinstance(key, str):
            raise ValueError(f"key must be a string, got {type(key).__name__}")
        return self.settings.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value
        
        Args:
            key: Configuration key
            value: Value to set
            
        Raises:
            ValueError: If key is None or empty
        """
        if not key:
            raise ValueError("key cannot be None or empty")
        if not isinstance(key, str):
            raise ValueError(f"key must be a string, got {type(key).__name__}")
        self.settings[key] = value
        self.save()
