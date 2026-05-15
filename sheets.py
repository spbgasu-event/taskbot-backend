import gspread
import os
import json
from google.oauth2.service_account import Credentials
from datetime import datetime

SPREADSHEET_ID = "1lmXv8npThRsCmnSnJYIEfS8g4jLlJli7rvAJuifxsxI"
CREDENTIALS_FILE = "credentials.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def get_client():
    google_creds = os.environ.get("GOOGLE_CREDENTIALS")
    if google_creds:
        creds_dict = json.loads(google_creds)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)

def get_spreadsheet():
    return get_client().open_by_key(SPREADSHEET_ID)


# ──────────────────────────────────────────────
# ИНИЦИАЛИЗАЦИЯ
# ──────────────────────────────────────────────
def init_sheets():
    ss = get_spreadsheet()
    existing = [ws.title for ws in ss.worksheets()]

    if "tasks" not in existing:
        ws = ss.add_worksheet(title="tasks", rows=100, cols=10)
    else:
        ws = ss.worksheet("tasks")
    if ws.row_values(1) == []:
        ws.append_row([
            "task_id", "title", "department", "description",
            "max_participants", "current_participants",
            "check_date_1", "check_date_2", "deadline"
        ])

    # participants теперь с telegram_username
    if "participants" not in existing:
        ws = ss.add_worksheet(title="participants", rows=200, cols=7)
    else:
        ws = ss.worksheet("participants")
    if ws.row_values(1) == []:
        ws.append_row([
            "participant_id", "name", "telegram_id", "telegram_username",
            "task_id", "task_title", "registered_at"
        ])

    if "checklist" not in existing:
        ws = ss.add_worksheet(title="checklist", rows=200, cols=6)
    else:
        ws = ss.worksheet("checklist")
    if ws.row_values(1) == []:
        ws.append_row([
            "task_id", "task_title", "participant_name",
            "check_date_1_done", "check_date_2_done", "final_done"
        ])

    print("✅ Листы готовы!")


# ──────────────────────────────────────────────
# ЗАДАЧИ
# ──────────────────────────────────────────────
def get_all_tasks() -> list[dict]:
    ws = get_spreadsheet().worksheet("tasks")
    return ws.get_all_records()

def get_tasks_by_department(department: str) -> list[dict]:
    return [t for t in get_all_tasks() if t["department"] == department]

def get_task_by_id(task_id: int) -> dict | None:
    for t in get_all_tasks():
        if int(t["task_id"]) == int(task_id):
            return t
    return None

def get_departments() -> list[str]:
    tasks = get_all_tasks()
    seen = []
    for t in tasks:
        if t["department"] not in seen:
            seen.append(t["department"])
    return seen

def is_task_available(task_id: int) -> bool:
    task = get_task_by_id(task_id)
    if not task:
        return False
    return int(task["current_participants"]) < int(task["max_participants"])

def increment_task_participants(task_id: int):
    ws = get_spreadsheet().worksheet("tasks")
    records = ws.get_all_records()
    for i, row in enumerate(records, start=2):
        if int(row["task_id"]) == int(task_id):
            ws.update_cell(i, 6, int(row["current_participants"]) + 1)
            return


# ──────────────────────────────────────────────
# УЧАСТНИКИ
# ──────────────────────────────────────────────
def get_participant_by_telegram(telegram_id: int) -> dict | None:
    ws = get_spreadsheet().worksheet("participants")
    for r in ws.get_all_records():
        if str(r["telegram_id"]) == str(telegram_id):
            return r
    return None

def is_already_in_task(telegram_id: int, task_id: int) -> bool:
    """Проверяет, уже ли участник записан на эту задачу."""
    ws = get_spreadsheet().worksheet("participants")
    for r in ws.get_all_records():
        if str(r["telegram_id"]) == str(telegram_id) and str(r["task_id"]) == str(task_id):
            return True
    return False

def get_participants_for_task(task_id: int) -> list[dict]:
    ws = get_spreadsheet().worksheet("participants")
    return [r for r in ws.get_all_records() if str(r["task_id"]) == str(task_id)]

def add_participant(name: str, telegram_id: int, telegram_username: str, task_id: int) -> tuple[bool, str]:
    """
    Записывает участника на задачу.
    Возвращает (True, "") если успешно.
    Возвращает (False, причина) если нет.
    """
    if is_already_in_task(telegram_id, task_id):
        return False, "already_registered"
    if not is_task_available(task_id):
        return False, "no_slots"

    task = get_task_by_id(task_id)
    ss = get_spreadsheet()

    ws_p = ss.worksheet("participants")
    all_p = ws_p.get_all_records()
    new_id = len(all_p) + 1

    # Если участник уже есть в системе — берём его имя из первой записи
    existing = get_participant_by_telegram(telegram_id)
    real_name = existing["name"] if existing else name

    ws_p.append_row([
        new_id, real_name, telegram_id, telegram_username,
        task_id, task["title"],
        datetime.now().strftime("%Y-%m-%d %H:%M")
    ])

    ws_c = ss.worksheet("checklist")
    ws_c.append_row([task_id, task["title"], real_name, "FALSE", "FALSE", "FALSE"])

    increment_task_participants(task_id)
    return True, ""

def get_all_participants() -> list[dict]:
    ws = get_spreadsheet().worksheet("participants")
    return ws.get_all_records()


# ──────────────────────────────────────────────
# НАПОМИНАНИЯ
# ──────────────────────────────────────────────
def get_upcoming_checks(days_ahead: int = 1) -> list[dict]:
    from datetime import timedelta
    target_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")
    tasks = get_all_tasks()
    participants = get_all_participants()

    result = []
    for task in tasks:
        for field in ["check_date_1", "check_date_2", "deadline"]:
            check_date = str(task.get(field, "")).strip()
            if check_date == target_date or (days_ahead == 0 and check_date == today):
                for p in participants:
                    if str(p["task_id"]) == str(task["task_id"]):
                        result.append({
                            "participant": p,
                            "task": task,
                            "event": field,
                            "date": check_date
                        })
    return result


# ──────────────────────────────────────────────
# ЧЕКЛИСТ
# ──────────────────────────────────────────────
def get_checklist() -> list[dict]:
    return get_spreadsheet().worksheet("checklist").get_all_records()

def update_checklist(updates: dict):
    """
    updates = {
      "task_id_participant_name": {
        "check_date_1_done": "TRUE",
        ...
      }
    }
    """
    ws = get_spreadsheet().worksheet("checklist")
    records = ws.get_all_records()
    headers = ws.row_values(1)

    col_map = {h: i+1 for i, h in enumerate(headers)}

    for i, row in enumerate(records, start=2):
        key = f"{row['task_id']}_{row['participant_name']}"
        if key in updates:
            for field, value in updates[key].items():
                if field in col_map:
                    ws.update_cell(i, col_map[field], value)


if __name__ == "__main__":
    print("Подключаемся...")
    init_sheets()
    print("Отделы:", get_departments())
    print("Задачи:", get_all_tasks())
