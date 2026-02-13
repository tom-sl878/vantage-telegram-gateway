# Vantage Telegram Gateway - Lessons Learned

## Architecture Decisions

### Why Custom Gateway Over OpenClaw
**Date**: 2026-02-13

**Problem**: OpenClaw framework had fundamental issues:
- Skill system didn't properly pass tool definitions to LLM
- Qwen3-8B model leaked reasoning despite extensive SOUL.md configuration
- Bot described actions but didn't execute tool calls
- No transparency into what tools LLM actually received
- Patches required (reasoning leak filter, isReasoningTagProvider) that break on updates

**Solution**: Built custom Python gateway with:
- Direct vLLM API control using OpenAI-compatible format
- Explicit tool definitions in OpenAI JSON format
- Full logging and debugging capabilities
- No framework abstractions hiding issues
- Easy to add/modify tools without framework limitations

**Key Insight**: **Framework choice matters more than configuration.** If the framework doesn't support your use case properly, build custom. The custom gateway took less time to build and debug than trying to fix OpenClaw issues.

---

## Configuration Issues & Solutions

### 1. Script Path Discovery (2026-02-13)

**Problem**: `get_projects` tool failed with "file not found" error.

**Root Cause**: Assumed `projects.py` was in `/OpenClaw/scripts/` but it's actually in `/OpenClaw/skills/project-manager/scripts/`.

**Solution**:
```bash
# Find scripts first
find /Users/tom/Projects/OSAP/Vantage -name "projects.py" -type f

# Update config.py and .env
PROJECT_SCRIPTS_DIR=/Users/tom/Projects/OSAP/Vantage/OpenClaw/skills/project-manager/scripts
```

**Lesson**: **Always verify script paths exist before configuring them.** Don't assume directory structure - check it.

### 2. Multiple Bot Instances Conflict (2026-02-13)

**Problem**: `telegram.error.Conflict: terminated by other getUpdates request`

**Root Cause**: Multiple processes trying to use same bot token:
- Old OpenClaw process still running
- Multiple gateway.py processes from repeated restarts
- Telegram allows only ONE active connection per bot token

**Solution**:
```bash
# Kill ALL instances
ps aux | grep -E "gateway|openclaw" | grep -v grep
kill <all PIDs>

# Disable OpenClaw auto-restart
launchctl unload ~/Library/LaunchAgents/ai.openclaw.gateway.plist

# Start single gateway instance
./start.sh > /tmp/gateway.log 2>&1 &
```

**Lesson**: **Only one bot instance can run at a time.** Before starting new gateway, ensure old instances (including OpenClaw) are fully stopped.

### 3. Environment Variables Not Loading (2026-02-13)

**Problem**: Gateway failed with "TELEGRAM_BOT_TOKEN environment variable is required" when run in background.

**Root Cause**: Background processes don't inherit shell environment variables from `.env` file.

**Solution**: Created `start.sh` script:
```bash
#!/bin/bash
set -a          # auto-export all variables
source .env     # load .env file
set +a
source venv/bin/activate
python3 gateway.py
```

**Lesson**: **Background processes need explicit environment loading.** Use `set -a` before sourcing `.env` to export all variables.

### 4. Bot Token Validation (2026-02-13)

**Problem**: Old bot token from OpenClaw config was invalid (401 Unauthorized).

**Root Cause**: Token had been revoked or expired.

**Solution**:
```bash
# Test token before using
curl -s "https://api.telegram.org/bot<TOKEN>/getMe"

# If invalid, create new bot with @BotFather in Telegram
# Update .env with new token
```

**Lesson**: **Always validate bot token before deployment.** A simple curl test saves debugging time.

---

## System Prompt Design

### Behavior Rules That Work

**1. <think> Tags for Hidden Reasoning**
```
ALL internal reasoning MUST be inside <think>...</think> tags.
Format EVERY reply as: <think>your reasoning</think> then your visible reply.
```
✅ Works: Gateway strips think tags in `strip_think_tags()` function
✅ Result: Clean user-facing responses

**2. Action Over Questions (With Exceptions)**
```
1. **Action over questions** - When user sends document or request, DO IT automatically
4. **Clarifying questions are OK** - If genuinely uncertain between similar weighted options, ask the user.
```
✅ Works: Bot takes action for clear requests but asks when genuinely ambiguous
✅ Result: Good UX - efficient but not presumptuous

**3. Project Selection Logic**
```
When user asks "show me my tasks":
1. Call get_projects tool to list available projects
2. If only one project exists: use it automatically and show tasks
3. If multiple projects: list them and ask "Which project?"
4. If no projects: tell user to upload an RFP document
```
✅ Works: Clear decision tree for bot to follow
✅ Result: Bot handles project context intelligently

### What Doesn't Work

❌ **"NEVER" statements without enforcement**: Telling bot "NEVER do X" doesn't work if model isn't designed for instruction following. Need technical controls (like `strip_think_tags()` function).

❌ **Overly strict output rules**: Saying "1-3 SHORT sentences only" conflicts with "report FULL details for status queries". Be specific about exceptions.

❌ **Assuming tool execution**: Just because tools are defined doesn't mean model will call them. Need model that supports function calling properly.

---

## Tool Execution

### Tool Definition Format

**OpenAI-Compatible JSON Format**:
```python
{
    "type": "function",
    "function": {
        "name": "get_tasks",
        "description": "List tasks for a project, optionally filtered by urgency",
        "parameters": {
            "type": "object",
            "properties": {
                "project_slug": {
                    "type": "string",
                    "description": "Project identifier slug"
                },
                "filter": {
                    "type": "string",
                    "enum": ["due_today", "due_this_week", "overdue", "upcoming", "completed", "all"],
                    "description": "Filter tasks by urgency"
                }
            },
            "required": ["project_slug"]
        }
    }
}
```

**Key Elements**:
- Clear description of what tool does
- Well-defined parameter types
- Enums for constrained choices
- Explicit required fields
- Descriptions for each parameter

### Tool Execution Pattern

```python
# 1. User sends message
user_message = update.message.text

# 2. Get enriched context from backend
enriched_context = await get_enriched_context(project_slug)

# 3. Call vLLM with tools
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "system", "content": f"PROJECT CONTEXT:\n{enriched_context}"},
    {"role": "user", "content": user_message}
]
response = await call_vllm(messages, TOOLS)

# 4. If LLM returns tool_calls, execute them
if message.get("tool_calls"):
    for tool_call in message["tool_calls"]:
        tool_result = execute_tool(tool_name, arguments)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "name": tool_name,
            "content": json.dumps(tool_result)
        })

    # 5. Call vLLM again with tool results
    final_response = await call_vllm(messages, TOOLS)
```

**Lesson**: **Keep tool execution simple and explicit.** Log everything (tool name, arguments, results) for debugging.

---

## Debugging & Monitoring

### DEBUG Logging Configuration

Set `LOG_LEVEL=DEBUG` in `.env` to see:
- All incoming Telegram messages with full text
- vLLM requests with messages + tools payload
- vLLM responses with tool_calls and content
- Tool execution commands and results
- Backend API calls for enriched context
- Final responses sent to user

**Example Log Output**:
```
INFO - Received message from 12345: Show me my tasks
DEBUG - Calling vLLM with 3 messages and 10 tools
INFO - Executing tool: get_projects with args: {}
INFO - Tool result: [{"id": 1, "name": "Erwin Center..."}]
DEBUG - Calling vLLM again with tool results
INFO - Executing tool: get_tasks with args: {"project_slug": "erwin-center-park-pool-bathhouse"}
INFO - Sent response: Here are your tasks...
```

### Running Gateway for Development

**Background (Production)**:
```bash
./start.sh > /tmp/gateway.log 2>&1 &
tail -f /tmp/gateway.log
```

**Foreground (Development)**:
```bash
./start-debug.sh
# See all logs in real-time in your terminal
```

**Lesson**: **Always run in foreground during development.** Immediate feedback is invaluable. Only run in background for production.

---

## Model Limitations

### Qwen3-8B Instruction Following

**Issue**: Qwen3-8B is "benchmark-oriented rather than instruction-focused" (per HuggingFace community).

**Observed Behaviors**:
- Leaks reasoning despite `<think>` tag instructions
- Describes actions but doesn't execute tool calls consistently
- Verbose reasoning patterns ("Okay,", "Wait,", "But,")

**Mitigation**:
1. Technical controls (strip_think_tags function) not just prompting
2. Clear decision trees in system prompt
3. Enriched context reduces need for tool calls
4. Plan to upgrade to QwQ-32B when available

**Lesson**: **Model choice matters more than prompt engineering.** Check model capabilities before extensive configuration. For production, use models designed for tool use (QwQ, Claude, GPT-4).

---

## Backend Integration

### Enriched Context Strategy

**Key Insight**: Backend's `/projects/{slug}/chat/context` endpoint provides ALL entity data via `_build_project_context()` function (backend/app/routers/chat.py:584-811).

**Context Format**:
```
Tasks:
T{id}: "{title}" ({status}, {priority}, {assignee}, conf={confidence})[{flags}]

Deliverables:
D{id}: "{title}" ({status}, format: {format}, conf={confidence})[{flags}]
  Evidence for: R{req_id} "{req_title}" ({relationship})

Requirements:
R{id}: "{title}" ({type}, {status}) — {link_info}

Team Members:
ID {id}: {name}, {role}{org}{label}
```

**Usage**:
- For status queries: Bot reads enriched context (no tool call needed)
- For write operations: Bot calls tools (complete_task, update_task, etc.)

**Lesson**: **Enriched context reduces tool calls and improves reliability.** Status queries work even if tool calling is flaky.

---

## Common Issues & Solutions

### "Conflict: terminated by other getUpdates request"

**Cause**: Multiple bot instances running
**Solution**:
```bash
pkill -f "gateway.py"
killall openclaw-gateway
launchctl unload ~/Library/LaunchAgents/ai.openclaw.gateway.plist
./start.sh
```

### "The project list functionality is currently unavailable"

**Cause**: Script path wrong in config
**Solution**: Verify path exists:
```bash
ls /Users/tom/Projects/OSAP/Vantage/OpenClaw/skills/project-manager/scripts/projects.py
```

### Bot not responding to messages

**Check**:
1. Gateway process running: `ps aux | grep gateway.py`
2. Backend API healthy: `curl http://localhost:8000/api/health`
3. vLLM server accessible: `curl http://10.0.8.2:8003/v1/models`
4. Bot token valid: `curl https://api.telegram.org/bot<TOKEN>/getMe`

### Gateway crashes on startup

**Check**:
1. Environment variables loaded: `echo $TELEGRAM_BOT_TOKEN`
2. Script paths exist: Check all paths in config.py
3. Virtual environment activated: `which python3` should show venv path
4. Dependencies installed: `pip list | grep telegram`

---

## Performance Notes

### Response Times

**Typical Flow** (Show me my tasks):
- Get enriched context: ~50ms
- vLLM inference with tools: ~2-3s
- Tool execution: ~100-500ms per tool
- Second vLLM call for final response: ~2-3s
- **Total**: ~5-7 seconds

**Optimization Opportunities**:
1. Cache enriched context (currently fetched every message)
2. Batch tool executions where possible
3. Upgrade to faster model (QwQ-32B with better instruction following may need fewer retries)

---

## Security Considerations

### Bot Token Management

- ✅ Token stored in `.env` (not committed to git)
- ✅ `.gitignore` includes `.env`
- ✅ `.env.example` provided with placeholder
- ⚠️ Token exposed in process list (`ps aux` shows command line)

**Future**: Consider using secrets manager or environment variable from systemd/launchd service.

### Script Execution

- ✅ Scripts executed with subprocess.run(timeout=X)
- ✅ No user input directly passed to shell
- ✅ Arguments validated via OpenAI parameter types
- ⚠️ Scripts run with user's permissions (full file system access)

**Future**: Consider containerization or restricted user account for gateway process.

---

## Migration from OpenClaw

### What Ported Successfully

✅ **Backend API** - Unchanged, works perfectly
✅ **All Python Scripts** - Unchanged (complete_task.py, tasks.py, etc.)
✅ **Behavior Rules** - Converted from SOUL.md to system prompt
✅ **Tool Definitions** - Converted from SKILL.md to OpenAI format
✅ **Database & Models** - Unchanged

### What Changed

❌ **Message Routing** - Custom gateway replaces OpenClaw framework
❌ **Tool Format** - SKILL.md markdown → OpenAI JSON
❌ **Configuration** - openclaw.json → .env file
❌ **Logging** - OpenClaw logs → Python logging with DEBUG mode

### Migration Time

- Planning & research: ~2 hours (understanding OpenClaw issues)
- Implementation: ~1 hour (gateway.py, tools.py, config.py, prompts.py)
- Testing & debugging: ~2 hours (script paths, bot token, conflicts)
- **Total**: ~5 hours from decision to working gateway

**Lesson**: **Custom implementation can be faster than fixing framework issues.** Don't be afraid to rebuild if framework is fundamentally broken.

---

## Future Improvements

### Short Term (When Engineer Available)

1. **Deploy QwQ-32B Model**
   - Better instruction following than Qwen3-8B
   - More reliable tool calling
   - Less reasoning leakage

2. **Add Conversation History**
   - Currently stateless (each message is independent)
   - Store conversation in memory or database
   - Allow multi-turn interactions

3. **Improve Error Messages**
   - Current: "System error" (generic)
   - Better: Specific actionable messages for users

### Long Term (Production Features)

1. **Multi-User Support**
   - User-specific project context
   - User authentication
   - Permission management

2. **Persistent Typing Indicator**
   - Use `createTypingController` instead of one-time callback
   - Refresh every 4-5 seconds during long operations

3. **Rich Response Formatting**
   - Better visual formatting for task lists
   - Inline buttons for actions
   - Progress bars for completion rates

4. **Analytics & Monitoring**
   - Track tool usage patterns
   - Monitor response times
   - Alert on errors

---

## Key Takeaways

1. **Model capabilities matter more than prompts** - Check model's instruction-following and tool-calling abilities before extensive configuration

2. **Custom > Framework when framework is broken** - Don't spend weeks fixing framework issues when custom solution takes hours

3. **Technical controls > Prompt instructions** - Functions like `strip_think_tags()` enforce behavior better than "NEVER do X" instructions

4. **Enriched context reduces tool dependency** - Pre-loading data into context makes bot more reliable for read operations

5. **One bot token = one instance** - Telegram enforces single connection per token; manage processes carefully

6. **Explicit logging is invaluable** - DEBUG mode saved hours of debugging during development

7. **Test scripts independently** - Verify `python3 script.py` works before integrating into gateway

8. **Environment variable pitfalls** - Background processes need explicit `set -a; source .env` loading

9. **Validate early** - Test bot token, script paths, API endpoints before complex integration

10. **Document as you go** - This LESSONS.md file was created while building; retroactive documentation is harder

---

## References

- **Migration Guide**: [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
- **GitHub Repository**: https://github.com/tom-sl878/vantage-telegram-gateway
- **Backend API**: http://localhost:8000/api
- **vLLM Server**: http://10.0.8.2:8003
- **OpenClaw Issues**: Documented in `/Users/tom/.claude/projects/-Users-tom/memory/MEMORY.md`
