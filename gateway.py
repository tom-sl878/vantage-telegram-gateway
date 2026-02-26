#!/usr/bin/env python3
"""Custom Telegram Gateway for Vantage Bot"""
import asyncio
import json
import logging
import re
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, MessageHandler, CallbackQueryHandler, CommandHandler, filters, ContextTypes
import httpx

from telegram import MenuButtonWebApp, WebAppInfo
from config import (
    TELEGRAM_TOKEN, VLLM_URL, BACKEND_API, DEFAULT_PROJECT,
    MEDIA_INBOX, VLLM_MODEL, MODEL_TEMPERATURE, MODEL_MAX_TOKENS, LOG_LEVEL,
    LLM_PROVIDER, ANTHROPIC_API_KEY, CLAUDE_MODEL, WEBAPP_URL,
)
from prompts import SYSTEM_PROMPT
from tools import TOOLS, execute_tool
from handlers import try_handle, handle_tasks_command, handle_projects_command, handle_stats_command
from formatters import format_help, format_welcome, format_task_list, format_task_detail, format_project_stats
from i18n import get_lang, t

# Lazy-init Claude client (only when provider=claude)
_claude_client = None

def _get_claude_client():
    global _claude_client
    if _claude_client is None:
        import anthropic
        _claude_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    return _claude_client

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _user_lang(update, person: dict | None = None) -> str:
    """Get user language: saved preference > Telegram language_code > English."""
    try:
        if person and person.get("language"):
            return person["language"]
        return get_lang(update.effective_user.language_code)
    except Exception:
        return "en"


async def save_language(person_id: int, lang: str) -> bool:
    """Save language preference to backend."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.patch(
                f"{BACKEND_API}/people/{person_id}",
                json={"language": lang},
            )
            return response.status_code == 200
    except Exception as e:
        logger.warning(f"Failed to save language for person {person_id}: {e}")
        return False


async def resolve_person(telegram_id: str, context: ContextTypes.DEFAULT_TYPE | None = None) -> dict | None:
    """Look up Person record by Telegram ID. Returns person dict or None.

    Caches the result in context.user_data so a transient API failure
    doesn't cause repeated verification prompts.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{BACKEND_API}/people/by-telegram/{telegram_id}")
            if response.status_code == 200:
                person = response.json()
                if context is not None:
                    context.user_data["cached_person"] = person
                return person
            # API returned non-200 — fall back to cache
            if context and context.user_data.get("cached_person"):
                logger.info("resolve_person: using cached person (API returned %s)", response.status_code)
                return context.user_data["cached_person"]
            return None
    except Exception as e:
        logger.warning(f"Failed to resolve person for telegram_id {telegram_id}: {e}")
        if context and context.user_data.get("cached_person"):
            logger.info("resolve_person: using cached person after exception")
            return context.user_data["cached_person"]
        return None


def _is_verified(person: dict | None) -> bool:
    """Check if a resolved person is verified."""
    return bool(person and person.get("verification_status") == "verified")


async def verify_code(code: str, telegram_id: str) -> dict:
    """Call backend verify endpoint. Returns dict with 'success', 'message', etc."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{BACKEND_API}/people/verify",
                json={"code": code, "telegram_id": telegram_id},
            )
            if response.status_code == 200:
                return response.json()
            return {"success": False, "message": "Verification service error."}
    except Exception as e:
        logger.error(f"Verification call failed: {e}")
        return {"success": False, "message": "Could not reach verification service."}


async def get_enriched_context(project_slug: str, person_id: int | None = None) -> str:
    """Fetch enriched context from backend API, optionally scoped to a person."""
    async with httpx.AsyncClient() as client:
        try:
            params = {}
            if person_id:
                params["person_id"] = person_id
            response = await client.get(f"{BACKEND_API}/projects/{project_slug}/chat/context", params=params)
            if response.status_code == 200:
                return response.json().get("context", "")
            else:
                logger.warning(f"Failed to fetch context: {response.status_code}")
                return ""
        except Exception as e:
            logger.error(f"Error fetching context: {e}")
            return ""


async def persist_messages(project_slug: str, user_id: str, user_msg: str, assistant_msg: str):
    """Save messages to backend DB — single source of truth for all channels."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{BACKEND_API}/projects/{project_slug}/chat/messages",
                json={
                    "user_id": user_id,
                    "messages": [
                        {"role": "user", "content": user_msg},
                        {"role": "assistant", "content": assistant_msg},
                    ],
                },
            )
            logger.debug(f"Persisted messages for user {user_id}")
    except Exception as e:
        logger.warning(f"Failed to persist messages: {e}")


async def get_chat_history(project_slug: str, user_id: str) -> list[dict]:
    """Fetch conversation history from backend DB (single source of truth)."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{BACKEND_API}/projects/{project_slug}/chat",
                params={"user_id": user_id, "limit": 20},
            )
            if response.status_code == 200:
                messages = response.json()
                # Convert DB format to OpenAI message format
                return [{"role": m["role"], "content": m["content"]} for m in messages]
            else:
                logger.warning(f"Failed to fetch history: {response.status_code}")
                return []
    except Exception as e:
        logger.warning(f"Error fetching history: {e}")
        return []


async def call_llm(messages: list, tools: list = None) -> dict:
    """Call configured LLM provider. Messages are in OpenAI format.
    Returns normalized dict: {"content": str|None, "tool_calls": list|None}
    where tool_calls match OpenAI format: [{"id": str, "function": {"name": str, "arguments": str}}]
    """
    if LLM_PROVIDER == "claude":
        return await _call_claude(messages, tools)
    else:
        return await _call_vllm(messages, tools)


async def _call_vllm(messages: list, tools: list = None) -> dict:
    """Call vLLM server with messages and optional tools"""
    payload = {
        "model": VLLM_MODEL,
        "messages": messages,
        "temperature": MODEL_TEMPERATURE,
        "max_tokens": MODEL_MAX_TOKENS
    }

    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    logger.debug(f"Calling vLLM with {len(messages)} messages and {len(tools) if tools else 0} tools")

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(VLLM_URL, json=payload)
            response.raise_for_status()
            result = response.json()
            logger.debug(f"vLLM response: {json.dumps(result, indent=2)}")
            msg = result["choices"][0]["message"]
            return {"content": msg.get("content"), "tool_calls": msg.get("tool_calls")}
        except Exception as e:
            logger.error(f"vLLM call failed: {e}")
            raise


def _convert_tools_for_claude(tools: list) -> list:
    """Convert OpenAI tool format to Claude tool format."""
    return [
        {
            "name": t["function"]["name"],
            "description": t["function"]["description"],
            "input_schema": t["function"]["parameters"],
        }
        for t in tools
    ]


def _convert_messages_for_claude(messages: list) -> tuple[str, list]:
    """Convert OpenAI-format messages to Claude format.
    Returns (system_prompt, claude_messages).
    """
    system_parts = []
    claude_messages = []

    for msg in messages:
        role = msg["role"]

        if role == "system":
            system_parts.append(msg["content"])

        elif role == "user":
            claude_messages.append({"role": "user", "content": msg["content"]})

        elif role == "assistant":
            if msg.get("tool_calls"):
                # Convert tool_calls to Claude tool_use content blocks
                content_blocks = []
                if msg.get("content"):
                    content_blocks.append({"type": "text", "text": msg["content"]})
                for tc in msg["tool_calls"]:
                    args = tc["function"]["arguments"]
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": json.loads(args) if isinstance(args, str) else args,
                    })
                claude_messages.append({"role": "assistant", "content": content_blocks})
            else:
                claude_messages.append({"role": "assistant", "content": msg.get("content", "")})

        elif role == "tool":
            # Claude expects tool_result blocks inside a user message.
            # Group consecutive tool results together.
            tool_result_block = {
                "type": "tool_result",
                "tool_use_id": msg["tool_call_id"],
                "content": msg["content"],
            }
            # If the last claude message is already a user message with tool_results, append
            if (claude_messages and claude_messages[-1]["role"] == "user"
                    and isinstance(claude_messages[-1]["content"], list)):
                claude_messages[-1]["content"].append(tool_result_block)
            else:
                claude_messages.append({"role": "user", "content": [tool_result_block]})

    return "\n\n".join(system_parts), claude_messages


async def _call_claude(messages: list, tools: list = None) -> dict:
    """Call Claude API with messages and optional tools."""
    client = _get_claude_client()
    system_prompt, claude_messages = _convert_messages_for_claude(messages)
    claude_tools = _convert_tools_for_claude(tools) if tools else []

    logger.debug(f"Calling Claude ({CLAUDE_MODEL}) with {len(claude_messages)} messages and {len(claude_tools)} tools")

    kwargs = {
        "model": CLAUDE_MODEL,
        "max_tokens": MODEL_MAX_TOKENS,
        "system": system_prompt,
        "messages": claude_messages,
        "temperature": MODEL_TEMPERATURE,
    }
    if claude_tools:
        kwargs["tools"] = claude_tools

    try:
        response = await client.messages.create(**kwargs)
        logger.debug(f"Claude response stop_reason={response.stop_reason}")

        # Convert Claude response to normalized format
        text_parts = []
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(block.input),
                    }
                })

        return {
            "content": "\n".join(text_parts) if text_parts else None,
            "tool_calls": tool_calls if tool_calls else None,
        }
    except Exception as e:
        logger.error(f"Claude call failed: {e}")
        raise


def strip_think_tags(text: str) -> str:
    """Remove <think> tags and their contents from text"""
    if not text:
        return ""
    # Remove everything from <think> to </think>
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # Clean up any remaining stray tags
    text = re.sub(r'</?think>', '', text)
    return text.strip()


def _md_to_html(text: str) -> str:
    """Convert common markdown patterns to Telegram-compatible HTML."""
    if not text:
        return text
    # Remove "ANSWER:" prefix
    text = re.sub(r'^ANSWER:\s*', '', text, flags=re.IGNORECASE)
    # ## Headers → bold with spacing
    text = re.sub(r'^#{1,6}\s+(.+)$', r'\n<b>\1</b>', text, flags=re.MULTILINE)
    # **bold** → <b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # *italic* → <i> (only if not preceded/followed by word chars, to avoid false matches)
    text = re.sub(r'(?<!\w)\*(.+?)\*(?!\w)', r'<i>\1</i>', text)
    # `code` → <code>
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    # Collapse excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


class _SyntheticUpdate:
    """Lightweight stand-in for telegram.Update used to route synthetic user
    messages (e.g. from callback buttons) through handle_message."""

    def __init__(self, *, message, effective_chat, effective_user, text):
        self.message = message
        self.effective_chat = effective_chat
        self.effective_user = effective_user
        self._synthetic_text = text


def _collect_template_actions(tool_result: dict, arguments: dict,
                              pending_files: list, reply_buttons: list):
    """Extract template files and buttons from get_report_template results.

    Modifies tool_result in-place to replace local paths/URLs with a delivery
    note so the LLM doesn't leak filesystem info to the user.
    """
    filename = tool_result.get("template_file", "template.pdf")

    # Prefer blank template (fillable form) over original
    file_path = None
    if tool_result.get("has_blank") and tool_result.get("blank_template_path"):
        file_path = tool_result["blank_template_path"]
        stem = Path(filename).stem
        filename = f"{stem}_blank.pdf"
    elif tool_result.get("template_path"):
        file_path = tool_result["template_path"]

    if file_path and Path(file_path).is_file():
        pending_files.append((file_path, filename))
        # Replace paths/URLs with delivery note for the LLM
        for key in ("template_path", "blank_template_path",
                     "template_download_url", "blank_download_url"):
            tool_result.pop(key, None)
        tool_result["file_delivery"] = (
            f"The template file '{filename}' will be sent as a document in chat automatically. "
            "Do NOT include any download URLs or file paths in your response."
        )

    # Add "Fill in via Chat" button if template has fields (tool-level fallback)
    if tool_result.get("template_fields"):
        report_id = arguments.get("report_id")
        reply_buttons.append([
            InlineKeyboardButton(
                "\U0001f4dd Fill in via Chat",
                callback_data=f"fill_report:{report_id}",
            )
        ])


def _parse_buttons(text: str) -> tuple[str, list[list[InlineKeyboardButton]]]:
    """Extract [BUTTONS]...[/BUTTONS] block from LLM response text.

    Returns (clean_text, button_rows).  Each row is a list of
    InlineKeyboardButton instances.  The block is stripped from the visible
    message.
    """
    match = re.search(r'\[BUTTONS\]\s*\n(.*?)\n?\s*\[/BUTTONS\]', text, re.DOTALL)
    if not match:
        return text, []

    clean_text = (text[:match.start()].rstrip() + text[match.end():]).strip()

    rows: list[list[InlineKeyboardButton]] = []
    for line in match.group(1).strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        row: list[InlineKeyboardButton] = []
        for part in line.split('||'):
            part = part.strip()
            if '|' not in part:
                continue
            label, cb_data = part.rsplit('|', 1)
            label, cb_data = label.strip(), cb_data.strip()
            if label and cb_data:
                row.append(InlineKeyboardButton(label, callback_data=cb_data))
        if row:
            rows.append(row)

    return clean_text, rows


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming Telegram messages"""
    # Check if this is a synthetic update with custom text
    if hasattr(update, '_synthetic_text'):
        user_message = update._synthetic_text
    else:
        user_message = update.message.text

    chat_id = update.effective_chat.id

    logger.info(f"Received message from {chat_id}: {user_message}")

    # Check if this message has a document (caption with file upload)
    if update.message.document:
        file_info = f"\n\n[User uploaded file: {update.message.document.file_name}]"
        user_message = user_message + file_info if user_message else file_info
        logger.info(f"Message includes document: {update.message.document.file_name}")
    # Or check if there was a recent file upload
    elif 'last_upload' in context.user_data:
        upload_info = context.user_data['last_upload']
        user_message = f"{user_message}\n\n[Recently uploaded file: {upload_info['filename']}]"
        logger.info(f"Referencing recent upload: {upload_info['filename']}")

    # Send typing indicator
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # Resolve Telegram user to a Person record
        tg_id = str(update.effective_user.id)
        person = await resolve_person(tg_id, context)
        user_id = f"person-{person['id']}" if person else tg_id
        is_synthetic = hasattr(update, '_synthetic_text')

        lang = _user_lang(update, person)

        # --- Verification gate (skip for synthetic updates from callbacks) ---
        if not is_synthetic and not _is_verified(person):
            await update.message.reply_text(t("verify_prompt", lang), parse_mode="HTML")
            return

        # --- Pending admin action (e.g. after clicking "Set Due Date" button) ---
        pending = context.user_data.pop("pending_action", None)
        if pending and pending.get("type") == "set_due_date":
            user_message = f"Update the due date for task {pending['task_id']} to {user_message}"

        # --- Handler chain: classify intent and handle common actions directly ---
        # Skip for synthetic updates (callbacks) and messages with documents
        has_document = hasattr(update.message, 'document') and update.message.document
        if not is_synthetic and not has_document:
            handler_result = await try_handle(user_message, person, DEFAULT_PROJECT, lang=lang)
            if handler_result is not None:
                reply_text, buttons = handler_result
                reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
                await update.message.reply_text(
                    reply_text, parse_mode="HTML", reply_markup=reply_markup,
                )
                logger.info(f"Handler chain responded: {reply_text[:100]}...")
                asyncio.create_task(persist_messages(DEFAULT_PROJECT, user_id, user_message, reply_text))
                return

        # --- Full agentic LLM loop (fallback for complex/ambiguous messages) ---

        # Get enriched context from backend (scoped to this person's role)
        person_db_id = person.get("id") if person else None
        enriched_context = await get_enriched_context(DEFAULT_PROJECT, person_id=person_db_id)

        # Fetch conversation history from DB (single source of truth)
        history = await get_chat_history(DEFAULT_PROJECT, user_id)

        # Build message history with enriched context and conversation history
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": f"PROJECT CONTEXT:\n{enriched_context}"},
        ]

        # Add conversation history (last 10 messages to avoid context overflow)
        messages.extend(history[-10:])

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        # Call LLM with tools - loop until we get text response
        max_iterations = 5  # Prevent infinite loops
        iteration = 0
        final_message = None
        pending_files = []   # [(local_path, filename)] to send after reply
        reply_buttons = []   # [[InlineKeyboardButton, ...]] for inline keyboard

        while iteration < max_iterations:
            result = await call_llm(messages, TOOLS)

            if result.get("tool_calls"):
                # Execute each tool call
                logger.info(f"LLM requested {len(result['tool_calls'])} tool calls (iteration {iteration + 1})")

                # Append assistant message (with tool_calls) in OpenAI format
                messages.append({
                    "role": "assistant",
                    "content": result.get("content"),
                    "tool_calls": result["tool_calls"],
                })

                for tool_call in result["tool_calls"]:
                    tool_name = tool_call["function"]["name"]
                    arguments = json.loads(tool_call["function"]["arguments"])

                    # Inject requester context for request_action
                    if tool_name == "request_action" and person:
                        arguments["requester_id"] = person["id"]

                    logger.info(f"Executing tool: {tool_name} with args: {arguments}")

                    # Execute tool (pass actor for activity logging)
                    actor_name = person.get("name") if person else None
                    tool_result = execute_tool(tool_name, arguments, actor=actor_name)
                    logger.info(f"Tool result: {tool_result}")

                    # Intercept get_report_template for file delivery + buttons
                    if (tool_name == "get_report_template"
                            and isinstance(tool_result, dict)
                            and tool_result.get("success")):
                        _collect_template_actions(
                            tool_result, arguments, pending_files, reply_buttons,
                        )

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": tool_name,
                        "content": json.dumps(tool_result)
                    })

                # Continue loop to call LLM again
                await context.bot.send_chat_action(chat_id=chat_id, action="typing")
                iteration += 1
            else:
                # No more tool calls, we have final response
                final_message = result.get("content", "")
                break

        if not final_message:
            logger.warning(f"No text response after {iteration} iterations")
            final_message = "I executed the tools but couldn't generate a response."

        # Strip <think> tags if present
        final_message = strip_think_tags(final_message)

        if not final_message or final_message.isspace():
            final_message = "I processed your request but have no response to show."
            logger.warning("Empty response after stripping think tags")

        # Clean up LLM markdown for Telegram HTML display
        final_message = _md_to_html(final_message)

        # Extract LLM-specified buttons from response text
        final_message, llm_buttons = _parse_buttons(final_message)

        # LLM buttons take precedence; tool-level buttons are a fallback
        all_buttons = llm_buttons if llm_buttons else reply_buttons
        reply_markup = InlineKeyboardMarkup(all_buttons) if all_buttons else None
        await update.message.reply_text(
            final_message, parse_mode="HTML", reply_markup=reply_markup,
        )
        logger.info(f"Sent response: {final_message[:100]}...")

        # Send pending files as Telegram documents
        for file_path, filename in pending_files:
            try:
                with open(file_path, "rb") as f:
                    await context.bot.send_document(
                        chat_id=chat_id, document=f, filename=filename,
                    )
                logger.info(f"Sent template file: {filename}")
            except Exception as e:
                logger.error(f"Failed to send file {filename}: {e}")

        # Persist to backend DB (single source of truth for all channels)
        asyncio.create_task(persist_messages(DEFAULT_PROJECT, user_id, user_message, final_message))

    except Exception as e:
        error_msg = f"Error processing message: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await update.message.reply_text(t("error_generic", _user_lang(update)))


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document uploads (PDFs, etc.)"""
    # Verification gate
    tg_id = str(update.effective_user.id)
    person = await resolve_person(tg_id, context)
    lang = _user_lang(update, person)
    if not _is_verified(person):
        await update.message.reply_text(t("verify_prompt", lang), parse_mode="HTML")
        return

    chat_id = update.effective_chat.id
    document = update.message.document

    logger.info(f"Received document: {document.file_name}")

    try:
        # Download file to media inbox
        MEDIA_INBOX.mkdir(parents=True, exist_ok=True)
        file = await context.bot.get_file(document.file_id)
        file_path = MEDIA_INBOX / document.file_name
        await file.download_to_drive(file_path)

        logger.info(f"Saved file to: {file_path}")

        # Store file info in user context for LLM to access
        context.user_data['last_upload'] = {
            'filename': document.file_name,
            'path': str(file_path),
            'timestamp': update.message.date.isoformat()
        }

        # If user sent a caption, Telegram will call handle_message separately with it
        # If no caption, check conversation history for task context
        if not update.message.caption:
            # Check if user was recently talking about a task
            history = context.user_data.get('conversation_history', [])
            recent_messages = ' '.join([msg.get('content', '') for msg in history[-4:]])  # Last 2 exchanges

            # Look for task mentions in recent conversation
            import re
            task_match = re.search(r'task (\d+)', recent_messages.lower())

            if task_match:
                task_id = task_match.group(1)
                logger.info(f"Auto-detected task context: task {task_id}")

                # Send confirmation and trigger analysis via handle_message
                await update.message.reply_text(
                    t("file_analyzing", lang, filename=document.file_name, task_id=task_id)
                )

                # Create a synthetic message to trigger the LLM with file context
                synthetic_update = _SyntheticUpdate(
                    message=update.message,
                    effective_chat=update.effective_chat,
                    effective_user=update.effective_user,
                    text=f"Analyze this uploaded document for task {task_id}",
                )
                await handle_message(synthetic_update, context)
            else:
                # No task context — route through LLM for smart file analysis
                logger.info(f"No task context for upload, routing through LLM for smart matching")
                await update.message.reply_text(
                    t("file_analyzing_smart", lang, filename=document.file_name)
                )

                synthetic_update = _SyntheticUpdate(
                    message=update.message,
                    effective_chat=update.effective_chat,
                    effective_user=update.effective_user,
                    text=(
                        f"I just uploaded a file called '{document.file_name}' without specifying what it's for. "
                        f"Please use the preview_file tool to look at its contents, then check my open tasks "
                        f"and deliverables to suggest what this file might be for. "
                        f"If you can identify a likely match, suggest it. Otherwise ask me what I'd like to do with it."
                    ),
                )
                await handle_message(synthetic_update, context)

    except Exception as e:
        error_msg = f"Error handling document: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await update.message.reply_text(t("error_file", lang))


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()

    data = query.data
    chat_id = query.message.chat_id
    tg_id = str(query.from_user.id) if query.from_user else None
    person = await resolve_person(tg_id, context) if tg_id else None
    lang = _user_lang(update, person)
    logger.info(f"Callback: {data}")

    # --- Language selection callback ---
    if data.startswith("set_lang:"):
        chosen = data.split(":")[1]
        if chosen in ("ko", "en", "vi") and person:
            await save_language(person["id"], chosen)
            await query.message.edit_text(t("lang_set", chosen), parse_mode="HTML")
        return

    def _synth(text: str) -> _SyntheticUpdate:
        return _SyntheticUpdate(
            message=query.message,
            effective_chat=query.message.chat,
            effective_user=query.from_user,
            text=text,
        )

    if data.startswith("get_template:"):
        # Direct file delivery — no LLM round-trip needed
        report_id = int(data.split(":")[1])
        actor_name = person.get("name") if person else None
        tool_result = execute_tool("get_report_template", {"report_id": report_id}, actor=actor_name)
        if isinstance(tool_result, dict) and tool_result.get("success"):
            filename = tool_result.get("template_file", "template.pdf")
            file_path = None
            if tool_result.get("has_blank") and tool_result.get("blank_template_path"):
                file_path = tool_result["blank_template_path"]
                stem = Path(filename).stem
                filename = f"{stem}_blank.pdf"
            elif tool_result.get("template_path"):
                file_path = tool_result["template_path"]

            if file_path and Path(file_path).is_file():
                try:
                    with open(file_path, "rb") as f:
                        await context.bot.send_document(
                            chat_id=chat_id, document=f, filename=filename,
                        )
                except Exception as e:
                    logger.error(f"Failed to send template: {e}")
                    await query.message.reply_text("Failed to send template file.")
            else:
                await query.message.reply_text("Template file not found.")
        else:
            await query.message.reply_text("Could not fetch template info.")

    elif data.startswith("fill_report:"):
        report_id = data.split(":")[1]
        await handle_message(
            _synth(f"I want to fill in data via chat for report {report_id}"),
            context,
        )

    elif data.startswith("start_task:"):
        task_id = data.split(":")[1]
        await handle_message(
            _synth(f"Start working on task {task_id}, set status to in_progress"),
            context,
        )

    elif data.startswith("complete_task:"):
        task_id = data.split(":")[1]
        # Confirmation prompt instead of immediate completion
        text = (
            f"{t('complete_confirm', lang)}\n\n"
            f"{t('complete_confirm_note', lang)}"
        )
        buttons = [[
            InlineKeyboardButton(t("btn_yes_complete", lang), callback_data=f"confirm_complete:{task_id}"),
            InlineKeyboardButton(t("btn_cancel", lang), callback_data="dismiss"),
        ]]
        await query.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("confirm_complete:"):
        task_id = data.split(":")[1]
        # Fetch enriched task detail to check acceptance criteria
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{BACKEND_API}/tasks/{task_id}/detail")
                if resp.status_code == 200:
                    task_detail = resp.json()
                else:
                    task_detail = None
        except Exception:
            task_detail = None

        # Check criteria: documents uploaded, requirements exist, deliverable format
        issues = []
        if task_detail:
            doc_count = task_detail.get("document_count", 0)
            requirements = task_detail.get("requirements", [])
            deliverable = task_detail.get("deliverable")

            if deliverable and doc_count == 0:
                issues.append(t("criteria_no_docs", lang))
            if requirements:
                req_titles = [r["title"] for r in requirements]
                issues.append(t("criteria_missing_reqs", lang))
                for title in req_titles:
                    issues.append(f"  \u2022 {title}")
            if deliverable and deliverable.get("format") and doc_count == 0:
                fmt = deliverable["format"].replace("_", " ").title()
                issues.append(t("criteria_expected_format", lang, format=fmt))

        if issues:
            # Push back with summary
            warning = t("criteria_warning", lang) + "\n".join(issues) + t("criteria_action_hint", lang)
            buttons = [[
                InlineKeyboardButton(t("btn_override_complete", lang), callback_data=f"force_complete:{task_id}"),
                InlineKeyboardButton(t("btn_cancel", lang), callback_data="dismiss"),
            ]]
            await query.message.reply_text(warning, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            # No issues — complete directly
            await handle_message(
                _synth(f"Mark task {task_id} as complete"),
                context,
            )

    elif data.startswith("force_complete:"):
        task_id = data.split(":")[1]
        await handle_message(
            _synth(f"Mark task {task_id} as complete"),
            context,
        )

    elif data == "dismiss":
        await query.message.reply_text(t("action_cancelled", lang), parse_mode="HTML")

    elif data.startswith("admin_set_due:"):
        task_id = data.split(":")[1]
        context.user_data["pending_action"] = {"type": "set_due_date", "task_id": task_id}
        await query.message.reply_text(
            t("admin_set_due_prompt", lang, tid=task_id),
            parse_mode="HTML",
        )

    elif data.startswith("reopen_task:"):
        task_id = data.split(":")[1]
        await handle_message(
            _synth(f"Reopen task {task_id}"),
            context,
        )

    elif data.startswith("view_tasks:"):
        slug = data.split(":", 1)[1]
        text, buttons = await handle_tasks_command(person, slug, lang=lang)
        reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
        await query.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)
        cb_uid = f"person-{person['id']}" if person else tg_id
        asyncio.create_task(persist_messages(slug, cb_uid, "[Viewed tasks]", text))

    elif data.startswith("view_overdue:"):
        slug = data.split(":", 1)[1]
        text, buttons = await handle_tasks_command(person, slug, lang=lang)
        reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
        await query.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)
        cb_uid = f"person-{person['id']}" if person else tg_id
        asyncio.create_task(persist_messages(slug, cb_uid, "[Viewed overdue tasks]", text))

    elif data.startswith("view_stats:"):
        slug = data.split(":", 1)[1]
        text, buttons = await handle_stats_command(person, slug, lang=lang)
        reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
        await query.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)
        cb_uid = f"person-{person['id']}" if person else tg_id
        asyncio.create_task(persist_messages(slug, cb_uid, "[Viewed stats]", text))

    elif data.startswith("view_task:"):
        task_id = int(data.split(":")[1])
        # Use enriched detail endpoint for full deliverable/requirements info
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{BACKEND_API}/tasks/{task_id}/detail")
                result = resp.json() if resp.status_code == 200 else {"error": "not found"}
        except Exception:
            result = {"error": "fetch failed"}
        if isinstance(result, dict) and not result.get("error"):
            text, buttons = format_task_detail(result, lang=lang)
        else:
            text, buttons = t("fetch_error", lang, item=f"task {task_id}", error="not found"), []
        reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
        await query.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)
        cb_uid = f"person-{person['id']}" if person else tg_id
        asyncio.create_task(persist_messages(DEFAULT_PROJECT, cb_uid, f"[Viewed task #{task_id}]", text))

    elif data.startswith("cmd:"):
        # Button-triggered commands (e.g. from help screen)
        cmd = data.split(":", 1)[1]
        if cmd == "tasks":
            text, buttons = await handle_tasks_command(person, DEFAULT_PROJECT, lang=lang)
        elif cmd == "stats":
            text, buttons = await handle_stats_command(person, DEFAULT_PROJECT, lang=lang)
        elif cmd == "help":
            text, buttons = format_help(lang=lang)
        else:
            text, buttons = f"Unknown command: {cmd}", []
        reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
        await query.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)
        cb_uid = f"person-{person['id']}" if person else tg_id
        asyncio.create_task(persist_messages(DEFAULT_PROJECT, cb_uid, f"[/{cmd}]", text))

    else:
        logger.warning(f"Unknown callback data: {data}")


async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start, /help, /tasks, /projects, /stats commands directly (no LLM)."""
    chat_id = update.effective_chat.id
    parts = update.message.text.split()
    command = parts[0].lstrip("/").split("@")[0]  # strip /command@botname
    args = parts[1:]

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    tg_id = str(update.effective_user.id)
    person = await resolve_person(tg_id, context)
    lang = _user_lang(update, person)

    try:
        # --- /lang: language selection (always accessible) ---
        if command == "lang":
            if not _is_verified(person):
                await update.message.reply_text(t("verify_prompt", lang), parse_mode="HTML")
                return
            if args and args[0].lower() in ("ko", "en", "vi"):
                chosen = args[0].lower()
                await save_language(person["id"], chosen)
                await update.message.reply_text(t("lang_set", chosen), parse_mode="HTML")
                return
            # Show picker buttons
            buttons = [[
                InlineKeyboardButton("KO \ud55c\uad6d\uc5b4", callback_data="set_lang:ko"),
                InlineKeyboardButton("EN English", callback_data="set_lang:en"),
                InlineKeyboardButton("VI Ti\u1ebfng Vi\u1ec7t", callback_data="set_lang:vi"),
            ]]
            text = f"{t('lang_current', lang, language=lang.upper())}\n\n{t('lang_pick', lang)}"
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
            return

        # --- /start: verification flow (always accessible) ---
        if command == "start":
            if args:
                # /start <code> — verification attempt
                code = args[0].strip()
                result = await verify_code(code, tg_id)
                if result.get("success"):
                    name = result.get("name", "there")
                    text = (
                        f"{t('verify_success', lang)}\n\n"
                        f"{t('verify_welcome', lang, name=name)}"
                    )
                    buttons = [[InlineKeyboardButton(t("btn_help", lang), callback_data="cmd:help")]]
                else:
                    msg = result.get("message") or t("verify_invalid", lang)
                    text = f"{t('verify_failed', lang)}\n\n{msg}"
                    buttons = []
            else:
                # /start (no code) — check if already verified
                if _is_verified(person):
                    projects = execute_tool("get_projects", {}, actor=person.get("name") if person else None)
                    text, buttons = format_welcome(projects if isinstance(projects, list) else [], lang=lang)
                else:
                    text = (
                        f"{t('welcome_title', lang)}\n\n"
                        f"{t('welcome_need_code', lang)}"
                    )
                    buttons = []

            reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)

            user_id = f"person-{person['id']}" if person else tg_id
            asyncio.create_task(persist_messages(DEFAULT_PROJECT, user_id, f"/start {' '.join(args)}".strip(), text))
            return

        # --- Verification gate for all other commands ---
        if not _is_verified(person):
            await update.message.reply_text(t("verify_prompt", lang), parse_mode="HTML")
            return

        user_id = f"person-{person['id']}" if person else tg_id

        if command == "help":
            text, buttons = format_help(lang=lang)
        elif command == "tasks":
            text, buttons = await handle_tasks_command(person, DEFAULT_PROJECT, lang=lang)
        elif command == "projects":
            text, buttons = await handle_projects_command(person, lang=lang)
        elif command == "stats":
            text, buttons = await handle_stats_command(person, DEFAULT_PROJECT, lang=lang)
        else:
            text, buttons = f"Unknown command: /{command}", []

        reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)
        asyncio.create_task(persist_messages(DEFAULT_PROJECT, user_id, f"/{command}", text))

    except Exception as e:
        logger.error(f"Error handling /{command}: {e}", exc_info=True)
        await update.message.reply_text(t("error_generic", lang))


async def handle_open_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a web_app button to open the mini app (bypasses BotFather domain)."""
    if not WEBAPP_URL:
        await update.message.reply_text("WEBAPP_URL not configured.")
        return

    # Method 1: Inline keyboard button with web_app
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Open Mini App", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await update.message.reply_text("Tap to open:", reply_markup=keyboard)


async def handle_webapp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a reply keyboard button with web_app (another approach)."""
    if not WEBAPP_URL:
        await update.message.reply_text("WEBAPP_URL not configured.")
        return

    # Method 2: Reply keyboard button with web_app
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("Open Vantage", web_app=WebAppInfo(url=WEBAPP_URL))]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.message.reply_text("Tap the button below:", reply_markup=keyboard)


def main():
    """Start the bot"""
    logger.info("Starting Vantage Telegram Gateway...")
    logger.info(f"LLM provider: {LLM_PROVIDER}")
    if LLM_PROVIDER == "claude":
        logger.info(f"Claude model: {CLAUDE_MODEL}")
    else:
        logger.info(f"vLLM model: {VLLM_MODEL}")
        logger.info(f"vLLM URL: {VLLM_URL}")
    logger.info(f"Backend API: {BACKEND_API}")
    logger.info(f"Default project: {DEFAULT_PROJECT}")

    # Set mini app menu button on startup
    async def post_init(app):
        if WEBAPP_URL:
            try:
                await app.bot.set_chat_menu_button(
                    menu_button=MenuButtonWebApp(
                        text="Open App",
                        web_app=WebAppInfo(url=WEBAPP_URL),
                    )
                )
                logger.info(f"Menu button set to {WEBAPP_URL}")
            except Exception as e:
                logger.warning(f"Failed to set menu button: {e}")

    # Create application
    builder = Application.builder().token(TELEGRAM_TOKEN)
    if WEBAPP_URL:
        builder = builder.post_init(post_init)
    application = builder.build()

    # Add handlers — command handlers first (most specific), then text, then documents
    application.add_handler(CommandHandler(["start", "help", "tasks", "projects", "stats", "lang"], handle_command))
    application.add_handler(CommandHandler("open", handle_open_command))
    application.add_handler(CommandHandler("webapp", handle_webapp_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Start bot
    logger.info("Bot started successfully. Ready to receive messages.")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
