"""
Centralized logging system for the application
"""
import logging
import os
from datetime import datetime


class AppLogger:
    """Centralized application logger"""
    
    _instance = None
    _logger = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the logger"""
        # Create logs directory
        log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # Setup logger
        self._logger = logging.getLogger("ITM_AutoClicker")
        self._logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        self._logger.handlers.clear()
        
        # Create formatters and handlers
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # File handler
        log_file = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y%m%d')}.log")
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self._logger.addHandler(file_handler)
        
        # Console handler (DEBUG level)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)
    
    @staticmethod
    def get_logger():
        """Get the application logger"""
        instance = AppLogger()
        return instance._logger
    
    @staticmethod
    def debug(message: str):
        """Log debug message"""
        AppLogger.get_logger().debug(message)
    
    @staticmethod
    def info(message: str):
        """Log info message"""
        AppLogger.get_logger().info(message)
    
    @staticmethod
    def warning(message: str):
        """Log warning message"""
        AppLogger.get_logger().warning(message)
    
    @staticmethod
    def error(message: str):
        """Log error message"""
        AppLogger.get_logger().error(message)
    
    @staticmethod
    def critical(message: str):
        """Log critical message"""
        AppLogger.get_logger().critical(message)
