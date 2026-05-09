# config.py
from typing import Dict, List
from pathlib import Path

# Get work path 
WORK_DIR = Path.cwd()

# Global variables should be typed and have clear names
last_message_dict: Dict[int, List[int]] = {}

