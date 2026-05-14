# config.py
import os
from typing import Dict, List
from pathlib import Path

# Get work path 
WORK_DIR = Path.cwd()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Global variables should be typed and have clear names
last_message_dict: Dict[int, List[int]] = {}

