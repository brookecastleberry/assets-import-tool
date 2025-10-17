import logging
import os
from datetime import datetime

def setup_logging(name: str = 'create_targets') -> logging.Logger:
    """
    Setup logging to file using SNYK_LOG_PATH environment variable
    """
    log_path = os.environ.get('SNYK_LOG_PATH')
    if not log_path:
        print("Warning: SNYK_LOG_PATH environment variable not set. Logs will only be displayed on console.")
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            console_handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        return logger
    os.makedirs(log_path, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_path, f'{name}_{timestamp}.log')
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        file_handler = logging.FileHandler(log_file)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    print(f"📝 Logging to: {log_file}")
    return logger
