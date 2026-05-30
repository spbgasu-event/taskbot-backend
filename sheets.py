import gspread
import os
import json
from datetime import datetime, timedelta

SPREADSHEET_ID = "1lmXv8npThRsCmnSnJYIEfS8g4jLlJli7rvAJuifxsxI"
CREDENTIALS_FILE = "credentials.json"
INTERN_DEPT = "Стажёры"

ROLES = ("intern", "member", "admin")
POINTS_PER_TASK = 10  # баллов за выполненную задачу


# ── Подключение ───────────────────────────────────────────────
def get_client() -> gspread.Client:
    google_creds = os.environ.get("GOOGLE_CREDENTIALS")
    if google_creds:
        creds_dict = json.loads(google_creds)
        return gspread.service_account_from_dict(creds_dict)
    else:
        return gspread.service_account(filename=CREDENTIALS_FILE)


def get_spreadsheet() -> gspread.Spreadsheet:
    return get_client().open_by_key(SPREADSHEET_ID)


# ── Вспомогательные ───────────────────────────────────────────
def _ws_ensure_col(ws, col_name: str) -> int:
    """Добавляет колонку если её нет; расширяет лист при необходимости."""
    headers = ws.row_values(1)
    if col_name not in headers:
        new_col = len(headers) + 1
        # Расширяем лист если не хватает колонок
        props = ws.spreadsheet.fetch_sheet_metadata()
        sheet_meta = next(
            (s for s in props["sheets"] if s["properties"]["sheetId"] == ws.id), None
        )
        if sheet_meta:
            max_cols = sheet_meta["properties"]["gridProperties"]["columnCount"]
            if new_col > max_cols:
                ws.resize(cols=new_col + 4)  # +4 запас
        ws.update_cell(1, new_col, col_name)
        headers.append(col_name)
    return headers.index(col_name) + 1


def _normalize_task(row: dict) -> dict:
    """Backward compat: превращает старые check_date_1/2/deadline в checkpoints."""
    row = dict(row)
    raw = row.get("checkpoints", "")
    if raw:
        try:
            row["checkpoints"] = json.loads(str(raw))
            if not row.get("deadline"):
                dl = next((c["date"] for c in row["checkpoints"]
                           if c.get("type") == "deadline"), "")
                row["deadline"] = dl
            return row
        except (json.JSONDecodeError, TypeError):
            pass
    checkpoints = []
    for field, label in [("check_date_1", "Проверка 1"), ("check_date_2", "Проверка 2")]:
        v = str(row.get(field, "")).strip()
        if v:
            checkpoints.append({"label": label, "date": v, "type": "check"})
    v = str(row.get("deadline", "")).strip()
    if v:
        checkpoints.append({"label": "Дедлайн", "date": v, "type": "deadline"})
    row["checkpoints"] = checkpoints
    return row


# ── Инициализация листов ──────────────────────────────────────
def init_sheets():
    ss = get_spreadsheet()
    existing = [ws.title for ws in ss.worksheets()]

    # tasks
    if "tasks" not in existing:
        ws = ss.add_worksheet(title="tasks", rows=200, cols=12)
        ws.append_row([
            "task_id", "title", "department", "description",
            "max_participants", "current_participants",
            "check_date_1", "check_date_2", "deadline", "status", "checkpoints"
        ])
    else:
        ws = ss.worksheet("tasks")
        if ws.row_values(1):
            _ws_ensure_col(ws, "status")
            _ws_ensure_col(ws, "checkpoints")

    # participants
    if "participants" not in existing:
        ws = ss.add_worksheet(title="participants", rows=300, cols=9)
        ws.append_row([
            "participant_id", "name", "telegram_id", "telegram_username",
            "task_id", "task_title", "registered_at", "role", "points"
        ])
    else:
        ws = ss.worksheet("participants")
        if ws.row_values(1):
            _ws_ensure_col(ws, "role")
            _ws_ensure_col(ws, "points")

    # checklist
    if "checklist" not in existing:
        ws = ss.add_worksheet(title="checklist", rows=300, cols=6)
        ws.append_row([
            "task_id", "task_title", "participant_name",
            "check_date_1_done", "check_date_2_done", "final_done"
        ])

    # submissions
    if "submissions" not in existing:
        ws = ss.add_worksheet(title="submissions", rows=300, cols=7)
        ws.append_row([
            "submission_id", "task_id", "task_title",
            "participant_telegram_id", "participant_name",
            "submitted_at", "status"
        ])

    print("✅ Листы готовы!")


# ── Задачи ────────────────────────────────────────────────────
def _get_tasks_raw() -> list[dict]:
    return get_spreadsheet().worksheet("tasks").get_all_records()


def get_all_tasks() -> list[dict]:
    return [_normalize_task(t) for t in _get_tasks_raw()]


def get_open_tasks() -> list[dict]:
    return [t for t in get_all_tasks() if str(t.get("status", "")).lower() != "closed"]


def get_closed_tasks() -> list[dict]:
    return [t for t in get_all_tasks() if str(t.get("status", "")).lower() == "closed"]


def get_tasks_for_role(role: str) -> list[dict]:
    """Фильтрует открытые задачи по роли пользователя."""
    tasks = get_open_tasks()
    if role == "intern":
        return [t for t in tasks if t.get("department") == INTERN_DEPT]
    return tasks  # member и admin видят все


def get_tasks_by_department(department: str, role: str = "member") -> list[dict]:
    return [t for t in get_tasks_for_role(role) if t["department"] == department]


def get_task_by_id(task_id: int) -> dict | None:
    for t in get_all_tasks():
        if int(t["task_id"]) == int(task_id):
            return t
    return None


def get_departments(role: str = "member") -> list[str]:
    tasks = get_tasks_for_role(role)
    return list(dict.fromkeys(t["department"] for t in tasks))


def is_task_available(task_id: int) -> bool:
    task = get_task_by_id(task_id)
    if not task:
        return False
    if str(task.get("status", "")).lower() == "closed":
        return False
    return int(task["current_participants"]) < int(task["max_participants"])


def increment_task_participants(task_id: int):
    ws = get_spreadsheet().worksheet("tasks")
    records = ws.get_all_records()
    for i, row in enumerate(records, start=2):
        if int(row["task_id"]) == int(task_id):
            ws.update_cell(i, 6, int(row["current_participants"]) + 1)
            return


def close_task(task_id: int) -> bool:
    ws = get_spreadsheet().worksheet("tasks")
    col = _ws_ensure_col(ws, "status")
    records = ws.get_all_records()
    for i, row in enumerate(records, start=2):
        if int(row["task_id"]) == int(task_id):
            ws.update_cell(i, col, "closed")
            return True
    return False


def create_task(title: str, department: str, description: str,
                max_participants: int, checkpoints: list[dict]) -> dict:
    """Создаёт новую задачу. checkpoints = [{label, date, type}]"""
    ws = get_spreadsheet().worksheet("tasks")
    _ws_ensure_col(ws, "checkpoints")
    _ws_ensure_col(ws, "status")
    records = ws.get_all_records()
    new_id = max((int(r.get("task_id", 0)) for r in records), default=0) + 1

    deadline = next((c["date"] for c in checkpoints if c.get("type") == "deadline"), "")
    checks = [c for c in checkpoints if c.get("type") == "check"]
    c1 = checks[0]["date"] if checks else ""
    c2 = checks[1]["date"] if len(checks) > 1 else ""

    ws.append_row([
        new_id, title, department, description,
        max_participants, 0,
        c1, c2, deadline, "open",
        json.dumps(checkpoints, ensure_ascii=False)
    ])
    return get_task_by_id(new_id)


def update_task(task_id: int, updates: dict) -> bool:
    ws = get_spreadsheet().worksheet("tasks")
    headers = ws.row_values(1)
    records = ws.get_all_records()
    for i, row in enumerate(records, start=2):
        if int(row["task_id"]) == int(task_id):
            for field, value in updates.items():
                if field in headers:
                    ws.update_cell(i, headers.index(field) + 1, value)
            return True
    return False


def delete_task(task_id: int) -> bool:
    ws = get_spreadsheet().worksheet("tasks")
    records = ws.get_all_records()
    for i, row in enumerate(records, start=2):
        if int(row["task_id"]) == int(task_id):
            ws.delete_rows(i)
            return True
    return False


# ── Участники ─────────────────────────────────────────────────
def get_all_participants() -> list[dict]:
    return get_spreadsheet().worksheet("participants").get_all_records()


def get_participant_by_telegram(telegram_id: int) -> dict | None:
    for r in get_all_participants():
        if str(r["telegram_id"]) == str(telegram_id):
            return r
    return None


def get_participant_role(telegram_id: int) -> str:
    p = get_participant_by_telegram(telegram_id)
    if not p:
        return "intern"
    return str(p.get("role", "intern") or "intern")


def set_participant_role(telegram_id: int, role: str) -> bool:
    if role not in ROLES:
        return False
    ws = get_spreadsheet().worksheet("participants")
    col = _ws_ensure_col(ws, "role")
    records = ws.get_all_records()
    updated = False
    for i, row in enumerate(records, start=2):
        if str(row["telegram_id"]) == str(telegram_id):
            ws.update_cell(i, col, role)
            updated = True
    return updated


def is_already_in_task(telegram_id: int, task_id: int) -> bool:
    for r in get_all_participants():
        if str(r["telegram_id"]) == str(telegram_id) and str(r["task_id"]) == str(task_id):
            return True
    return False


def get_participants_for_task(task_id: int) -> list[dict]:
    return [r for r in get_all_participants() if str(r["task_id"]) == str(task_id)]


def add_participant(name: str, telegram_id: int, telegram_username: str,
                    task_id: int) -> tuple[bool, str]:
    if is_already_in_task(telegram_id, task_id):
        return False, "already_registered"
    if not is_task_available(task_id):
        return False, "no_slots"

    task = get_task_by_id(task_id)
    ss = get_spreadsheet()

    ws_p = ss.worksheet("participants")
    all_p = ws_p.get_all_records()
    new_id = len(all_p) + 1

    existing = get_participant_by_telegram(telegram_id)
    real_name = existing["name"] if existing else name
    role = str(existing.get("role", "intern") or "intern") if existing else "intern"
    points = int(existing.get("points", 0) or 0) if existing else 0

    ws_p.append_row([
        new_id, real_name, telegram_id, telegram_username,
        task_id, task["title"],
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        role, points
    ])

    ws_c = ss.worksheet("checklist")
    ws_c.append_row([task_id, task["title"], real_name, "FALSE", "FALSE", "FALSE"])

    increment_task_participants(task_id)
    return True, ""


def award_points(telegram_id: int, pts: int):
    ws = get_spreadsheet().worksheet("participants")
    col = _ws_ensure_col(ws, "points")
    records = ws.get_all_records()
    for i, row in enumerate(records, start=2):
        if str(row["telegram_id"]) == str(telegram_id):
            current = int(row.get("points", 0) or 0)
            ws.update_cell(i, col, current + pts)
            break


def get_user_stats(telegram_id: int) -> dict:
    all_p = get_all_participants()
    my = [p for p in all_p if str(p["telegram_id"]) == str(telegram_id)]
    task_map = {str(t["task_id"]): t for t in get_all_tasks()}

    active = [p for p in my
              if str(task_map.get(str(p["task_id"]), {}).get("status", "")).lower() != "closed"]
    completed = [p for p in my
                 if str(task_map.get(str(p["task_id"]), {}).get("status", "")).lower() == "closed"]

    p = get_participant_by_telegram(telegram_id)
    return {
        "name": p.get("name", "") if p else "",
        "telegram_username": p.get("telegram_username", "") if p else "",
        "role": str(p.get("role", "intern") or "intern") if p else "intern",
        "points": int(p.get("points", 0) or 0) if p else 0,
        "active_tasks": len(active),
        "completed_tasks": len(completed),
        "total_tasks": len(my),
        "active_list": [task_map[str(p["task_id"])] for p in active
                        if str(p["task_id"]) in task_map],
    }


def get_leaderboard() -> list[dict]:
    all_p = get_all_participants()
    agg: dict[str, dict] = {}
    for p in all_p:
        tid = str(p["telegram_id"])
        if tid not in agg:
            agg[tid] = {
                "name": p["name"],
                "telegram_username": p.get("telegram_username", ""),
                "points": int(p.get("points", 0) or 0),
                "tasks": 0,
            }
        agg[tid]["tasks"] += 1
        agg[tid]["points"] = max(agg[tid]["points"], int(p.get("points", 0) or 0))
    return sorted(agg.values(), key=lambda x: (-x["points"], -x["tasks"]))[:20]


def get_unique_participants() -> list[dict]:
    """Уникальные участники (по telegram_id) с ролью и баллами."""
    all_p = get_all_participants()
    seen: dict[str, dict] = {}
    for p in all_p:
        tid = str(p["telegram_id"])
        if tid not in seen:
            seen[tid] = {
                "name": p["name"],
                "telegram_id": tid,
                "telegram_username": p.get("telegram_username", ""),
                "role": str(p.get("role", "intern") or "intern"),
                "points": int(p.get("points", 0) or 0),
            }
    return list(seen.values())


# ── Сдача задачи ──────────────────────────────────────────────
def submit_task_for_review(task_id: int, participant_telegram_id: int,
                            participant_name: str, task_title: str) -> int:
    """Создаёт заявку на сдачу задачи. Возвращает submission_id."""
    ss = get_spreadsheet()
    ws = ss.worksheet("submissions")
    records = ws.get_all_records()
    new_id = len(records) + 1
    ws.append_row([
        new_id, task_id, task_title,
        participant_telegram_id, participant_name,
        datetime.now().strftime("%Y-%m-%d %H:%M"), "pending"
    ])
    return new_id


def get_pending_submissions() -> list[dict]:
    return [r for r in get_spreadsheet().worksheet("submissions").get_all_records()
            if str(r.get("status", "")) == "pending"]


def update_submission_status(submission_id: int, status: str):
    ws = get_spreadsheet().worksheet("submissions")
    headers = ws.row_values(1)
    if "status" not in headers:
        return
    col = headers.index("status") + 1
    for i, row in enumerate(ws.get_all_records(), start=2):
        if int(row.get("submission_id", 0)) == int(submission_id):
            ws.update_cell(i, col, status)
            return


# ── Напоминания ────────────────────────────────────────────────
def get_upcoming_checks(days_ahead: int = 1) -> list[dict]:
    target = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    result = []
    for task in get_open_tasks():
        for cp in task.get("checkpoints", []):
            if str(cp.get("date", "")).strip() == target:
                for p in get_all_participants():
                    if str(p["task_id"]) == str(task["task_id"]):
                        result.append({
                            "participant": p,
                            "task": task,
                            "event": cp.get("type", "check"),
                            "label": cp.get("label", "Проверка"),
                            "date": cp["date"],
                        })
    return result


def get_all_active_participants_for_digest() -> list[dict]:
    """Все участники с активными задачами для еженедельного дайджеста."""
    all_p = get_all_participants()
    task_map = {str(t["task_id"]): t for t in get_open_tasks()}
    return [p for p in all_p if str(p["task_id"]) in task_map]


# ── Чеклист ────────────────────────────────────────────────────
def get_checklist() -> list[dict]:
    return get_spreadsheet().worksheet("checklist").get_all_records()


def update_checklist(updates: dict):
    ws = get_spreadsheet().worksheet("checklist")
    records = ws.get_all_records()
    headers = ws.row_values(1)
    col_map = {h: i + 1 for i, h in enumerate(headers)}
    for i, row in enumerate(records, start=2):
        key = f"{row['task_id']}_{row['participant_name']}"
        if key in updates:
            for field, value in updates[key].items():
                if field in col_map:
                    ws.update_cell(i, col_map[field], value)


# ── Статистика невыполненных ───────────────────────────────────
def get_failed_participants() -> list[dict]:
    closed_ids = {str(t["task_id"]) for t in get_closed_tasks()}
    checklist = get_checklist()
    participants = get_all_participants()
    p_index = {f"{p['task_id']}_{p['name']}": p for p in participants}
    failed = []
    for row in checklist:
        if str(row["task_id"]) not in closed_ids:
            continue
        if str(row.get("final_done", "FALSE")).upper() != "TRUE":
            key = f"{row['task_id']}_{row['participant_name']}"
            p = p_index.get(key, {})
            failed.append({
                "name": row["participant_name"],
                "telegram_username": p.get("telegram_username", ""),
                "telegram_id": p.get("telegram_id", ""),
                "task_id": row["task_id"],
                "task_title": row["task_title"],
                "check_date_1_done": row.get("check_date_1_done", "FALSE"),
                "check_date_2_done": row.get("check_date_2_done", "FALSE"),
                "final_done": row.get("final_done", "FALSE"),
            })
    return failed


if __name__ == "__main__":
    print("Подключаемся...")
    init_sheets()
    print("Отделы:", get_departments())
    print("Задачи:", get_all_tasks())
