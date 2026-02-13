"""Tool definitions and execution for Vantage bot"""
import json
import subprocess
from pathlib import Path
from typing import Dict, Any
from config import TASK_SCRIPTS_DIR, RFP_SCRIPTS_DIR, PROJECT_SCRIPTS_DIR

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
            "name": "process_rfp",
            "description": "Process an RFP document and create project with all topics, requirements, deliverables, and tasks. Automatically uses the most recently uploaded file or accepts a specific file path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Optional specific file path. If not provided, uses 'latest' to process most recent upload from ~/.openclaw/media/inbound/"
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
    }
]


def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool by name with given arguments"""

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

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "get_task":
            cmd = ["python3", str(TASK_SCRIPTS_DIR / "tasks.py"), "get", str(arguments["task_id"])]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "analyze_task_document":
            cmd = ["python3", str(TASK_SCRIPTS_DIR / "analyze_task_document.py"), str(arguments["task_id"])]
            import os
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=os.environ.copy())
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "complete_task":
            cmd = ["python3", str(TASK_SCRIPTS_DIR / "complete_task.py"), str(arguments["task_id"])]
            # Pass environment variables to subprocess (needed for VLLM_URL, VANTAGE_API_URL)
            import os
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=os.environ.copy())
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

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "update_task":
            cmd = ["python3", str(TASK_SCRIPTS_DIR / "tasks.py"), "update", str(arguments["task_id"])]
            if "title" in arguments:
                cmd.extend(["--title", arguments["title"]])
            if "due" in arguments:
                cmd.extend(["--due", arguments["due"]])
            if "status" in arguments:
                cmd.extend(["--status", arguments["status"]])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "delete_task":
            cmd = ["python3", str(TASK_SCRIPTS_DIR / "tasks.py"), "delete", str(arguments["task_id"])]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "process_rfp":
            file_path = arguments.get("file_path", "latest")
            cmd = ["python3", str(RFP_SCRIPTS_DIR / "process_rfp.py"), file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "get_project_stats":
            cmd = ["python3", str(PROJECT_SCRIPTS_DIR / "projects.py"), "stats", arguments["project_slug"]]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "delete_project":
            cmd = ["python3", str(PROJECT_SCRIPTS_DIR / "projects.py"), "delete", arguments["project_slug"]]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        elif tool_name == "get_projects":
            cmd = ["python3", str(PROJECT_SCRIPTS_DIR / "projects.py"), "list"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return json.loads(result.stdout) if result.returncode == 0 else {"error": result.stderr}

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except subprocess.TimeoutExpired:
        return {"error": f"Tool {tool_name} timed out"}
    except Exception as e:
        return {"error": f"Tool execution failed: {str(e)}"}
