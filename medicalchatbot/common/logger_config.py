import logging
import json
from datetime import datetime
import os

# Ensure the data directory exists
os.makedirs("data", exist_ok=True)

def setup_logger(name, log_file):
    """Helper to create a specific logger instance."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Avoid adding multiple handlers if the logger is re-initialized
    if not logger.handlers:
        handler = logging.FileHandler(log_file)
        # Optional: Add a formatter for better readability
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

# Initialize both loggers
chat_logger = setup_logger("MedicalAudit", "data/medical_chatbot_audit.log")
dd_logger = setup_logger("DDAudit", "data/dd_audit.log")

def log_clinical_interaction(mode, module_tag, session_id, client_ip, query, response):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "origin": module_tag,
        "mode": mode,
        "client_ip": client_ip,
        "session_id": session_id,
        "query": query,
        "response_len": len(response),
        "response": response
    }
    
    log_json = json.dumps(log_entry)
    
    # ROUTING LOGIC: Choose the logger based on the mode
    if mode.lower() == "dd":
        dd_logger.info(log_json)
        target = "DD Audit"
    else:
        chat_logger.info(log_json)
        target = "Medical Chat Audit"

    print(f"📝 {target} Logged: {module_tag} | Session: {session_id}")