import logging
import logging.handlers

logger = logging.getLogger('IoTGuard')

def setup_logging():
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    
    file_handler = logging.FileHandler('resources/iotguard_log.txt')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)