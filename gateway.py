#!/usr/bin/env python3
"""Custom Telegram Gateway for Vantage Bot"""
import asyncio
import logging
import re
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, MessageHandler, CallbackQueryHandler, CommandHandler, filters, ContextTypes
import httpx

from telegram import MenuButtonWebApp, WebAppInfo
from config import (
    TELEGRAM_TOKEN, BACKEND_API,
    MEDIA_INBOX, LOG_LEVEL, WEBAPP_URL,
    INTERNAL_TOKEN,
)
from handlers import try_handle, handle_tasks_command, handle_projects_command, handle_stats_command
from formatters import format_help, format_welcome, format_task_list, format_task_detail, format_project_stats
from i18n import get_lang, t

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def _record_activity(person_id: int) -> None:
    """Fire-and-forget: bump last_active_at via backend."""
    try:
        headers = _backend_headers()
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{BACKEND_API}/people/{person_id}/activity", headers=headers)
    except Exception:
        pass


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


async def _get_person_projects(person_id: int) -> list[dict]:
    """Fetch projects for a person from the backend."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{BACKEND_API}/people/{person_id}/projects")
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.warning(f"Failed to fetch projects for person {person_id}: {e}")
    return []


async def _get_active_project(context: ContextTypes.DEFAULT_TYPE, person: dict | None) -> str | None:
    """Get the active project slug for this user session.

    Returns slug from user_data, or auto-selects if the user has exactly one project.
    Returns None if no project could be determined.
    """
    # Check if already selected in this session
    active = context.user_data.get("active_project")
    if active:
        return active["slug"]

    # Auto-resolve from person's memberships
    if not person or not person.get("id"):
        return None

    projects = await _get_person_projects(person["id"])
    if len(projects) == 1:
        context.user_data["active_project"] = {
            "slug": projects[0]["slug"],
            "name": projects[0]["name"],
        }
        return projects[0]["slug"]

    return None


async def _ensure_project_or_prompt(
    update: Update, context: ContextTypes.DEFAULT_TYPE, person: dict | None, lang: str,
) -> str | None:
    """Ensure the user has an active project. If multiple projects exist and none is
    selected, show a project selector keyboard and return None.
    Returns the project slug if available.
    """
    slug = await _get_active_project(context, person)
    if slug:
        return slug

    # No project auto-selected — need to show selector
    if not person or not person.get("id"):
        return None

    projects = await _get_person_projects(person["id"])
    if not projects:
        await update.message.reply_text(t("no_projects", lang))
        return None

    # Multiple projects — show inline keyboard selector
    buttons = []
    for p in projects:
        buttons.append([InlineKeyboardButton(
            p["name"], callback_data=f"sp:{p['slug']}"
        )])
    await update.message.reply_text(
        t("select_project", lang),
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return None


async def persist_messages(project_slug: str, user_id: str, user_msg: str, assistant_msg: str):
    """Save messages to backend DB. Used by intent fast-path handlers only.
    The main chat flow persists messages via the backend chat endpoint."""
    try:
        headers = _backend_headers()
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
                headers=headers,
            )
            logger.debug(f"Persisted messages for user {user_id}")
    except Exception as e:
        logger.warning(f"Failed to persist messages: {e}")


def _backend_headers(person_id: int | None = None) -> dict:
    """Build common headers for backend API calls."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if INTERNAL_TOKEN:
        headers["X-Internal-Token"] = INTERNAL_TOKEN
    if person_id:
        headers["X-Person-Id"] = str(person_id)
    return headers


def strip_think_tags(text: str) -> str:
    """Remove <think> tags and their contents from text"""
    if not text:
        return ""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
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

        # Track activity (fire-and-forget)
        if person and person.get("id"):
            asyncio.create_task(_record_activity(person["id"]))

        # --- Verification gate (skip for synthetic updates from callbacks) ---
        if not is_synthetic and not _is_verified(person):
            await update.message.reply_text(t("verify_prompt", lang), parse_mode="HTML")
            return

        # --- Pending admin action (e.g. after clicking "Set Due Date" button) ---
        pending = context.user_data.pop("pending_action", None)
        if pending and pending.get("type") == "set_due_date":
            user_message = f"Update the due date for task {pending['task_id']} to {user_message}"

        # --- Resolve active project (per-user, session-scoped) ---
        if not is_synthetic:
            project_slug = await _ensure_project_or_prompt(update, context, person, lang)
            if not project_slug:
                return  # project selector shown, wait for callback
        else:
            project_slug = await _get_active_project(context, person)
            if not project_slug:
                return

        # --- Handler chain: classify intent and handle common actions directly ---
        # Skip for synthetic updates (callbacks) and messages with documents
        has_document = hasattr(update.message, 'document') and update.message.document
        if not is_synthetic and not has_document:
            handler_result = await try_handle(user_message, person, project_slug, lang=lang)
            if handler_result is not None:
                reply_text, buttons = handler_result
                reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
                await update.message.reply_text(
                    reply_text, parse_mode="HTML", reply_markup=reply_markup,
                )
                logger.info(f"Handler chain responded: {reply_text[:100]}...")
                asyncio.create_task(persist_messages(project_slug, user_id, user_message, reply_text))
                return

        # --- Route through backend chat endpoint (unified LLM orchestration) ---
        person_db_id = person.get("id") if person else None

        # Build request payload
        chat_payload = {
            "message": user_message,
            "user_id": user_id,
            "person_id": person_db_id,
            "source": "telegram",
        }

        # Include attachment info if file was recently uploaded
        upload_info = context.user_data.get("last_upload")
        if upload_info:
            chat_payload["attachment"] = {
                "filename": upload_info["filename"],
                "url": f"/uploads/{upload_info['filename']}",
                "size": upload_info.get("size", "unknown"),
            }

        headers = _backend_headers(person_id=person_db_id)
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{BACKEND_API}/projects/{project_slug}/chat",
                json=chat_payload,
                headers=headers,
            )

        if response.status_code != 200:
            logger.error(f"Backend chat failed: {response.status_code} {response.text[:300]}")
            await update.message.reply_text(t("error_generic", lang))
            return

        result = response.json()
        final_message = result.get("response", "")
        backend_files = result.get("files") or []

        # Strip any remaining think tags (safety net)
        final_message = strip_think_tags(final_message)

        if not final_message or final_message.isspace():
            final_message = "I processed your request but have no response to show."

        # Convert markdown to Telegram HTML
        final_message = _md_to_html(final_message)

        # Extract [BUTTONS]...[/BUTTONS] and create InlineKeyboard
        final_message, llm_buttons = _parse_buttons(final_message)

        reply_markup = InlineKeyboardMarkup(llm_buttons) if llm_buttons else None
        await update.message.reply_text(
            final_message, parse_mode="HTML", reply_markup=reply_markup,
        )
        logger.info(f"Sent response: {final_message[:100]}...")

        # Send any files returned by backend (e.g., report templates)
        for file_info in backend_files:
            try:
                fname = file_info["filename"]
                file_url = file_info.get("url")
                fpath = file_info.get("path")
                file_bytes = None

                # Prefer URL download (works across Docker containers)
                if file_url:
                    dl_url = f"{BACKEND_API}{file_url}" if file_url.startswith("/") else file_url
                    async with httpx.AsyncClient(timeout=30) as client:
                        resp = await client.get(dl_url)
                        resp.raise_for_status()
                        file_bytes = resp.content
                # Fallback to local file path (same-host only)
                elif fpath:
                    with open(fpath, "rb") as f:
                        file_bytes = f.read()

                if file_bytes:
                    from io import BytesIO
                    await context.bot.send_document(
                        chat_id=chat_id, document=BytesIO(file_bytes), filename=fname,
                    )
                    logger.info(f"Sent file: {fname} ({len(file_bytes)} bytes)")
                else:
                    logger.warning(f"No file content for {fname}")
            except Exception as e:
                logger.error(f"Failed to send file {file_info.get('filename')}: {e}")

        # Clear upload info after it's been used
        context.user_data.pop("last_upload", None)

    except Exception as e:
        error_msg = f"Error processing message: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await update.message.reply_text(t("error_generic", _user_lang(update)))


def _human_size(byte_count: int | None) -> str:
    """Format byte count as human-readable string."""
    if byte_count and byte_count > 1024 * 1024:
        return f"{byte_count / 1024 / 1024:.1f} MB"
    if byte_count and byte_count > 1024:
        return f"{byte_count / 1024:.0f} KB"
    if byte_count:
        return f"{byte_count} B"
    return "unknown"


async def _download_and_forward(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    file_id: str,
    filename: str,
    file_size: int | None,
) -> None:
    """Download a Telegram file, store metadata, and forward to unified chat.

    Works for documents, photos, and any future media type.  All
    intelligence (task matching, smart suggestions) lives in the backend
    chat endpoint — the gateway just downloads and forwards.
    """
    tg_id = str(update.effective_user.id)
    person = await resolve_person(tg_id, context)
    lang = _user_lang(update, person)
    if not _is_verified(person):
        await update.message.reply_text(t("verify_prompt", lang), parse_mode="HTML")
        return

    try:
        MEDIA_INBOX.mkdir(parents=True, exist_ok=True)
        file = await context.bot.get_file(file_id)
        file_path = MEDIA_INBOX / filename
        await file.download_to_drive(file_path)
        logger.info(f"Saved file to: {file_path}")

        # Store for handle_message → backend attachment payload
        context.user_data['last_upload'] = {
            'filename': filename,
            'path': str(file_path),
            'size': _human_size(file_size),
            'timestamp': update.message.date.isoformat(),
        }

        # Caption or simple default — backend LLM has full context to handle it
        text = update.message.caption or f"I uploaded a file: {filename}"

        synthetic = _SyntheticUpdate(
            message=update.message,
            effective_chat=update.effective_chat,
            effective_user=update.effective_user,
            text=text,
        )
        await handle_message(synthetic, context)

    except Exception as e:
        logger.error(f"Error handling file {filename}: {e}", exc_info=True)
        await update.message.reply_text(t("error_file", lang))


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document uploads — download and forward to unified chat."""
    doc = update.message.document
    logger.info(f"Received document: {doc.file_name}")
    await _download_and_forward(
        update, context,
        file_id=doc.file_id,
        filename=doc.file_name,
        file_size=doc.file_size,
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo uploads — download and forward to unified chat."""
    photo = update.message.photo[-1]  # highest resolution
    logger.info(f"Received photo: {photo.file_id} ({photo.width}x{photo.height})")
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = Path(photo.file_path).suffix if getattr(photo, 'file_path', None) else ".jpg"
    filename = f"photo_{timestamp}{ext}"
    await _download_and_forward(
        update, context,
        file_id=photo.file_id,
        filename=filename,
        file_size=photo.file_size,
    )


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
        # Download template directly from backend and send as document
        report_id = data.split(":")[1]
        try:
            # Try blank template first, fall back to original
            for endpoint in (f"/api/reports/{report_id}/blank-template", f"/api/reports/{report_id}/template-file"):
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(f"{BACKEND_API}{endpoint}")
                if resp.status_code == 200:
                    # Extract filename from content-disposition header
                    cd = resp.headers.get("content-disposition", "")
                    fname = "template.pdf"
                    if "filename=" in cd:
                        fname = cd.split("filename=")[-1].strip('"').strip("'")
                    from io import BytesIO
                    await context.bot.send_document(
                        chat_id=chat_id, document=BytesIO(resp.content), filename=fname,
                    )
                    logger.info(f"Sent template: {fname} ({len(resp.content)} bytes)")
                    return
            await query.message.reply_text(t("error_generic", lang))
        except Exception as e:
            logger.error(f"Failed to send template for report {report_id}: {e}")
            await query.message.reply_text(t("error_generic", lang))
        return

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
        cb_slug = await _get_active_project(context, person) or "unknown"
        asyncio.create_task(persist_messages(cb_slug, cb_uid, f"[Viewed task #{task_id}]", text))

    elif data.startswith("cmd:"):
        # Button-triggered commands (e.g. from help screen)
        cmd = data.split(":", 1)[1]
        cb_slug = await _get_active_project(context, person) or "unknown"
        if cmd == "tasks":
            text, buttons = await handle_tasks_command(person, cb_slug, lang=lang)
        elif cmd == "stats":
            text, buttons = await handle_stats_command(person, cb_slug, lang=lang)
        elif cmd == "help":
            text, buttons = format_help(lang=lang)
        else:
            text, buttons = f"Unknown command: {cmd}", []
        reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
        await query.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)
        cb_uid = f"person-{person['id']}" if person else tg_id
        asyncio.create_task(persist_messages(cb_slug, cb_uid, f"[/{cmd}]", text))

    elif data.startswith("sp:"):
        slug = data[3:]
        # Get project name from the button that was clicked
        name = slug
        if query.message and query.message.reply_markup:
            for row in query.message.reply_markup.inline_keyboard:
                for btn in row:
                    if btn.callback_data == data:
                        name = btn.text
                        break
        context.user_data["active_project"] = {"slug": slug, "name": name}
        await query.message.reply_text(
            t("project_selected", lang, name=name), parse_mode="HTML",
        )

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
                    person_projects = await _get_person_projects(person["id"]) if person and person.get("id") else []
                    text, buttons = format_welcome(person_projects, lang=lang)
                else:
                    text = (
                        f"{t('welcome_title', lang)}\n\n"
                        f"{t('welcome_need_code', lang)}"
                    )
                    buttons = []

            reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)

            user_id = f"person-{person['id']}" if person else tg_id
            cmd_slug = await _get_active_project(context, person) or "unknown"
            asyncio.create_task(persist_messages(cmd_slug, user_id, f"/start {' '.join(args)}".strip(), text))
            return

        # --- Verification gate for all other commands ---
        if not _is_verified(person):
            await update.message.reply_text(t("verify_prompt", lang), parse_mode="HTML")
            return

        user_id = f"person-{person['id']}" if person else tg_id
        cmd_slug = await _get_active_project(context, person) or "unknown"

        if command == "help":
            text, buttons = format_help(lang=lang)
        elif command == "tasks":
            text, buttons = await handle_tasks_command(person, cmd_slug, lang=lang)
        elif command == "projects":
            text, buttons = await handle_projects_command(person, lang=lang)
        elif command == "stats":
            text, buttons = await handle_stats_command(person, cmd_slug, lang=lang)
        elif command == "switch":
            # Show project selector
            projects = await _get_person_projects(person["id"]) if person else []
            if not projects:
                text, buttons = t("no_projects", lang), []
            else:
                btns = [[InlineKeyboardButton(
                    p["name"], callback_data=f"sp:{p['slug']}"
                )] for p in projects]
                await update.message.reply_text(
                    t("select_project", lang), reply_markup=InlineKeyboardMarkup(btns),
                )
                return
        else:
            text, buttons = f"Unknown command: /{command}", []

        reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)
        asyncio.create_task(persist_messages(cmd_slug, user_id, f"/{command}", text))

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
    logger.info("Starting Vantage Telegram Gateway (unified backend mode)...")
    logger.info(f"Backend API: {BACKEND_API}")
    logger.info("LLM orchestration delegated to backend chat endpoint")

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

    # Add handlers — command handlers first (most specific), then text, then documents, then photos
    application.add_handler(CommandHandler(["start", "help", "tasks", "projects", "stats", "lang", "switch"], handle_command))
    application.add_handler(CommandHandler("open", handle_open_command))
    application.add_handler(CommandHandler("webapp", handle_webapp_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Start bot
    logger.info("Bot started successfully. Ready to receive messages.")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
