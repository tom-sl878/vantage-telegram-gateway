"""Tool definitions and execution for Vantage bot"""
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Any

import httpx

from config import TASK_SCRIPTS_DIR, RFP_SCRIPTS_DIR, PROJECT_SCRIPTS_DIR, REPORT_SCRIPTS_DIR, BACKEND_API

# OpenAI format tool definitions
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_tasks",
            "description": "List tasks for a project, optionally filtered by urgency (due_today, due_this_week, overdue, upcoming, completed, all)",
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
                        "description": "Filter tasks by urgency. Defaults to 'all'"
                    }
                },
                "required": ["project_slug"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_task",
            "description": "Get a single task by its ID with full details",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "Task identifier"
                    }
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "preview_file",
            "description": "Preview the most recently uploaded file. Returns file metadata (name, size, type), detected language, and a text preview (first ~2000 chars). Use this when a user uploads a file without context to understand what it contains before suggesting which task or deliverable it might be for.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_task_document",
            "description": "Analyze an uploaded document for task compatibility WITHOUT completing the task. Returns language detection, comprehensive analysis, and compatibility assessment. Use this BEFORE completing to show user analysis and ask for approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "Task identifier to analyze document for"
                    }
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Complete a task with full file upload workflow. Fetches task and deliverable details, finds latest uploaded file, validates content, creates document record, links document to deliverable, and marks task complete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "Task identifier to complete"
                    }
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a single task with specified details",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic_id": {
                        "type": "integer",
                        "description": "Topic ID to create task under"
                    },
                    "title": {
                        "type": "string",
                        "description": "Task title/description"
                    },
                    "due": {
                        "type": "string",
                        "description": "Due date in YYYY-MM-DD format",
                        "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                    },
                    "assignee_id": {
                        "type": "integer",
                        "description": "Team member ID to assign task to"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["critical", "high", "medium", "low"],
                        "description": "Task priority level"
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed task description"
                    },
                    "source": {
                        "type": "string",
                        "description": "Source reference (e.g., 'Section 2.1')"
                    },
                    "deliverable_id": {
                        "type": "integer",
                        "description": "Deliverable ID to link task to"
                    }
                },
                "required": ["topic_id", "title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Update an existing task's fields (title, due date, status, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "Task identifier to update"
                    },
                    "title": {
                        "type": "string",
                        "description": "New task title"
                    },
                    "due": {
                        "type": "string",
                        "description": "New due date in YYYY-MM-DD format"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["todo", "in_progress", "blocked", "complete"],
                        "description": "New task status"
                    }
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Delete a task by its ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "Task identifier to delete"
                    }
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "process_document",
            "description": "Process a document (RFP, bidding guidelines, contract, specification, etc.) and create or update a project with topics, requirements, deliverables, and tasks. Automatically uses the most recently uploaded file or accepts a specific file path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Optional specific file path. If not provided, uses 'latest' to process most recent upload."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_project_stats",
            "description": "Get project statistics including task counts, completion rates, and deadlines",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_slug": {
                        "type": "string",
                        "description": "Project identifier slug"
                    }
                },
                "required": ["project_slug"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_project",
            "description": "Delete a project by its slug. Use when user wants to replace a duplicate project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_slug": {
                        "type": "string",
                        "description": "Project slug to delete"
                    }
                },
                "required": ["project_slug"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_projects",
            "description": "List all available projects. Use when user asks 'show me projects', 'list projects', 'my tasks' (to find current project), or when project slug is unknown.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_task_comment",
            "description": "Add a comment/note to a task. Comments are appended to the task description with timestamp. Use when user wants to add notes, comments, or additional information to a task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "Task identifier to add comment to"
                    },
                    "comment": {
                        "type": "string",
                        "description": "The comment text to add"
                    }
                },
                "required": ["task_id", "comment"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task_document",
            "description": "Remove a document from a task's deliverable and delete it. Use when user wants to remove or delete an uploaded file from a task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "Task identifier"
                    },
                    "document_id": {
                        "type": "integer",
                        "description": "Document ID to delete"
                    }
                },
                "required": ["task_id", "document_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reopen_task",
            "description": "Reopen a completed task by changing its status from complete to in_progress. Use when user wants to reopen or undo task completion.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "Task identifier to reopen"
                    }
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "request_action",
            "description": "Request an action from a project admin when the current user cannot perform it themselves. Use when user asks to set due dates, change priority, reassign tasks, or any admin-level action. Sends a notification with actionable buttons to the project admin via Telegram.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "Task ID the request is about"
                    },
                    "action_type": {
                        "type": "string",
                        "enum": ["set_due_date", "change_priority", "reassign", "other"],
                        "description": "Type of action being requested"
                    },
                    "message": {
                        "type": "string",
                        "description": "Message explaining the request to the admin"
                    }
                },
                "required": ["task_id", "action_type", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_report_template",
            "description": "Get template info, fillable fields, and download links for a report. Use when submitter asks about report format, what to submit, or wants to fill in data via chat.",
            "parameters": {
                "type": "object",
                "properties": {
                    "report_id": {
                        "type": "integer",
                        "description": "Report identifier"
                    }
                },
                "required": ["report_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_reports",
            "description": "List all reports for a project with template status. Use when user asks about reports, report submissions, or available templates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_slug": {
                        "type": "string",
                        "description": "Project identifier slug"
                    }
                },
                "required": ["project_slug"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_report_template",
            "description": "Update or replace the template for a report. Uses the most recently uploaded file. Admin only.",
            "parameters": {
                "type": "object",
                "properties": {
                    "report_id": {
                        "type": "integer",
                        "description": "Report identifier"
                    },
                    "handling": {
                        "type": "string",
                        "enum": ["blank", "reference"],
                        "description": "How to handle the template: 'blank' removes data fields, 'reference' keeps as-is"
                    }
                },
                "required": ["report_id", "handling"]
            }
        }
    }
]


def execute_tool(tool_name: str, arguments: Dict[str, Any], actor: str | None = None) -> Dict[str, Any]:
    """Execute a tool by name with given arguments.

    Args:
        actor: Person name to pass as VANTAGE_ACTOR env var for activity logging.
    """
    _env = os.environ.copy()
    if actor:
        _env["VANTAGE_ACTOR"] = actor
    # Always pass the internal token so scripts can authenticate with backend
    if "VANTAGE_INTERNAL_TOKEN" not in _env:
        from config import INTERNAL_TOKEN
        if INTERNAL_TOKEN:
            _env["VANTAGE_INTERNAL_TOKEN"] = INTERNAL_TOKEN

    try:
        if tool_name == "get_tasks":
            cmd = [
                "python3",
                str(TASK_SCRIPTS_DIR / "tasks.py"),
                "list",
                arguments["project_slug"]
            ]
            if "filter" in arguments:
                cmd.extend(["--filter", arguments["filter"]])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=_env)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "get_task":
            cmd = ["python3", str(TASK_SCRIPTS_DIR / "tasks.py"), "get", str(arguments["task_id"])]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=_env)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "preview_file":
            cmd = ["python3", str(TASK_SCRIPTS_DIR / "preview_file.py"), "latest"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=_env)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "analyze_task_document":
            cmd = ["python3", str(TASK_SCRIPTS_DIR / "analyze_task_document.py"), str(arguments["task_id"])]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=_env)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "complete_task":
            cmd = ["python3", str(TASK_SCRIPTS_DIR / "complete_task.py"), str(arguments["task_id"])]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=_env)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "create_task":
            cmd = ["python3", str(TASK_SCRIPTS_DIR / "tasks.py"), "create"]
            cmd.extend(["--topic-id", str(arguments["topic_id"])])
            cmd.extend(["--title", arguments["title"]])
            if "due" in arguments:
                cmd.extend(["--due", arguments["due"]])
            if "assignee_id" in arguments:
                cmd.extend(["--assignee-id", str(arguments["assignee_id"])])
            if "priority" in arguments:
                cmd.extend(["--priority", arguments["priority"]])
            if "description" in arguments:
                cmd.extend(["--description", arguments["description"]])
            if "source" in arguments:
                cmd.extend(["--source", arguments["source"]])
            if "deliverable_id" in arguments:
                cmd.extend(["--deliverable-id", str(arguments["deliverable_id"])])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=_env)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "update_task":
            cmd = ["python3", str(TASK_SCRIPTS_DIR / "tasks.py"), "update", str(arguments["task_id"])]
            if "title" in arguments:
                cmd.extend(["--title", arguments["title"]])
            if "due" in arguments:
                cmd.extend(["--due", arguments["due"]])
            if "status" in arguments:
                cmd.extend(["--status", arguments["status"]])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=_env)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "delete_task":
            cmd = ["python3", str(TASK_SCRIPTS_DIR / "tasks.py"), "delete", str(arguments["task_id"])]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=_env)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "process_document":
            file_path = arguments.get("file_path", "latest")
            cmd = ["python3", str(RFP_SCRIPTS_DIR / "process_document.py"), file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=_env)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "get_project_stats":
            cmd = ["python3", str(PROJECT_SCRIPTS_DIR / "projects.py"), "stats", arguments["project_slug"]]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=_env)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "delete_project":
            cmd = ["python3", str(PROJECT_SCRIPTS_DIR / "projects.py"), "delete", arguments["project_slug"]]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=_env)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "get_projects":
            cmd = ["python3", str(PROJECT_SCRIPTS_DIR / "projects.py"), "list"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=_env)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "add_task_comment":
            cmd = ["python3", str(TASK_SCRIPTS_DIR / "add_task_comment.py"), str(arguments["task_id"]), arguments["comment"]]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=_env)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "delete_task_document":
            cmd = ["python3", str(TASK_SCRIPTS_DIR / "delete_task_document.py"), str(arguments["task_id"]), str(arguments["document_id"])]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=_env)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "reopen_task":
            cmd = ["python3", str(TASK_SCRIPTS_DIR / "reopen_task.py"), str(arguments["task_id"])]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=_env)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "request_action":
            headers = {}
            if _env.get("VANTAGE_INTERNAL_TOKEN"):
                headers["X-Internal-Token"] = _env["VANTAGE_INTERNAL_TOKEN"]
            if _env.get("VANTAGE_ACTOR"):
                headers["X-Actor"] = _env["VANTAGE_ACTOR"]
            resp = httpx.post(
                f"{BACKEND_API}/tasks/{arguments['task_id']}/request-action",
                json={
                    "requester_id": arguments.get("requester_id", 0),
                    "action_type": arguments.get("action_type", "other"),
                    "message": arguments.get("message", ""),
                },
                headers=headers,
                timeout=10.0,
            )
            return resp.json() if resp.status_code == 200 else {"error": resp.text}

        elif tool_name == "get_report_template":
            cmd = ["python3", str(REPORT_SCRIPTS_DIR / "get_report_template.py"), str(arguments["report_id"])]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=_env)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "get_reports":
            cmd = ["python3", str(REPORT_SCRIPTS_DIR / "get_reports.py"), arguments["project_slug"]]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=_env)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "update_report_template":
            cmd = ["python3", str(REPORT_SCRIPTS_DIR / "update_report_template.py"),
                   str(arguments["report_id"]), arguments.get("handling", "blank")]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=_env)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except subprocess.TimeoutExpired:
        return {"error": f"Tool {tool_name} timed out"}
    except Exception as e:
        return {"error": f"Tool execution failed: {str(e)}"}
