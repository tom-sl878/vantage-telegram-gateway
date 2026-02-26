"""Configuration for Vantage Telegram Gateway"""
import os
from pathlib import Path

# API Configuration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
BACKEND_API = os.environ.get("VANTAGE_API_URL", "http://localhost:8000") + "/api"

# LLM Provider: "vllm" or "claude"
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "vllm")

# vLLM Configuration
VLLM_URL = os.environ.get("VLLM_URL", "http://10.0.8.2:8003/v1/chat/completions")
VLLM_MODEL = os.environ.get("VLLM_MODEL", "Qwen/Qwen3-8B")

# Claude Configuration
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

# Paths
MEDIA_INBOX = Path(os.environ.get(
    "MEDIA_INBOX",
    "/Users/tom/Projects/OSAP/Vantage/backend/data/uploads"
))
TASK_SCRIPTS_DIR = Path(os.environ.get(
    "TASK_SCRIPTS_DIR",
    "/Users/tom/Projects/OSAP/Vantage/scripts/tasks"
))
RFP_SCRIPTS_DIR = Path(os.environ.get(
    "RFP_SCRIPTS_DIR",
    "/Users/tom/Projects/OSAP/Vantage/scripts/rfp"
))
PROJECT_SCRIPTS_DIR = Path(os.environ.get(
    "PROJECT_SCRIPTS_DIR",
    "/Users/tom/Projects/OSAP/Vantage/scripts/projects"
))
REPORT_SCRIPTS_DIR = Path(os.environ.get(
    "REPORT_SCRIPTS_DIR",
    "/Users/tom/Projects/OSAP/Vantage/scripts/reports"
))

# Shared Model Configuration
MODEL_TEMPERATURE = float(os.environ.get("MODEL_TEMPERATURE", "0.7"))
MODEL_MAX_TOKENS = int(os.environ.get("MODEL_MAX_TOKENS", "2000"))

# Intent classifier — cheap/fast model for routing (defaults to main model)
CLASSIFIER_MODEL = os.environ.get("CLASSIFIER_MODEL", "")  # empty = use main model
CLASSIFIER_MAX_TOKENS = int(os.environ.get("CLASSIFIER_MAX_TOKENS", "20"))

# Bot identity (for deep links: t.me/BOT_USERNAME?start=CODE)
BOT_USERNAME = os.environ.get("BOT_USERNAME", "VantageBot")

# Default project (would be per-user in production)
DEFAULT_PROJECT = os.environ.get("DEFAULT_PROJECT_SLUG", "demo-project")

# Mini App URL (set by cloudflared tunnel or manually)
WEBAPP_URL = os.environ.get("WEBAPP_URL", "")

# Internal service token (shared secret with backend for actor identity)
INTERNAL_TOKEN = os.environ.get("VANTAGE_INTERNAL_TOKEN", "")

# Logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# Validate required configuration
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
if LLM_PROVIDER == "claude" and not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=claude")
if LLM_PROVIDER not in ("vllm", "claude"):
    raise ValueError(f"LLM_PROVIDER must be 'vllm' or 'claude', got '{LLM_PROVIDER}'")

# Ensure directories exist
MEDIA_INBOX.mkdir(parents=True, exist_ok=True)
