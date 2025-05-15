import os
import logging
from datetime import datetime

def setup_logging(logs_dir, logs_sub_dir, module_name):
    """
    Set up logging configuration for a module.
    
    Parameters:
    -----------
    logs_dir : str
        Name of the directory where logs are stored
    logs_sub_dir : str
        Name of the sub-directory where logs are stored
    module_name : str
        Name of the module (used for the logger name and log file)
        
    Returns:
    --------
    logging.Logger
        Configured logger
    """
    # Create logs directory if it doesn't exist
    log_path = os.path.join(logs_dir, logs_sub_dir)
    os.makedirs(log_path, exist_ok=True)
    
    logger = logging.getLogger(module_name)
    
    if not logger.handlers:
        current_time = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_filename = f"{module_name}_{current_time}.log"
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        file_handler = logging.FileHandler(os.path.join(log_path, log_filename))
        file_handler.setFormatter(formatter)
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        logger.setLevel(logging.INFO)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        logger.propagate = False
    
    return logger