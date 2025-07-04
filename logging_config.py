import logging
import sys
from datetime import datetime
import os

def setup_logging():
    """Configure logging for the application"""
    
    # Get log level from environment
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (optional)
    if os.getenv('LOG_FILE'):
        file_handler = logging.FileHandler(os.getenv('LOG_FILE'))
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Suppress some noisy loggers
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    return root_logger

# Initialize logging
logger = setup_logging()

class APILogger:
    """Custom logger for API operations"""
    
    @staticmethod
    def log_request(endpoint: str, params: dict = None):
        """Log API request"""
        logger.info(f"API Request: {endpoint}", extra={
            'params': params,
            'timestamp': datetime.now().isoformat()
        })
    
    @staticmethod
    def log_response(endpoint: str, status_code: int, response_size: int = 0):
        """Log API response"""
        logger.info(f"API Response: {endpoint} - {status_code}", extra={
            'status_code': status_code,
            'response_size': response_size,
            'timestamp': datetime.now().isoformat()
        })
    
    @staticmethod
    def log_error(endpoint: str, error: Exception):
        """Log API error"""
        logger.error(f"API Error: {endpoint} - {str(error)}", extra={
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': datetime.now().isoformat()
        })

class DatabaseLogger:
    """Custom logger for database operations"""
    
    @staticmethod
    def log_query(query_type: str, table: str = None):
        """Log database query"""
        logger.debug(f"DB Query: {query_type}", extra={
            'table': table,
            'timestamp': datetime.now().isoformat()
        })
    
    @staticmethod
    def log_connection_error(error: Exception):
        """Log database connection error"""
        logger.error(f"DB Connection Error: {str(error)}", extra={
            'error_type': type(error).__name__,
            'timestamp': datetime.now().isoformat()
        })

class AILogger:
    """Custom logger for AI operations"""
    
    @staticmethod
    def log_ai_request(operation: str, model: str, tokens: int = 0):
        """Log AI service request"""
        logger.info(f"AI Request: {operation} using {model}", extra={
            'operation': operation,
            'model': model,
            'tokens': tokens,
            'timestamp': datetime.now().isoformat()
        })
    
    @staticmethod
    def log_ai_error(operation: str, error: Exception):
        """Log AI service error"""
        logger.error(f"AI Error: {operation} - {str(error)}", extra={
            'operation': operation,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': datetime.now().isoformat()
        })
