"""Configuration for Vantage Telegram Gateway"""
import os
from pathlib import Path

# API Configuration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
VLLM_URL = os.environ.get("VLLM_URL", "http://10.0.8.2:8003/v1/chat/completions")
BACKEND_API = os.environ.get("VANTAGE_API_URL", "http://localhost:8000") + "/api"

# Paths
MEDIA_INBOX = Path.home() / ".openclaw" / "media" / "inbound"
TASK_SCRIPTS_DIR = Path(os.environ.get(
    "TASK_SCRIPTS_DIR",
    "/Users/tom/Projects/OSAP/Vantage/OpenClaw/skills/task-tracker/scripts"
))
RFP_SCRIPTS_DIR = Path(os.environ.get(
    "RFP_SCRIPTS_DIR",
    "/Users/tom/Projects/OSAP/Vantage/OpenClaw/skills/rfp-analyzer/scripts"
))
PROJECT_SCRIPTS_DIR = Path(os.environ.get(
    "PROJECT_SCRIPTS_DIR",
    "/Users/tom/Projects/OSAP/Vantage/OpenClaw/scripts"
))

# Model Configuration
MODEL_NAME = "Qwen/Qwen3-8B"
MODEL_TEMPERATURE = 0.7
MODEL_MAX_TOKENS = 2000

# Default project (would be per-user in production)
DEFAULT_PROJECT = os.environ.get("DEFAULT_PROJECT_SLUG", "demo-project")

# Logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# Validate required configuration
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

# Ensure directories exist
MEDIA_INBOX.mkdir(parents=True, exist_ok=True)
