"""
Configuration manager for the application
"""
import json
import os
from typing import Any, Dict


class Config:
    """Manage application configuration"""
    
    DEFAULT_CONFIG = {
        "click_delay_ms": 100,
        "image_confidence": 0.8,
        "auto_save": True,
        "last_script": None
    }
    
    def __init__(self, config_file: str = "config/settings.json"):
        self.config_file = config_file
        self.settings: Dict[str, Any] = self.DEFAULT_CONFIG.copy()
        self.load()
    
    def load(self):
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.settings.update(loaded)
        except Exception as e:
            print(f"Error loading config: {e}")
            self.settings = self.DEFAULT_CONFIG.copy()
    
    def save(self):
        """Save configuration to file"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        return self.settings.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set a configuration value"""
        self.settings[key] = value
        self.save()
