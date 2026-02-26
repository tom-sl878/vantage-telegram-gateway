"""Format tool results into Telegram HTML + inline buttons."""

import re
from datetime import datetime

from telegram import InlineKeyboardButton

from i18n import t


def _format_label(value: str) -> str:
    """Format raw DB values for display: 'not_started' → 'Not Started'."""
    return value.replace("_", " ").title() if value else ""


def _clean_markdown(text: str) -> str:
    """Convert markdown to Telegram HTML for readable display."""
    text = re.sub(r'^#{1,6}\s+(.+)$', r'\n<b>\1</b>', text, flags=re.MULTILINE)  # ## Headers → bold
    text = re.sub(r'- \[ \] ', '- ', text)   # - [ ] unchecked
    text = re.sub(r'- \[x\] ', '- ', text)   # - [x] checked
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)  # **bold** → HTML bold
    text = re.sub(r'(?<!\w)\*(.+?)\*(?!\w)', r'<i>\1</i>', text)  # *italic* → HTML italic
    text = re.sub(r'`(.+?)`', r'\1', text)         # `code` → plain
    text = re.sub(r'\n{3,}', '\n\n', text)   # collapse blank lines
    return text.strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(raw: str | None) -> str:
    """Parse ISO datetime string to 'Mar 15' or 'Mar 15, 2026' format."""
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw)
        today = datetime.now()
        if dt.year == today.year:
            return dt.strftime("%b %d")
        return dt.strftime("%b %d, %Y")
    except (ValueError, TypeError):
        return str(raw)


def _status_label(status: str | None) -> str:
    """Single clean indicator for task status."""
    return {
        "complete": "\u2705",
        "in_progress": "\u25b6",
        "blocked": "\u26d4",
        "todo": "\u2022",
    }.get((status or "").lower(), "\u2022")


# ---------------------------------------------------------------------------
# Formatters — each returns (html_text, button_rows)
# ---------------------------------------------------------------------------

def format_task_list(
    tasks: list[dict], title: str = "", lang: str = "en",
) -> tuple[str, list[list[InlineKeyboardButton]]]:
    """Format a list of tasks into HTML. No per-task buttons — use detail view."""
    if not title:
        title = t("tasks_title", lang)
    if not tasks:
        return f"<b>{title}</b>\n\n{t('no_tasks', lang)}", []

    count_key = "task_count" if len(tasks) == 1 else "task_count_plural"
    lines = [f"<b>{title}</b>  ({t(count_key, lang, n=len(tasks))})\n"]

    for tk in tasks[:15]:  # cap at 15
        mark = _status_label(tk.get("status"))
        due = _parse_date(tk.get("due_date"))
        due_str = f"  \u2014 {due}" if due else ""
        tid = tk.get("id", "")

        lines.append(f"{mark} <code>#{tid}</code>  <b>{tk['title']}</b>{due_str}")

    if len(tasks) > 15:
        lines.append(f"\n<i>{t('and_n_more', lang, n=len(tasks) - 15)}</i>")

    lines.append(f"\n{t('task_list_prompt', lang)}")

    return "\n".join(lines), []


def format_project_list(
    projects: list[dict], lang: str = "en",
) -> tuple[str, list[list[InlineKeyboardButton]]]:
    """Format project list into HTML + per-project buttons."""
    title = t("projects_title", lang)
    if not projects:
        return f"<b>{title}</b>\n\n{t('no_projects', lang)}", []

    lines = [f"<b>{title}</b>  ({len(projects)})\n"]
    buttons: list[list[InlineKeyboardButton]] = []

    for p in projects:
        status_icon = "\U0001f7e2" if p.get("status") == "active" else "\u26aa"
        due = _parse_date(p.get("due_date"))
        due_str = f"  \U0001f4c5 {due}" if due else ""
        client = p.get("client") or ""
        client_str = f"  \u2014 {client}" if client else ""
        task_count = p.get("task_count")
        count_str = f"  ({task_count} {t('tasks_title', lang).lower()})" if task_count else ""

        lines.append(f"{status_icon} <b>{p['name']}</b>{client_str}{due_str}{count_str}")

        buttons.append([
            InlineKeyboardButton(t("btn_tasks", lang), callback_data=f"view_tasks:{p['slug']}"),
        ])

    return "\n".join(lines), buttons


def format_project_stats(
    stats: dict, slug: str, lang: str = "en",
) -> tuple[str, list[list[InlineKeyboardButton]]]:
    """Format project stats into HTML + action buttons."""
    total = stats.get("total", 0)
    in_progress = stats.get("in_progress", 0)
    due_today = stats.get("due_today", 0)
    this_week = stats.get("this_week", 0)
    completed_count = stats.get("completed", 0)

    lines = [
        f"<b>{t('stats_title', lang)}</b>  <code>{slug}</code>\n",
        f"\U0001f4cb {t('stats_total', lang)} <b>{total}</b>",
        f"\U0001f7e1 {t('stats_in_progress', lang)} <b>{in_progress}</b>",
        f"\U0001f534 {t('due_today', lang)} <b>{due_today}</b>",
        f"\U0001f4c5 {t('this_week', lang)} <b>{this_week}</b>",
        f"\u2705 {t('completed', lang)} <b>{completed_count}</b>",
    ]

    buttons = [
        [
            InlineKeyboardButton(t("btn_view_tasks", lang), callback_data=f"view_tasks:{slug}"),
            InlineKeyboardButton(t("btn_overdue", lang), callback_data=f"view_overdue:{slug}"),
        ]
    ]

    return "\n".join(lines), buttons


def format_task_detail(
    task: dict, lang: str = "en",
) -> tuple[str, list[list[InlineKeyboardButton]]]:
    """Format a single task detail into HTML + action buttons."""
    mark = _status_label(task.get("status"))
    due = _parse_date(task.get("due_date"))
    assignee = task.get("assignee_name") or t("unassigned", lang)

    lines = [
        f"{mark} <b>{task['title']}</b>\n",
        f"{t('status_label', lang)} {_format_label(task.get('status', 'unknown'))}",
        f"{t('priority_label', lang)} {_format_label(task.get('priority', 'none'))}",
        f"{t('assignee_label', lang)} {assignee}",
    ]
    if due:
        lines.append(f"{t('due_label', lang)} {due}")

    # Topic (section)
    if task.get("topic_name"):
        lines.append(f"Section: {task['topic_name']}")

    # Scope (from task description)
    if task.get("description"):
        desc = _clean_markdown(task["description"])
        lines.append(f"\n<b>Scope</b>\n{desc}")

    # Deliverable info (expected document)
    deliverable = task.get("deliverable")
    if deliverable:
        lines.append(f"\n<b>Expected Deliverable</b>")
        lines.append(f"- {deliverable['title']}")
        if deliverable.get("format"):
            lines.append(f"- Format: {_format_label(deliverable['format'])}")
        if deliverable.get("page_limit"):
            lines.append(f"- Page limit: {deliverable['page_limit']}")
        if deliverable.get("description"):
            ddesc = _clean_markdown(deliverable["description"])
            lines.append(f"  {ddesc}")

    # Requirements / acceptance criteria
    requirements = task.get("requirements", [])
    if requirements:
        lines.append(f"\n<b>Acceptance Criteria</b>")
        for req in requirements:
            rtype = f" ({_format_label(req['type'])})" if req.get("type") and req["type"] != "mandatory" else ""
            lines.append(f"- {req['title']}{rtype}")
            if req.get("source"):
                lines.append(f"  <i>Source: {req['source']}</i>")

    # Source excerpt (RFP reference)
    if task.get("source_excerpt"):
        excerpt = task["source_excerpt"][:200]
        if len(task["source_excerpt"]) > 200:
            excerpt += "..."
        lines.append(f"\n<b>RFP Reference</b>\n<i>{excerpt}</i>")

    # Report-specific info (submission guide, description, template)
    ri = task.get("report_info")
    if ri:
        if ri.get("report_description"):
            rdesc = _clean_markdown(ri["report_description"])
            lines.append(f"\n<b>{t('report_description', lang)}</b>\n{rdesc}")
        if ri.get("submission_guide"):
            guide = _clean_markdown(ri["submission_guide"])
            # Truncate long guides for Telegram message limits
            if len(guide) > 1500:
                guide = guide[:1500] + "…"
            lines.append(f"\n<b>{t('submission_guide', lang)}</b>\n{guide}")
        if ri.get("has_template"):
            fname = ri.get("template_file", "template")
            lines.append(f"\n📎 {t('template_available', lang, file=fname)}")

    task_id = task["id"]
    status = task.get("status", "")
    buttons: list[list[InlineKeyboardButton]] = []

    # Template download button for report tasks
    if ri and ri.get("has_template"):
        buttons.append([
            InlineKeyboardButton(
                f"📎 {t('btn_get_template', lang)}",
                callback_data=f"get_template:{ri['report_id']}",
            ),
        ])
    if status == "complete":
        buttons.append([
            InlineKeyboardButton(t("btn_reopen", lang), callback_data=f"reopen_task:{task_id}"),
        ])
    elif status == "in_progress":
        buttons.append([
            InlineKeyboardButton(t("btn_complete", lang), callback_data=f"complete_task:{task_id}"),
        ])
    else:
        buttons.append([
            InlineKeyboardButton(t("btn_start", lang), callback_data=f"start_task:{task_id}"),
            InlineKeyboardButton(t("btn_complete", lang), callback_data=f"complete_task:{task_id}"),
        ])

    return "\n".join(lines), buttons


def format_help(lang: str = "en") -> tuple[str, list[list[InlineKeyboardButton]]]:
    """Static help text + action buttons."""
    text = (
        f"{t('help_title', lang)}\n\n"
        f"{t('help_commands', lang)}\n"
        f"{t('help_tasks_cmd', lang)}\n"
        f"{t('help_projects_cmd', lang)}\n"
        f"{t('help_stats_cmd', lang)}\n"
        f"{t('help_help_cmd', lang)}\n"
        f"{t('help_open_cmd', lang)}\n"
        f"{t('help_lang_cmd', lang)}\n\n"
        f"{t('help_natural', lang)}\n"
        f"\u2022 {t('help_ex1', lang)}\n"
        f"\u2022 {t('help_ex2', lang)}\n"
        f"\u2022 {t('help_ex3', lang)}\n"
        f"\u2022 {t('help_ex4', lang)}\n\n"
        f"{t('help_footer', lang)}"
    )
    buttons = [
        [
            InlineKeyboardButton(t("btn_tasks", lang), callback_data="cmd:tasks"),
            InlineKeyboardButton(t("btn_stats", lang), callback_data="cmd:stats"),
        ]
    ]
    return text, buttons


def format_greeting(
    first_name: str,
    tasks: list[dict],
    projects: list[dict],
    lang: str = "en",
) -> tuple[str, list[list[InlineKeyboardButton]]]:
    """Format a rich greeting with urgent tasks, project summary, and action buttons."""
    # Greeting line
    if first_name:
        lines = [t("greeting_hello_name", lang, name=first_name)]
    else:
        lines = [t("greeting_hello", lang)]

    # Urgent tasks due this week (already sorted by due_date from API)
    if tasks:
        lines.append("")
        lines.append(t("greeting_urgent_title", lang))
        for tk in tasks[:8]:
            mark = _status_label(tk.get("status"))
            due = _parse_date(tk.get("due_date"))
            due_str = f"  \u2014 {due}" if due else ""
            tid = tk.get("id", "")
            lines.append(f"{mark} <code>#{tid}</code>  {tk['title']}{due_str}")
        if len(tasks) > 8:
            lines.append(f"<i>{t('and_n_more', lang, n=len(tasks) - 8)}</i>")

    # Project summary
    if projects:
        lines.append("")
        lines.append(t("greeting_projects_title", lang))
        for p in projects:
            status_icon = "\U0001f7e2" if p.get("status") == "active" else "\u26aa"
            # Count how many of the person's tasks belong to this project
            proj_task_count = sum(
                1 for tk in tasks if tk.get("project_slug") == p.get("slug")
            )
            count_str = f" \u2014 {proj_task_count} {t('greeting_tasks_due', lang)}" if proj_task_count else ""
            lines.append(f"{status_icon} <b>{p['name']}</b>{count_str}")

    # Closing line
    lines.append("")
    lines.append(t("greeting_closing", lang))

    # Action buttons
    buttons: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(t("btn_view_tasks", lang), callback_data="cmd:tasks"),
            InlineKeyboardButton(t("btn_help", lang), callback_data="cmd:help"),
        ],
    ]

    return "\n".join(lines), buttons


def format_welcome(
    projects: list[dict], lang: str = "en",
) -> tuple[str, list[list[InlineKeyboardButton]]]:
    """Welcome message + project list."""
    lines = [
        f"{t('welcome_greeting', lang)}\n",
        f"{t('welcome_desc', lang)}\n",
    ]

    buttons: list[list[InlineKeyboardButton]] = []

    if projects:
        lines.append(f"{t('your_projects', lang, n=len(projects))}\n")
        for p in projects:
            status_icon = "\U0001f7e2" if p.get("status") == "active" else "\u26aa"
            lines.append(f"{status_icon} {p['name']}")
            buttons.append([
                InlineKeyboardButton(f"\U0001f4cb {p['name']}", callback_data=f"view_tasks:{p['slug']}"),
            ])
    else:
        lines.append(t("no_projects_upload", lang))

    buttons.append([
        InlineKeyboardButton(t("btn_help", lang), callback_data="cmd:help"),
    ])

    return "\n".join(lines), buttons
