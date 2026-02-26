"""Handler chain: intent classifier + direct tool execution.

Layer 1 (slash commands) is routed by python-telegram-bot's CommandHandler
in gateway.py — this module handles Layer 2 (natural language classification).

ALL data queries are person-scoped via direct API calls — never use
unauthenticated script tools for user-facing data.
"""

import logging
import re as _re

import httpx

from config import (
    LLM_PROVIDER, VLLM_URL, VLLM_MODEL, ANTHROPIC_API_KEY,
    CLAUDE_MODEL, CLASSIFIER_MODEL, CLASSIFIER_MAX_TOKENS, DEFAULT_PROJECT,
    BACKEND_API,
)
from formatters import (
    format_task_list,
    format_project_list,
    format_project_stats,
    format_help,
    format_greeting,
)
from i18n import t

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared HTTP helper — person-scoped API calls
# ---------------------------------------------------------------------------

_HTTP_TIMEOUT = 10.0


async def _api_get(path: str, params: dict | None = None) -> list | dict | None:
    """GET request to backend API. Returns parsed JSON or None on failure."""
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.get(f"{BACKEND_API}{path}", params=params)
            if resp.status_code == 200:
                return resp.json()
            logger.warning(f"API {path} returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"API {path} failed: {e}")
    return None


# ---------------------------------------------------------------------------
# Intent classification prompt
# ---------------------------------------------------------------------------

CLASSIFY_PROMPT = """Classify the user's message into exactly one intent.
Respond with ONLY the intent name, nothing else.

Intents:
- show_tasks: user wants to see their tasks, task list, what's due, overdue items
- show_projects: user wants to see projects list
- project_stats: user wants project status, summary, how the project is going, progress
- help: user asks what the bot CAN DO or how to USE THE BOT (e.g. "what can you do?", "commands", "help"). ONLY for bot-capability questions.
- unknown: anything else — including requests for help WITH something specific (e.g. "help me fill out X", "can you help me with task 5", "help me understand this"), complex questions, multi-step requests, creating/updating things, task-specific questions, file/document actions

IMPORTANT: "help me [do something]" or "can you help me with [X]" is NOT the help intent — it is unknown. The help intent is ONLY for "what can this bot do?" type questions.

User message: {message}"""


# ---------------------------------------------------------------------------
# Lightweight LLM call for classification (no tools, minimal tokens)
# ---------------------------------------------------------------------------

async def _classify_claude(text: str) -> str:
    """Classify intent using Claude API."""
    import anthropic

    model = CLASSIFIER_MODEL or CLAUDE_MODEL
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    response = await client.messages.create(
        model=model,
        max_tokens=CLASSIFIER_MAX_TOKENS,
        temperature=0,
        messages=[{"role": "user", "content": CLASSIFY_PROMPT.format(message=text)}],
    )

    result = response.content[0].text.strip().lower()
    return result


async def _classify_vllm(text: str) -> str:
    """Classify intent using vLLM (OpenAI-compatible)."""
    model = CLASSIFIER_MODEL or VLLM_MODEL
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": CLASSIFY_PROMPT.format(message=text)}],
        "temperature": 0,
        "max_tokens": CLASSIFIER_MAX_TOKENS,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(VLLM_URL, json=payload)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"].strip().lower()


async def classify_intent(text: str) -> str:
    """Classify user message intent. Returns intent name string."""
    try:
        if LLM_PROVIDER == "claude":
            return await _classify_claude(text)
        else:
            return await _classify_vllm(text)
    except Exception as e:
        logger.warning(f"Intent classification failed: {e}")
        return "unknown"


# ---------------------------------------------------------------------------
# Intent handlers — all person-scoped via direct API calls
# ---------------------------------------------------------------------------

VALID_INTENTS = {"show_tasks", "show_projects", "project_stats", "help", "greeting"}


async def handle_greeting(
    person: dict | None, project_slug: str, lang: str = "en",
) -> tuple[str, list]:
    """Fetch person's upcoming tasks + projects and return a rich greeting."""
    person_name = (person or {}).get("name", "")
    first_name = person_name.split()[0] if person_name else ""
    tasks = []
    projects = []

    person_id = (person or {}).get("id")
    if person_id:
        tasks = await _api_get(
            f"/people/{person_id}/tasks",
            {"days": 7, "include_no_due": "true"},
        ) or []
        projects = await _api_get(f"/people/{person_id}/projects") or []

    return format_greeting(first_name, tasks, projects, lang=lang)


async def handle_intent(
    intent: str, person: dict | None, project_slug: str, lang: str = "en",
) -> tuple[str, list] | None:
    """Execute the right tool for a classified intent and format the result.

    Returns (html_text, button_rows) or None if intent is unknown.
    """
    if intent not in VALID_INTENTS:
        return None

    if intent == "greeting":
        return await handle_greeting(person, project_slug, lang=lang)

    if intent == "help":
        return format_help(lang=lang)

    if intent == "show_tasks":
        return await handle_tasks_command(person, project_slug, lang=lang)

    if intent == "show_projects":
        return await handle_projects_command(person, lang=lang)

    if intent == "project_stats":
        return await handle_stats_command(person, project_slug, lang=lang)

    return None


# ---------------------------------------------------------------------------
# Regex fast-path — matched before the LLM classifier
# ---------------------------------------------------------------------------

_TASK_PATTERNS = _re.compile(
    r"(?:show|list|view|get|what(?:'s| is| are)?|display|see|check)"
    r".*\b(?:tasks?|to.?do|due|overdue|assigned)\b"
    r"|^my tasks?\s*$"
    r"|^tasks?\s*$",
    _re.IGNORECASE,
)
_PROJECT_PATTERNS = _re.compile(
    r"(?:show|list|view|get|what(?:'s| is| are)?|display|see)"
    r".*\bprojects?\b"
    r"|^projects?\s*$",
    _re.IGNORECASE,
)
_STATS_PATTERNS = _re.compile(
    r"(?:how(?:'s| is)|what(?:'s| is)|show|get)"
    r".*\b(?:project|progress|status|stats?|statistics|going|doing)\b"
    r"|^stats?\s*$",
    _re.IGNORECASE,
)
_HELP_PATTERNS = _re.compile(
    r"^(?:what can you do|how (?:do|can) I use (?:this|you)|commands?|features?|/help)\s*[?!.]?\s*$"
    r"|^help\s*[?!.]?\s*$",
    _re.IGNORECASE,
)
_GREETING_PATTERNS = _re.compile(
    r"^(?:hi|hello|hey|yo|sup|good\s*(?:morning|afternoon|evening)|howdy|hola|what'?s?\s*up)\s*[!.\?]?\s*$",
    _re.IGNORECASE,
)


def _fast_classify(text: str) -> str | None:
    """Regex-based fast classification. Returns intent or None to fall through."""
    text = text.strip()
    if _GREETING_PATTERNS.search(text):
        return "greeting"
    if _TASK_PATTERNS.search(text):
        return "show_tasks"
    if _PROJECT_PATTERNS.search(text):
        return "show_projects"
    if _STATS_PATTERNS.search(text):
        return "project_stats"
    if _HELP_PATTERNS.search(text):
        return "help"
    return None


# ---------------------------------------------------------------------------
# Entry point — called from gateway.py handle_message()
# ---------------------------------------------------------------------------

async def try_handle(
    text: str, person: dict | None, project_slug: str, lang: str = "en",
) -> tuple[str, list] | None:
    """Classify intent and handle if recognized.

    Returns (html_text, button_rows) if handled, None to fall through to LLM.
    """
    # Fast regex classification first — avoids LLM round-trip for common phrases
    intent = _fast_classify(text)
    if intent:
        logger.info(f"Fast-classified intent: '{intent}' for message: '{text[:80]}'")
    else:
        intent = await classify_intent(text)
        logger.info(f"LLM-classified intent: '{intent}' for message: '{text[:80]}'")

    result = await handle_intent(intent, person, project_slug, lang=lang)
    if result is not None:
        logger.info(f"Handled by intent '{intent}' — skipping agentic LLM loop")
    return result


# ---------------------------------------------------------------------------
# Command handlers — person-scoped, called for /commands AND button callbacks
# ---------------------------------------------------------------------------

async def handle_tasks_command(
    person: dict | None, project_slug: str, lang: str = "en",
) -> tuple[str, list]:
    """Show person's assigned tasks across all their projects."""
    person_id = (person or {}).get("id")
    if person_id:
        tasks = await _api_get(
            f"/people/{person_id}/tasks",
            {"days": 365, "include_no_due": "true"},
        )
        if isinstance(tasks, list):
            return format_task_list(tasks, title=t("your_tasks", lang), lang=lang)
    return t("no_data", lang, item=t("tasks_title", lang)), []


async def handle_projects_command(
    person: dict | None, lang: str = "en",
) -> tuple[str, list]:
    """Show projects this person is a member of."""
    person_id = (person or {}).get("id")
    if person_id:
        projects = await _api_get(f"/people/{person_id}/projects")
        if isinstance(projects, list):
            return format_project_list(projects, lang=lang)
    return t("no_data", lang, item=t("projects_title", lang)), []


async def handle_stats_command(
    person: dict | None, project_slug: str, lang: str = "en",
) -> tuple[str, list]:
    """Show project statistics scoped to this person's tasks."""
    person_id = (person or {}).get("id")
    if person_id:
        # Use person's task data to build stats
        tasks = await _api_get(
            f"/people/{person_id}/tasks",
            {"days": 365, "include_no_due": "true"},
        )
        if isinstance(tasks, list):
            # Filter to the requested project
            proj_tasks = [tk for tk in tasks if tk.get("project_slug") == project_slug]
            from datetime import date, timedelta
            today = date.today()
            end_of_week = today + timedelta(days=(6 - today.weekday()))
            stats = {
                "total": len(proj_tasks),
                "in_progress": sum(1 for tk in proj_tasks if tk.get("status") == "in_progress"),
                "due_today": sum(1 for tk in proj_tasks if tk.get("due_date") and tk["due_date"][:10] == str(today)),
                "this_week": sum(
                    1 for tk in proj_tasks
                    if tk.get("due_date") and str(today) <= tk["due_date"][:10] <= str(end_of_week)
                ),
                "completed": 0,  # person endpoint excludes completed tasks
            }
            return format_project_stats(stats, project_slug, lang=lang)
    return t("fetch_stats_error", lang, slug=project_slug), []
