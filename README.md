# Vantage Telegram Gateway

Custom Telegram bot gateway for Vantage construction project management system.

## Overview

This is a custom implementation that replaces OpenClaw, providing direct control over:
- LLM interactions with vLLM server
- Tool execution via Python scripts
- Backend API integration for enriched context
- Telegram message handling

## Architecture

```
User (Telegram)
    ↓
Custom Gateway (Python)
    ↓
Backend API - Get enriched context
    ↓
vLLM Server (Qwen3-8B) with tools
    ↓
Gateway - Execute tool_calls
    ↓
Return results to vLLM
    ↓
Gateway - Send final response to Telegram
```

## Setup

### 1. Prerequisites

```bash
# Python 3.9+
python3 --version

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Variables

```bash
# Copy example
cp .env.example .env

# Edit .env with your values
nano .env
```

Required:
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token

Optional (with defaults):
- `VANTAGE_API_URL` - Backend API URL (default: http://localhost:8000)
- `VLLM_URL` - vLLM server URL (default: http://10.0.8.2:8003/v1/chat/completions)
- `DEFAULT_PROJECT_SLUG` - Default project (default: demo-project)

### 3. Start Services

```bash
# Terminal 1 - Backend API
cd /Users/tom/Projects/OSAP/Vantage/backend
source .venv/bin/activate
.venv/bin/uvicorn app.main:app --reload

# Terminal 2 - Gateway
cd /Users/tom/Projects/OSAP/vantage-telegram-gateway
source .env  # Load environment variables
python3 gateway.py
```

### 4. Verify Setup

```bash
# Check backend health
curl http://localhost:8000/api/health

# Check vLLM server
curl http://10.0.8.2:8003/v1/models

# Test bot in Telegram
# Send message: "What's due today?"
```

## Usage

### Status Queries

Ask about tasks, deliverables, requirements, or team members:

```
"What is the status of task 20?"
"Show me deliverable 5"
"Get requirement 12"
"Who is team member 3?"
```

Bot will read enriched context and report full details.

### Task Completion

Upload a file and complete a task:

```
1. Upload PDF/DOC file in Telegram
2. Send: "Complete task 4"
```

Bot will:
- Find the uploaded file
- Validate content
- Create document record
- Link to deliverable
- Mark task complete

### RFP Processing

Upload RFP document:

```
1. Upload PDF in Telegram
```

Bot will automatically:
- Process RFP document
- Create project
- Extract topics, requirements, deliverables, tasks
- Report summary

## Tool Execution

The gateway supports these tools:
- `get_tasks` - List tasks with filters
- `get_task` - Get single task details
- `complete_task` - Complete task with file workflow
- `create_task` - Create new task
- `update_task` - Update task fields
- `delete_task` - Delete task
- `process_rfp` - Process RFP document
- `get_project_stats` - Get project statistics
- `delete_project` - Delete project

All tools execute Python scripts from the OpenClaw skills directory.

## Troubleshooting

### Bot not responding

```bash
# Check gateway is running
ps aux | grep gateway.py

# Check TELEGRAM_BOT_TOKEN
echo $TELEGRAM_BOT_TOKEN

# Check vLLM server
curl http://10.0.8.2:8003/v1/models

# Check backend API
curl http://localhost:8000/api/health
```

### Tools not executing

```bash
# Check script paths in config.py
python3 -c "from config import TASK_SCRIPTS_DIR; print(TASK_SCRIPTS_DIR)"

# Test script directly
python3 /path/to/scripts/tasks.py list demo-project

# Check logs
tail -f gateway.log  # or check console output
```

### Context not loading

```bash
# Check backend context endpoint
curl http://localhost:8000/api/projects/demo-project/chat/context

# Verify project slug in DEFAULT_PROJECT_SLUG
echo $DEFAULT_PROJECT_SLUG
```

### File uploads not working

```bash
# Check media inbox directory
ls -la ~/.openclaw/media/inbound/

# Verify file permissions
stat ~/.openclaw/media/inbound/

# Check complete_task.py can find files
python3 /path/to/scripts/complete_task.py 4
```

## Development

### Running Tests

```bash
# Unit tests for tools
python3 -m pytest tests/test_tools.py

# Integration tests for gateway
python3 -m pytest tests/test_gateway.py
```

### Adding New Tools

1. Add tool definition to `tools.py` TOOLS array
2. Add execution handler in `execute_tool()` function
3. Update system prompt in `prompts.py` if needed
4. Test tool execution independently

### Debugging

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
python3 gateway.py
```

View detailed logs:
- vLLM request/response payloads
- Tool execution commands and results
- Message processing flow

## Migration from OpenClaw

See [MIGRATION_GUIDE.md](../Vantage/MIGRATION_GUIDE.md) for complete migration documentation.

Key differences:
- ✅ Direct control over LLM interactions
- ✅ Proper tool execution (no skill system issues)
- ✅ Full transparency with logging
- ✅ Easy to add new tools
- ✅ No framework patches to maintain

What ported over:
- ✅ Backend API (unchanged)
- ✅ All Python scripts (unchanged)
- ✅ Behavior rules (converted to system prompt)
- ✅ Tool definitions (converted to OpenAI format)

## Support

For issues or questions:
- Check troubleshooting section above
- Review logs with DEBUG level
- Verify all services are running
- Test components independently (backend, vLLM, scripts)

## License

Internal BuildRight Construction tool.
