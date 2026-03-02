"""Lightweight i18n for Vantage Telegram Bot — ko / en / vi."""

SUPPORTED = ("ko", "en", "vi")
DEFAULT = "en"

DICT: dict[str, dict[str, str]] = {
    # ── Verification ──
    "verify_prompt": {
        "en": (
            "You need to verify your identity first.\n"
            "Send <code>/start CODE</code> using the code from your admin, "
            "or tap the invite link you received."
        ),
        "ko": (
            "먼저 본인 인증이 필요합니다.\n"
            "관리자에게 받은 코드를 <code>/start 코드</code> 형식으로 보내거나, "
            "받은 초대 링크를 탭하세요."
        ),
        "vi": (
            "Ban can xac minh danh tinh truoc.\n"
            "Gui <code>/start MA</code> voi ma tu quan tri vien, "
            "hoac nhan vao lien ket moi ban nhan duoc."
        ),
    },
    "verify_success": {
        "en": "<b>Verification successful!</b>",
        "ko": "<b>인증 성공!</b>",
        "vi": "<b>Xac minh thanh cong!</b>",
    },
    "verify_welcome": {
        "en": "Welcome, {name}! You now have access to Vantage Bot.\nType /help to see what I can do.",
        "ko": "환영합니다, {name}! 이제 Vantage Bot을 사용할 수 있습니다.\n/help 를 입력하면 기능을 확인할 수 있습니다.",
        "vi": "Chao mung, {name}! Ban da co quyen truy cap Vantage Bot.\nNhap /help de xem toi co the lam gi.",
    },
    "verify_failed": {
        "en": "<b>Verification failed</b>",
        "ko": "<b>인증 실패</b>",
        "vi": "<b>Xac minh that bai</b>",
    },
    "verify_invalid": {
        "en": "Invalid code.",
        "ko": "유효하지 않은 코드입니다.",
        "vi": "Ma khong hop le.",
    },
    "welcome_title": {
        "en": "<b>Welcome to Vantage Bot!</b>",
        "ko": "<b>Vantage Bot에 오신 것을 환영합니다!</b>",
        "vi": "<b>Chao mung den voi Vantage Bot!</b>",
    },
    "welcome_need_code": {
        "en": (
            "To get started, you need a verification code from your admin.\n"
            "Send <code>/start CODE</code> or tap the invite link you received."
        ),
        "ko": (
            "시작하려면 관리자에게 인증 코드를 받아야 합니다.\n"
            "<code>/start 코드</code>를 보내거나 받은 초대 링크를 탭하세요."
        ),
        "vi": (
            "De bat dau, ban can ma xac minh tu quan tri vien.\n"
            "Gui <code>/start MA</code> hoac nhan lien ket moi ban nhan duoc."
        ),
    },

    # ── Help ──
    "help_title": {
        "en": "<b>Vantage Bot</b> \u2014 Project Management Assistant",
        "ko": "<b>Vantage Bot</b> \u2014 프로젝트 관리 어시스턴트",
        "vi": "<b>Vantage Bot</b> \u2014 Tro ly quan ly du an",
    },
    "help_commands": {
        "en": "<b>Commands:</b>",
        "ko": "<b>명령어:</b>",
        "vi": "<b>Lenh:</b>",
    },
    "help_tasks_cmd": {
        "en": "/tasks \u2014 View your tasks",
        "ko": "/tasks \u2014 작업 목록 보기",
        "vi": "/tasks \u2014 Xem cong viec cua ban",
    },
    "help_projects_cmd": {
        "en": "/projects \u2014 List projects",
        "ko": "/projects \u2014 프로젝트 목록",
        "vi": "/projects \u2014 Danh sach du an",
    },
    "help_stats_cmd": {
        "en": "/stats \u2014 Project statistics",
        "ko": "/stats \u2014 프로젝트 통계",
        "vi": "/stats \u2014 Thong ke du an",
    },
    "help_help_cmd": {
        "en": "/help \u2014 This help message",
        "ko": "/help \u2014 이 도움말",
        "vi": "/help \u2014 Tin nhan tro giup nay",
    },
    "help_open_cmd": {
        "en": "/open \u2014 Open the mini app",
        "ko": "/open \u2014 미니 앱 열기",
        "vi": "/open \u2014 Mo ung dung mini",
    },
    "help_natural": {
        "en": "<b>You can also ask me naturally:</b>",
        "ko": "<b>자연어로 질문할 수도 있습니다:</b>",
        "vi": "<b>Ban cung co the hoi tu nhien:</b>",
    },
    "help_ex1": {
        "en": '"What tasks do I have due today?"',
        "ko": '"오늘 마감인 작업이 뭐가 있나요?"',
        "vi": '"Hom nay toi co cong viec gi can lam?"',
    },
    "help_ex2": {
        "en": '"How is the project going?"',
        "ko": '"프로젝트 진행 상황은 어때요?"',
        "vi": '"Du an dang tien hanh the nao?"',
    },
    "help_ex3": {
        "en": '"Create a task for..."',
        "ko": '"작업을 만들어 줘..."',
        "vi": '"Tao cong viec cho..."',
    },
    "help_ex4": {
        "en": '"Upload a document for task 5"',
        "ko": '"작업 5에 문서를 업로드해 줘"',
        "vi": '"Tai len tai lieu cho cong viec 5"',
    },
    "help_footer": {
        "en": "For any other questions, please ask and I'll do my best to help you.",
        "ko": "다른 질문이 있으면 물어보세요. 최선을 다해 도와드리겠습니다.",
        "vi": "Moi cau hoi khac, hay hoi va toi se co gang giup ban.",
    },

    # ── Greeting (hi/hello) ──
    "greeting_hello_name": {
        "en": "\U0001f44b <b>Hi {name}!</b> Here's your quick overview:",
        "ko": "\U0001f44b <b>안녕하세요 {name}!</b> 간략한 현황입니다:",
        "vi": "\U0001f44b <b>Xin chao {name}!</b> Day la tong quan nhanh:",
    },
    "greeting_hello": {
        "en": "\U0001f44b <b>Hello!</b> Here's your quick overview:",
        "ko": "\U0001f44b <b>안녕하세요!</b> 간략한 현황입니다:",
        "vi": "\U0001f44b <b>Xin chao!</b> Day la tong quan nhanh:",
    },
    "greeting_urgent_title": {
        "en": "\U0001f4cb <b>Your assigned tasks:</b>",
        "ko": "\U0001f4cb <b>배정된 작업:</b>",
        "vi": "\U0001f4cb <b>Cong viec duoc giao:</b>",
    },
    "greeting_projects_title": {
        "en": "\U0001f4c1 <b>Your projects:</b>",
        "ko": "\U0001f4c1 <b>프로젝트:</b>",
        "vi": "\U0001f4c1 <b>Du an cua ban:</b>",
    },
    "greeting_tasks_due": {
        "en": "tasks assigned",
        "ko": "개 작업 배정",
        "vi": "cong viec duoc giao",
    },
    "greeting_closing": {
        "en": "If there is anything else you need, please don't hesitate to ask!",
        "ko": "다른 도움이 필요하시면 언제든 말씀하세요!",
        "vi": "Neu ban can gi khac, dung ngai hoi nhe!",
    },

    # ── Welcome (verified start) ──
    "welcome_greeting": {
        "en": "<b>Welcome to Vantage!</b> \U0001f44b",
        "ko": "<b>Vantage에 오신 것을 환영합니다!</b> \U0001f44b",
        "vi": "<b>Chao mung den voi Vantage!</b> \U0001f44b",
    },
    "welcome_desc": {
        "en": (
            "I'm your project management assistant. I can help you view tasks, "
            "track progress, upload documents, and more."
        ),
        "ko": (
            "저는 프로젝트 관리 어시스턴트입니다. 작업 확인, 진행 상황 추적, "
            "문서 업로드 등을 도와드릴 수 있습니다."
        ),
        "vi": (
            "Toi la tro ly quan ly du an. Toi co the giup ban xem cong viec, "
            "theo doi tien do, tai len tai lieu, va nhieu hon nua."
        ),
    },
    "your_projects": {
        "en": "<b>Your projects</b> ({n}):",
        "ko": "<b>프로젝트</b> ({n}):",
        "vi": "<b>Du an cua ban</b> ({n}):",
    },
    "no_projects_upload": {
        "en": "No projects yet. Upload an RFP to get started!",
        "ko": "아직 프로젝트가 없습니다. RFP를 업로드하여 시작하세요!",
        "vi": "Chua co du an nao. Tai len RFP de bat dau!",
    },

    # ── Formatters ──
    "tasks_title": {
        "en": "Tasks",
        "ko": "작업",
        "vi": "Cong viec",
    },
    "no_tasks": {
        "en": "No tasks found.",
        "ko": "작업이 없습니다.",
        "vi": "Khong tim thay cong viec.",
    },
    "task_count": {
        "en": "{n} task",
        "ko": "{n}개 작업",
        "vi": "{n} cong viec",
    },
    "task_count_plural": {
        "en": "{n} tasks",
        "ko": "{n}개 작업",
        "vi": "{n} cong viec",
    },
    "and_n_more": {
        "en": "... and {n} more",
        "ko": "... 그 외 {n}개",
        "vi": "... va {n} nua",
    },
    "task_list_prompt": {
        "en": "Let me know what task you want to work on.",
        "ko": "어떤 작업을 진행하고 싶으신지 알려주세요.",
        "vi": "Hay cho toi biet ban muon lam cong viec nao.",
    },
    "projects_title": {
        "en": "Projects",
        "ko": "프로젝트",
        "vi": "Du an",
    },
    "no_projects": {
        "en": "No projects found.",
        "ko": "프로젝트가 없습니다.",
        "vi": "Khong tim thay du an.",
    },
    "select_project": {
        "en": "Which project would you like to work on?",
        "ko": "어떤 프로젝트에서 작업하시겠습니까?",
        "vi": "Ban muon lam viec voi du an nao?",
    },
    "project_selected": {
        "en": "Switched to <b>{name}</b>. How can I help?",
        "ko": "<b>{name}</b>(으)로 전환했습니다. 무엇을 도와드릴까요?",
        "vi": "Da chuyen sang <b>{name}</b>. Toi co the giup gi?",
    },
    "stats_title": {
        "en": "Project Stats",
        "ko": "프로젝트 통계",
        "vi": "Thong ke du an",
    },
    "stats_total": {
        "en": "Total tasks:",
        "ko": "전체 작업:",
        "vi": "Tong cong viec:",
    },
    "stats_in_progress": {
        "en": "In progress:",
        "ko": "진행 중:",
        "vi": "Dang thuc hien:",
    },
    "due_today": {
        "en": "Due today:",
        "ko": "오늘 마감:",
        "vi": "Den han hom nay:",
    },
    "this_week": {
        "en": "This week:",
        "ko": "이번 주:",
        "vi": "Tuan nay:",
    },
    "completed": {
        "en": "Completed:",
        "ko": "완료:",
        "vi": "Hoan thanh:",
    },
    "unassigned": {
        "en": "Unassigned",
        "ko": "미배정",
        "vi": "Chua phan cong",
    },

    # ── Buttons ──
    "btn_details": {
        "en": "\U0001f4dd Details",
        "ko": "\U0001f4dd 상세",
        "vi": "\U0001f4dd Chi tiet",
    },
    "btn_start": {
        "en": "\u25b6\ufe0f Start",
        "ko": "\u25b6\ufe0f 시작",
        "vi": "\u25b6\ufe0f B\u1eaft \u0111\u1ea7u",
    },
    "btn_complete": {
        "en": "\u2705 Complete",
        "ko": "\u2705 완료",
        "vi": "\u2705 Hoan thanh",
    },
    "btn_reopen": {
        "en": "\U0001f504 Reopen",
        "ko": "\U0001f504 다시 열기",
        "vi": "\U0001f504 Mo lai",
    },
    "btn_yes_complete": {
        "en": "\u2705 Yes, Complete",
        "ko": "\u2705 \ub124, \uc644\ub8cc",
        "vi": "\u2705 Co, Hoan thanh",
    },
    "btn_cancel": {
        "en": "\u274c Cancel",
        "ko": "\u274c \ucde8\uc18c",
        "vi": "\u274c Huy",
    },
    "complete_confirm": {
        "en": "\u2753 <b>Mark this task as complete?</b>",
        "ko": "\u2753 <b>\uc774 \uc791\uc5c5\uc744 \uc644\ub8cc\ub85c \ud45c\uc2dc\ud558\uc2dc\uaca0\uc2b5\ub2c8\uae4c?</b>",
        "vi": "\u2753 <b>Danh dau cong viec nay la hoan thanh?</b>",
    },
    "complete_confirm_note": {
        "en": "If you have documents to upload, please send them first before completing.",
        "ko": "\uc5c5\ub85c\ub4dc\ud560 \ubb38\uc11c\uac00 \uc788\uc73c\uba74 \uc644\ub8cc \uc804\uc5d0 \uba3c\uc800 \ubcf4\ub0b4\uc8fc\uc138\uc694.",
        "vi": "Neu ban co tai lieu can tai len, vui long gui truoc khi hoan thanh.",
    },
    "action_cancelled": {
        "en": "Action cancelled.",
        "ko": "\uc791\uc5c5\uc774 \ucde8\uc18c\ub418\uc5c8\uc2b5\ub2c8\ub2e4.",
        "vi": "Hanh dong da bi huy.",
    },
    "criteria_warning": {
        "en": "\u26a0\ufe0f <b>This task may not be ready to complete.</b>\n",
        "ko": "\u26a0\ufe0f <b>\uc774 \uc791\uc5c5\uc740 \uc544\uc9c1 \uc644\ub8cc\ud560 \uc900\ube44\uac00 \ub418\uc9c0 \uc54a\uc558\uc744 \uc218 \uc788\uc2b5\ub2c8\ub2e4.</b>\n",
        "vi": "\u26a0\ufe0f <b>Cong viec nay co the chua san sang hoan thanh.</b>\n",
    },
    "criteria_no_docs": {
        "en": "\u274c No documents uploaded yet",
        "ko": "\u274c \uc544\uc9c1 \ubb38\uc11c\uac00 \uc5c5\ub85c\ub4dc\ub418\uc9c0 \uc54a\uc558\uc2b5\ub2c8\ub2e4",
        "vi": "\u274c Chua co tai lieu nao duoc tai len",
    },
    "criteria_missing_reqs": {
        "en": "\u274c Acceptance criteria not yet addressed:",
        "ko": "\u274c \uc544\uc9c1 \ucc98\ub9ac\ub418\uc9c0 \uc54a\uc740 \uc218\ub77d \uae30\uc900:",
        "vi": "\u274c Tieu chi chap nhan chua duoc xu ly:",
    },
    "criteria_expected_format": {
        "en": "\u274c Expected format: {format}",
        "ko": "\u274c \uc608\uc0c1 \ud615\uc2dd: {format}",
        "vi": "\u274c Dinh dang yeu cau: {format}",
    },
    "criteria_action_hint": {
        "en": "\n<b>What to do:</b> Upload the required documents before completing, or override if not applicable.",
        "ko": "\n<b>\uc870\uce58 \uc0ac\ud56d:</b> \uc644\ub8cc \uc804\uc5d0 \ud544\uc694\ud55c \ubb38\uc11c\ub97c \uc5c5\ub85c\ub4dc\ud558\uac70\ub098, \ud574\ub2f9\ub418\uc9c0 \uc54a\ub294 \uacbd\uc6b0 \uac15\uc81c \uc644\ub8cc\ud558\uc138\uc694.",
        "vi": "\n<b>Can lam:</b> Tai len tai lieu can thiet truoc khi hoan thanh, hoac bo qua neu khong ap dung.",
    },
    "btn_override_complete": {
        "en": "\u26a1 Complete Anyway",
        "ko": "\u26a1 \uadf8\ub798\ub3c4 \uc644\ub8cc",
        "vi": "\u26a1 Van hoan thanh",
    },
    "btn_view_tasks": {
        "en": "\U0001f4cb View Tasks",
        "ko": "\U0001f4cb 작업 보기",
        "vi": "\U0001f4cb Xem cong viec",
    },
    "btn_get_template": {
        "en": "Get Template",
        "ko": "템플릿 받기",
        "vi": "Tai mau",
    },
    "report_description": {
        "en": "Report Description",
        "ko": "보고서 설명",
        "vi": "Mo ta bao cao",
    },
    "submission_guide": {
        "en": "Submission Guide",
        "ko": "제출 안내",
        "vi": "Huong dan nop",
    },
    "template_available": {
        "en": "Template: {file}",
        "ko": "템플릿: {file}",
        "vi": "Mau: {file}",
    },
    "btn_overdue": {
        "en": "\u26a0\ufe0f Overdue",
        "ko": "\u26a0\ufe0f 기한 초과",
        "vi": "\u26a0\ufe0f Qua han",
    },
    "btn_tasks": {
        "en": "\U0001f4cb Tasks",
        "ko": "\U0001f4cb 작업",
        "vi": "\U0001f4cb Cong viec",
    },
    "btn_stats": {
        "en": "\U0001f4ca Stats",
        "ko": "\U0001f4ca 통계",
        "vi": "\U0001f4ca Thong ke",
    },
    "btn_help": {
        "en": "\u2753 Help",
        "ko": "\u2753 도움말",
        "vi": "\u2753 Tro giup",
    },

    # ── Task detail labels ──
    "status_label": {
        "en": "<b>Status:</b>",
        "ko": "<b>상태:</b>",
        "vi": "<b>Trang thai:</b>",
    },
    "priority_label": {
        "en": "<b>Priority:</b>",
        "ko": "<b>우선순위:</b>",
        "vi": "<b>Uu tien:</b>",
    },
    "assignee_label": {
        "en": "<b>Assignee:</b>",
        "ko": "<b>담당자:</b>",
        "vi": "<b>Nguoi phu trach:</b>",
    },
    "due_label": {
        "en": "<b>Due:</b>",
        "ko": "<b>마감일:</b>",
        "vi": "<b>Han:</b>",
    },

    # ── Handlers ──
    "your_tasks": {
        "en": "Your Tasks",
        "ko": "내 작업",
        "vi": "Cong viec cua ban",
    },
    "all_tasks": {
        "en": "All Tasks",
        "ko": "전체 작업",
        "vi": "Tat ca cong viec",
    },
    "tasks_attention": {
        "en": "Tasks \u2014 Needs Attention",
        "ko": "작업 \u2014 주의 필요",
        "vi": "Cong viec \u2014 Can chu y",
    },
    "fetch_error": {
        "en": "Failed to fetch {item}: {error}",
        "ko": "{item} 가져오기 실패: {error}",
        "vi": "Khong the lay {item}: {error}",
    },
    "no_data": {
        "en": "No {item} data returned.",
        "ko": "{item} 데이터가 없습니다.",
        "vi": "Khong co du lieu {item}.",
    },
    "fetch_projects_error": {
        "en": "Failed to fetch projects.",
        "ko": "프로젝트를 가져올 수 없습니다.",
        "vi": "Khong the lay du an.",
    },
    "fetch_stats_error": {
        "en": "Failed to fetch stats for {slug}.",
        "ko": "{slug}의 통계를 가져올 수 없습니다.",
        "vi": "Khong the lay thong ke cho {slug}.",
    },

    # ── Error messages ──
    "error_generic": {
        "en": "Sorry, I encountered an error processing your request.",
        "ko": "죄송합니다, 요청을 처리하는 중에 오류가 발생했습니다.",
        "vi": "Xin loi, toi gap loi khi xu ly yeu cau cua ban.",
    },
    "error_file": {
        "en": "Sorry, I encountered an error handling your file.",
        "ko": "죄송합니다, 파일을 처리하는 중에 오류가 발생했습니다.",
        "vi": "Xin loi, toi gap loi khi xu ly tep cua ban.",
    },
    "file_received": {
        "en": "Received {filename}. What would you like me to do with it?",
        "ko": "{filename}을(를) 수신했습니다. 어떻게 처리할까요?",
        "vi": "Da nhan {filename}. Ban muon toi lam gi voi no?",
    },
    "file_analyzing": {
        "en": "Received {filename}. Analyzing for task {task_id}...",
        "ko": "{filename}을(를) 수신했습니다. 작업 {task_id} 분석 중...",
        "vi": "Da nhan {filename}. Dang phan tich cho cong viec {task_id}...",
    },
    "file_analyzing_smart": {
        "en": "Received {filename}. Let me take a look and check your tasks...",
        "ko": "{filename}을(를) 수신했습니다. 파일을 확인하고 작업을 검토할게요...",
        "vi": "Đã nhận {filename}. Để tôi xem và kiểm tra công việc của bạn...",
    },

    # ── /lang command ──
    "lang_current": {
        "en": "Current language: <b>{language}</b>",
        "ko": "현재 언어: <b>{language}</b>",
        "vi": "Ngon ngu hien tai: <b>{language}</b>",
    },
    "lang_pick": {
        "en": "Choose your language:",
        "ko": "언어를 선택하세요:",
        "vi": "Chon ngon ngu cua ban:",
    },
    "lang_set": {
        "en": "Language set to <b>English</b>.",
        "ko": "언어가 <b>한국어</b>로 설정되었습니다.",
        "vi": "Ngon ngu da duoc dat thanh <b>Tieng Viet</b>.",
    },
    "help_lang_cmd": {
        "en": "/lang \u2014 Change language",
        "ko": "/lang \u2014 언어 변경",
        "vi": "/lang \u2014 Doi ngon ngu",
    },

    # ── Admin action requests ──
    "admin_set_due_prompt": {
        "en": "What due date should I set for task <code>#{tid}</code>?\n<i>(e.g., March 15, next Monday, 2026-04-01)</i>",
        "ko": "태스크 <code>#{tid}</code>의 마감일을 언제로 설정할까요?\n<i>(예: 3월 15일, 다음 월요일, 2026-04-01)</i>",
        "vi": "Ngay han cho nhiem vu <code>#{tid}</code> la bao nhieu?\n<i>(vi du: 15 thang 3, thu Hai toi, 2026-04-01)</i>",
    },
    "request_sent": {
        "en": "Request sent to {admin_name}.",
        "ko": "{admin_name}에게 요청을 보냈습니다.",
        "vi": "Da gui yeu cau den {admin_name}.",
    },
}


def get_lang(language_code: str | None) -> str:
    """Map Telegram language_code to a supported language."""
    if not language_code:
        return DEFAULT
    code = language_code.lower()[:2]
    return code if code in SUPPORTED else DEFAULT


def t(key: str, lang: str = "en", **kwargs) -> str:
    """Translate a key. Supports {param} interpolation."""
    entry = DICT.get(key, {})
    text = entry.get(lang) or entry.get(DEFAULT, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text
