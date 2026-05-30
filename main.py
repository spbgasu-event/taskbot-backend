import asyncio
import logging
import os
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import (
    Bot, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, Update,
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters,
)
from telegram.error import TelegramError

from sheets import (
    # Задачи
    get_departments, get_tasks_by_department, get_task_by_id,
    get_open_tasks, get_closed_tasks, get_all_tasks,
    get_tasks_for_role, create_task, update_task, delete_task, close_task,
    # Участники
    add_participant, get_participant_by_telegram, get_participant_role,
    set_participant_role, get_participants_for_task,
    get_all_participants, get_unique_participants,
    get_user_stats, get_leaderboard, award_points,
    # Напоминания / дайджест
    get_upcoming_checks, get_all_active_participants_for_digest,
    # Сдача
    submit_task_for_review, get_pending_submissions, update_submission_status,
    # Прочее
    get_checklist, update_checklist, get_failed_participants,
    INTERN_DEPT, ROLES, POINTS_PER_TASK,
)

# ──────────────────────────────────────────────
# НАСТРОЙКИ (всё из переменных окружения)
# ──────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN не задан! Установи переменную окружения.")

ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "changeme")
ORGANIZER_TELEGRAM_ID = int(os.environ.get("ORGANIZER_TELEGRAM_ID", "1251988176"))
SITE_URL = os.environ.get("SITE_URL", "https://spbgasu-event.github.io/taskbot-site/")
WEBHOOK_BASE_URL = os.environ.get("WEBHOOK_URL") or os.environ.get("RENDER_EXTERNAL_URL")
WEBHOOK_PATH = "/webhook"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_TOKEN)

# ── Состояния ConversationHandler ─────────────────────────────
(CT_TITLE, CT_DEPT, CT_DESC, CT_MAX, CT_CHECK, CT_DEADLINE, CT_CONFIRM) = range(7)
(RL_SELECT, RL_ROLE) = range(10, 12)
(ONBOARD_NAME,) = range(20, 21)
(SUBMIT_TASK,) = range(30, 31)


# ──────────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ
# ──────────────────────────────────────────────
def _check_admin(x_admin_secret: Optional[str]) -> bool:
    return x_admin_secret == ADMIN_SECRET


def _require_admin(x_admin_secret: Optional[str]):
    if not _check_admin(x_admin_secret):
        raise HTTPException(status_code=403, detail="Требуется X-Admin-Secret")


async def notify(telegram_id: int, message: str,
                 reply_markup=None, parse_mode: str = "Markdown"):
    try:
        await bot.send_message(
            chat_id=telegram_id, text=message,
            parse_mode=parse_mode, reply_markup=reply_markup,
        )
    except Exception as e:
        logger.error(f"Ошибка отправки {telegram_id}: {e}")


def role_label(role: str) -> str:
    return {"intern": "Стажёр", "member": "Участник", "admin": "Организатор"}.get(role, role)


def format_checkpoints(checkpoints: list[dict]) -> str:
    lines = []
    for cp in checkpoints:
        icon = "🏁" if cp.get("type") == "deadline" else "🔍"
        lines.append(f"{icon} {cp.get('label','Проверка')}: {cp.get('date','—')}")
    return "\n".join(lines) if lines else "Без дат"


# ──────────────────────────────────────────────
# КЛАВИАТУРЫ БОТА
# ──────────────────────────────────────────────
def main_menu(telegram_id: int = 0) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton("📋 Мои задачи"), KeyboardButton("📅 Ближайшие даты")],
        [KeyboardButton("🏆 Рейтинг"), KeyboardButton("📁 История")],
        [KeyboardButton("👤 Профиль"), KeyboardButton("🆔 Мой Telegram ID")],
        [KeyboardButton("📤 Сдать задачу")],
    ]
    if telegram_id == ORGANIZER_TELEGRAM_ID:
        rows.append([KeyboardButton("⚙️ Панель организатора")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [KeyboardButton("📝 Создать задачу"), KeyboardButton("❌ Закрыть задачу")],
        [KeyboardButton("👑 Роли участников"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("↩️ Главное меню")],
    ], resize_keyboard=True)


def site_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🌐 Открыть сайт задач", url=SITE_URL)
    ]])


def cancel_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]])


# ──────────────────────────────────────────────
# LIFESPAN
# ──────────────────────────────────────────────
async def _set_webhook_with_retry(url: str, attempts: int = 5):
    delay = 2
    for i in range(1, attempts + 1):
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await bot.set_webhook(url=url, allowed_updates=Update.ALL_TYPES,
                                  drop_pending_updates=True)
            logger.info(f"✅ Webhook установлен: {url}")
            return
        except TelegramError as e:
            logger.warning(f"⚠️ set_webhook попытка {i}/{attempts}: {e}")
            if i == attempts:
                raise
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Планировщик ──
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_reminders, "cron", hour=5, minute=0)   # 8:00 МСК
    scheduler.add_job(send_weekly_digest, "cron", day_of_week="sun", hour=8, minute=0)  # воскресенье 11:00 МСК
    scheduler.start()
    logger.info("✅ Планировщик запущен")

    # ── Telegram Application ──
    tg_app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .connect_timeout(30).read_timeout(30).write_timeout(30)
        .updater(None)
        .build()
    )

    # ConversationHandler: создание задачи
    create_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📝 Создать задачу$"), admin_create_start)],
        states={
            CT_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_got_title)],
            CT_DEPT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_got_dept)],
            CT_DESC:  [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_got_desc)],
            CT_MAX:   [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_got_max)],
            CT_CHECK: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_got_check)],
            CT_DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_got_deadline)],
            CT_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
        per_user=True,
    )

    # ConversationHandler: онбординг нового пользователя
    onboard_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start_handler)],
        states={
            ONBOARD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, onboard_got_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
        per_user=True,
    )

    tg_app.add_handler(onboard_conv)
    tg_app.add_handler(create_conv)
    tg_app.add_handler(CommandHandler("admin", admin_panel_cmd))
    tg_app.add_handler(CommandHandler("profile", profile_cmd))
    tg_app.add_handler(CommandHandler("team", team_cmd))
    tg_app.add_handler(CallbackQueryHandler(callback_handler))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler))

    async def error_handler(update, context):
        logger.error("Telegram error: %s", context.error)

    tg_app.add_error_handler(error_handler)

    await tg_app.initialize()
    await tg_app.start()
    app.state.tg_app = tg_app

    if WEBHOOK_BASE_URL:
        webhook_url = WEBHOOK_BASE_URL.rstrip("/") + WEBHOOK_PATH
        try:
            await _set_webhook_with_retry(webhook_url)
        except Exception as e:
            logger.error(f"❌ Не удалось установить webhook: {e}")
    else:
        logger.warning("⚠️ WEBHOOK_URL/RENDER_EXTERNAL_URL не заданы — webhook не установлен.")

    logger.info("✅ Telegram бот готов")
    yield

    # ── Остановка ──
    try:
        await bot.delete_webhook(drop_pending_updates=False)
    except Exception as e:
        logger.warning(f"delete_webhook: {e}")
    await tg_app.stop()
    await tg_app.shutdown()
    scheduler.shutdown()
    logger.info("✅ Бот остановлен")


# ──────────────────────────────────────────────
# FASTAPI
# ──────────────────────────────────────────────
app = FastAPI(title="TaskBot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# ── Pydantic модели ───────────────────────────────────────────
class RegisterRequest(BaseModel):
    name: str
    telegram_id: int
    telegram_username: str
    task_id: int


class ChecklistUpdate(BaseModel):
    updates: dict


class TaskCreateRequest(BaseModel):
    title: str
    department: str
    description: str
    max_participants: int
    checkpoints: list[dict]  # [{label, date, type: "check"|"deadline"}]


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    max_participants: Optional[int] = None
    checkpoints: Optional[list[dict]] = None


class RoleUpdateRequest(BaseModel):
    role: str


class SubmitRequest(BaseModel):
    telegram_id: int


# ── Публичные эндпоинты ───────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/departments")
def departments(telegram_id: Optional[int] = Query(None)):
    role = get_participant_role(telegram_id) if telegram_id else "member"
    return {"departments": get_departments(role)}


@app.get("/tasks/{department}")
def tasks_by_dept(department: str, telegram_id: Optional[int] = Query(None)):
    role = get_participant_role(telegram_id) if telegram_id else "member"
    return {"tasks": get_tasks_by_department(department, role)}


@app.get("/tasks-open")
def open_tasks(telegram_id: Optional[int] = Query(None)):
    role = get_participant_role(telegram_id) if telegram_id else "member"
    return {"tasks": get_tasks_for_role(role)}


@app.get("/tasks-closed")
def closed_tasks():
    return {"tasks": get_closed_tasks()}


@app.get("/task/{task_id}")
def task_detail(task_id: int):
    task = get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return task


@app.get("/task/{task_id}/participants")
def task_participants(task_id: int):
    return {"participants": get_participants_for_task(task_id)}


@app.get("/participant/{telegram_id}")
def get_participant(telegram_id: int):
    p = get_participant_by_telegram(telegram_id)
    return {"participant": p}


@app.get("/profile/{telegram_id}")
def profile(telegram_id: int):
    return get_user_stats(telegram_id)


@app.get("/leaderboard")
def leaderboard():
    return {"leaderboard": get_leaderboard()}


@app.get("/my-tasks/{telegram_id}")
def my_tasks(telegram_id: int):
    all_p = get_all_participants()
    my = [p for p in all_p if str(p["telegram_id"]) == str(telegram_id)]
    task_map = {str(t["task_id"]): t for t in get_all_tasks()}
    active, history = [], []
    for p in my:
        t = task_map.get(str(p["task_id"]))
        if t:
            if str(t.get("status", "")).lower() == "closed":
                history.append(t)
            else:
                active.append(t)
    return {"active": active, "history": history}


@app.post("/register")
async def register(req: RegisterRequest):
    # Проверка роли: стажёр не может записаться вне отдела Стажёры
    role = get_participant_role(req.telegram_id)
    task = get_task_by_id(req.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if role == "intern" and task.get("department") != INTERN_DEPT:
        raise HTTPException(status_code=403,
                            detail="Стажёры могут записываться только на задачи отдела «Стажёры»")

    success, reason = add_participant(
        req.name, req.telegram_id, req.telegram_username, req.task_id
    )
    if not success:
        if reason == "already_registered":
            raise HTTPException(status_code=400, detail="Ты уже записан на эту задачу")
        raise HTTPException(status_code=400, detail="Нет свободных мест")

    participants = get_participants_for_task(req.task_id)
    tags = " ".join(
        [f"@{p['telegram_username']}" for p in participants if p.get("telegram_username")]
    )
    cps = format_checkpoints(task.get("checkpoints", []))

    await notify(req.telegram_id,
                 f"✅ Ты записался на задачу!\n\n"
                 f"📌 *{task['title']}*\n"
                 f"🏢 Отдел: {task['department']}\n\n"
                 f"{cps}\n\n"
                 f"👥 Команда: {tags if tags else 'пока только ты'}")

    new_tag = f"@{req.telegram_username}"
    for p in participants:
        if str(p["telegram_id"]) != str(req.telegram_id):
            await notify(int(p["telegram_id"]),
                         f"👋 В вашу задачу *{task['title']}* добавился {new_tag}!\n\n"
                         f"👥 Вся команда: {tags}")

    await notify(ORGANIZER_TELEGRAM_ID,
                 f"🔔 Новый участник!\n\n"
                 f"👤 {req.name} ({new_tag})\n"
                 f"📌 Задача: *{task['title']}*\n"
                 f"🏢 Отдел: {task['department']}\n"
                 f"👥 Всего: {len(participants)}/{task['max_participants']}")

    return {"status": "ok"}


@app.post("/task/{task_id}/submit")
async def submit_task(task_id: int, req: SubmitRequest):
    task = get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    p = get_participant_by_telegram(req.telegram_id)
    if not p:
        raise HTTPException(status_code=404, detail="Участник не найден")

    sub_id = submit_task_for_review(
        task_id, req.telegram_id, p["name"], task["title"]
    )

    await notify(ORGANIZER_TELEGRAM_ID,
                 f"📤 *Заявка на сдачу задачи!*\n\n"
                 f"👤 {p['name']} (@{p.get('telegram_username','')})\n"
                 f"📌 {task['title']}\n"
                 f"🏢 {task['department']}",
                 reply_markup=InlineKeyboardMarkup([
                     [
                         InlineKeyboardButton("✅ Принять", callback_data=f"approve_{sub_id}"),
                         InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{sub_id}"),
                     ]
                 ]))

    return {"status": "ok", "submission_id": sub_id}


# ── Эндпоинты для организатора (требуют X-Admin-Secret) ───────
@app.get("/tasks-all")
def all_tasks(x_admin_secret: Optional[str] = Header(None)):
    _require_admin(x_admin_secret)
    return {"tasks": get_all_tasks()}


@app.get("/participants-all")
def all_participants(x_admin_secret: Optional[str] = Header(None)):
    _require_admin(x_admin_secret)
    return {"participants": get_unique_participants()}


@app.post("/task")
def create_task_endpoint(req: TaskCreateRequest,
                          x_admin_secret: Optional[str] = Header(None)):
    _require_admin(x_admin_secret)
    task = create_task(req.title, req.department, req.description,
                       req.max_participants, req.checkpoints)
    return {"status": "ok", "task": task}


@app.put("/task/{task_id}")
def update_task_endpoint(task_id: int, req: TaskUpdateRequest,
                          x_admin_secret: Optional[str] = Header(None)):
    _require_admin(x_admin_secret)
    updates = req.model_dump(exclude_none=True)
    if "checkpoints" in updates:
        import json as _json
        updates["checkpoints"] = _json.dumps(updates["checkpoints"], ensure_ascii=False)
    if not update_task(task_id, updates):
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return {"status": "ok"}


@app.delete("/task/{task_id}")
def delete_task_endpoint(task_id: int, x_admin_secret: Optional[str] = Header(None)):
    _require_admin(x_admin_secret)
    if not delete_task(task_id):
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return {"status": "ok"}


@app.post("/task/{task_id}/close")
def close_task_endpoint(task_id: int, x_admin_secret: Optional[str] = Header(None)):
    _require_admin(x_admin_secret)
    if not close_task(task_id):
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return {"status": "ok"}


@app.post("/participant/{telegram_id}/role")
def set_role(telegram_id: int, req: RoleUpdateRequest,
             x_admin_secret: Optional[str] = Header(None)):
    _require_admin(x_admin_secret)
    if req.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Допустимые роли: {ROLES}")
    if not set_participant_role(telegram_id, req.role):
        raise HTTPException(status_code=404, detail="Участник не найден")
    return {"status": "ok"}


@app.get("/checklist")
def checklist(x_admin_secret: Optional[str] = Header(None)):
    _require_admin(x_admin_secret)
    return {"checklist": get_checklist()}


@app.post("/checklist/update")
def checklist_update(req: ChecklistUpdate,
                     x_admin_secret: Optional[str] = Header(None)):
    _require_admin(x_admin_secret)
    update_checklist(req.updates)
    return {"status": "ok"}


@app.get("/stats/failed")
def failed_stats(x_admin_secret: Optional[str] = Header(None)):
    _require_admin(x_admin_secret)
    return {"failed": get_failed_participants()}


@app.get("/test-reminders")
async def test_reminders(x_admin_secret: Optional[str] = Header(None)):
    _require_admin(x_admin_secret)
    await send_reminders()
    return {"status": "ok"}


# ──────────────────────────────────────────────
# ПЛАНИРОВЩИК: напоминания и дайджест
# ──────────────────────────────────────────────
async def send_reminders():
    logger.info("Проверяем напоминания...")
    for days, prefix in [(3, None), (1, None), (0, None)]:
        for item in get_upcoming_checks(days_ahead=days):
            p, task, label = item["participant"], item["task"], item["label"]
            ev_type = item["event"]
            if days == 3 and ev_type == "deadline":
                text = f"📌 Через 3 дня дедлайн по задаче *{task['title']}*!\nНе забудь."
            elif days == 1:
                icons = {"deadline": "🚨", "check": "⏰"}
                icon = icons.get(ev_type, "⏰")
                text = f"{icon} Завтра {label} по задаче *{task['title']}*!\nБудь готов."
            elif days == 0:
                icons = {"deadline": "🚨", "check": "🔍"}
                icon = icons.get(ev_type, "🔍")
                text = f"{icon} Сегодня {label} по задаче *{task['title']}*!"
            else:
                continue
            await notify(int(p["telegram_id"]), text)


async def send_weekly_digest():
    logger.info("Отправляем еженедельный дайджест...")
    active = get_all_active_participants_for_digest()
    # Группируем по telegram_id
    by_user: dict[str, list] = {}
    for p in active:
        tid = str(p["telegram_id"])
        by_user.setdefault(tid, []).append(p)

    week_end = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    for tid, parts in by_user.items():
        lines = ["📅 *Еженедельный дайджест*\n"]
        upcoming_lines = []
        for p in parts:
            task = get_task_by_id(p["task_id"])
            if not task:
                continue
            lines.append(f"📌 {task['title']} ({task['department']})")
            for cp in task.get("checkpoints", []):
                d = str(cp.get("date", "")).strip()
                if today <= d <= week_end:
                    icon = "🏁" if cp.get("type") == "deadline" else "🔍"
                    upcoming_lines.append(f"  {icon} {cp['label']}: {d}")
        if upcoming_lines:
            lines.append("\n🗓 На этой неделе:")
            lines.extend(upcoming_lines)
        await notify(int(tid), "\n".join(lines))


# ──────────────────────────────────────────────
# TELEGRAM БОТ: хэндлеры
# ──────────────────────────────────────────────

# ── /start + онбординг ────────────────────────
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    existing = get_participant_by_telegram(user.id)

    if existing:
        # Уже зарегистрирован
        await update.message.reply_text(
            f"👋 С возвращением, {existing['name']}!\n"
            f"Роль: {role_label(existing.get('role','intern'))} · "
            f"Баллы: {existing.get('points',0)}",
            reply_markup=main_menu(user.id),
        )
        await update.message.reply_text("Записаться на задачу:", reply_markup=site_button())
        return ConversationHandler.END

    # Новый пользователь — онбординг
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}! Добро пожаловать в студсовет СПбГАСУ!\n\n"
        "Я помогу тебе записываться на задачи и следить за дедлайнами.\n\n"
        "Для начала — как тебя зовут? Введи имя и фамилию:"
    )
    return ONBOARD_NAME


async def onboard_got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("Пожалуйста, введи имя и фамилию.")
        return ONBOARD_NAME

    user = update.effective_user
    context.user_data["onboard_name"] = name

    await update.message.reply_text(
        f"Отлично, {name}! 🎉\n\n"
        f"Ты зарегистрирован как *стажёр*.\n"
        f"Тебе доступны задачи отдела «{INTERN_DEPT}».\n\n"
        f"Когда организатор повысит тебя до участника — откроются задачи всех отделов.\n\n"
        f"🆔 Твой Telegram ID: `{user.id}` — понадобится для записи на сайте.",
        parse_mode="Markdown",
        reply_markup=main_menu(user.id),
    )
    await update.message.reply_text("Записаться на задачу:", reply_markup=site_button())
    return ConversationHandler.END


async def cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Отменено.", reply_markup=main_menu(update.effective_user.id))
    return ConversationHandler.END


# ── /profile ──────────────────────────────────
async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    stats = get_user_stats(user.id)
    role = stats.get("role", "intern")
    await update.message.reply_text(
        f"👤 *Профиль*\n\n"
        f"Имя: {stats.get('name', '—')}\n"
        f"Роль: {role_label(role)}\n"
        f"⭐ Баллы: {stats.get('points', 0)}\n\n"
        f"📋 Активных задач: {stats.get('active_tasks', 0)}\n"
        f"✅ Выполнено: {stats.get('completed_tasks', 0)}\n"
        f"📊 Всего: {stats.get('total_tasks', 0)}",
        parse_mode="Markdown",
        reply_markup=main_menu(user.id),
    )


# ── /team ─────────────────────────────────────
async def team_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    all_p = get_all_participants()
    my = [p for p in all_p if str(p["telegram_id"]) == str(user.id)]
    task_map = {str(t["task_id"]): t for t in get_all_tasks()}
    active = [p for p in my
              if str(task_map.get(str(p["task_id"]), {}).get("status", "")).lower() != "closed"]

    if not active:
        await update.message.reply_text("У тебя нет активных задач.")
        return

    msg = "👥 *Команды по задачам:*\n\n"
    for p in active:
        task = task_map.get(str(p["task_id"]))
        if not task:
            continue
        members = get_participants_for_task(p["task_id"])
        names = "\n".join(
            f"  • {m['name']} @{m.get('telegram_username','')}" for m in members
        )
        msg += f"📌 *{task['title']}*\n{names}\n\n"

    await update.message.reply_text(msg, parse_mode="Markdown",
                                    reply_markup=main_menu(user.id))


# ── /admin ────────────────────────────────────
async def admin_panel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ORGANIZER_TELEGRAM_ID:
        await update.message.reply_text("⛔ Нет доступа.")
        return
    await update.message.reply_text(
        "⚙️ *Панель организатора*\nВыбери действие:",
        parse_mode="Markdown",
        reply_markup=admin_menu(),
    )


# ── Создание задачи (ConversationHandler) ─────
async def admin_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ORGANIZER_TELEGRAM_ID:
        await update.message.reply_text("⛔ Нет доступа.")
        return ConversationHandler.END
    context.user_data["new_task"] = {"checkpoints": []}
    await update.message.reply_text(
        "📝 Создание задачи\n\nШаг 1/6 — Название задачи:",
        reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True),
    )
    return CT_TITLE


async def admin_got_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "❌ Отмена":
        return await cancel_conv(update, context)
    context.user_data["new_task"]["title"] = text

    existing_depts = get_departments("member")
    dept_list = list(dict.fromkeys([INTERN_DEPT] + existing_depts))
    rows = [[d] for d in dept_list] + [["❌ Отмена"]]
    await update.message.reply_text(
        f"Шаг 2/6 — Отдел:\n(или введи новый)",
        reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True),
    )
    return CT_DEPT


async def admin_got_dept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "❌ Отмена":
        return await cancel_conv(update, context)
    context.user_data["new_task"]["department"] = text
    await update.message.reply_text(
        "Шаг 3/6 — Описание задачи (или 'пропустить'):",
        reply_markup=ReplyKeyboardMarkup([["Пропустить"], ["❌ Отмена"]], resize_keyboard=True),
    )
    return CT_DESC


async def admin_got_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "❌ Отмена":
        return await cancel_conv(update, context)
    context.user_data["new_task"]["description"] = "" if text == "Пропустить" else text
    await update.message.reply_text(
        "Шаг 4/6 — Максимальное количество участников (число):",
        reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True),
    )
    return CT_MAX


async def admin_got_max(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "❌ Отмена":
        return await cancel_conv(update, context)
    if not text.isdigit() or int(text) < 1:
        await update.message.reply_text("Введи целое число > 0")
        return CT_MAX
    context.user_data["new_task"]["max_participants"] = int(text)
    await update.message.reply_text(
        "Шаг 5/6 — Промежуточные проверки.\n\n"
        "Отправляй по одной строке в формате:\n`YYYY-MM-DD Название`\n\n"
        "Например: `2025-04-15 Первый чек-ин`\n\n"
        "Когда закончишь — напиши `готово`",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["готово"], ["❌ Отмена"]], resize_keyboard=True),
    )
    return CT_CHECK


async def admin_got_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "❌ Отмена":
        return await cancel_conv(update, context)
    if text.lower() == "готово":
        await update.message.reply_text(
            "Шаг 6/6 — Дедлайн (YYYY-MM-DD):",
            reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True),
        )
        return CT_DEADLINE
    parts = text.split(" ", 1)
    if len(parts) < 2:
        await update.message.reply_text("Формат: `YYYY-MM-DD Название`\nИли напиши `готово`",
                                        parse_mode="Markdown")
        return CT_CHECK
    date_str, label = parts[0].strip(), parts[1].strip()
    context.user_data["new_task"]["checkpoints"].append(
        {"label": label, "date": date_str, "type": "check"}
    )
    await update.message.reply_text(
        f"✅ Добавлено: {label} — {date_str}\n\nЕщё проверку или `готово`:",
        parse_mode="Markdown",
    )
    return CT_CHECK


async def admin_got_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "❌ Отмена":
        return await cancel_conv(update, context)
    context.user_data["new_task"]["checkpoints"].append(
        {"label": "Дедлайн", "date": text, "type": "deadline"}
    )
    nt = context.user_data["new_task"]
    cps_text = format_checkpoints(nt["checkpoints"])
    preview = (
        f"📋 *Превью задачи:*\n\n"
        f"📌 {nt['title']}\n"
        f"🏢 {nt['department']}\n"
        f"📝 {nt.get('description','—')}\n"
        f"👥 Мест: {nt['max_participants']}\n\n"
        f"{cps_text}"
    )
    await update.message.reply_text(preview, parse_mode="Markdown",
                                    reply_markup=ReplyKeyboardMarkup(
                                        [["✅ Опубликовать"], ["❌ Отмена"]],
                                        resize_keyboard=True))
    return CT_CONFIRM


async def admin_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text != "✅ Опубликовать":
        return await cancel_conv(update, context)
    nt = context.user_data["new_task"]
    task = create_task(
        nt["title"], nt["department"], nt.get("description", ""),
        nt["max_participants"], nt["checkpoints"],
    )
    context.user_data.clear()
    await update.message.reply_text(
        f"🎉 Задача опубликована!\n📌 *{task['title']}*\nID: {task['task_id']}",
        parse_mode="Markdown",
        reply_markup=admin_menu(),
    )
    return ConversationHandler.END


# ── Callback-хэндлер (inline кнопки) ─────────
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # Сдать задачу (выбор задачи из инлайн-меню)
    if data.startswith("submit_confirm_"):
        task_id = int(data.split("_")[-1])
        user = update.effective_user
        task = get_task_by_id(task_id)
        p = get_participant_by_telegram(user.id)
        if not task or not p:
            await query.edit_message_text("⚠️ Ошибка. Попробуй снова.")
            return
        sub_id = submit_task_for_review(task_id, user.id, p["name"], task["title"])
        await query.edit_message_text(
            f"📤 Заявка отправлена!\nЗадача: *{task['title']}*\nОжидай ответа организатора.",
            parse_mode="Markdown",
        )
        await notify(ORGANIZER_TELEGRAM_ID,
                     f"📤 *Заявка на сдачу задачи!*\n\n"
                     f"👤 {p['name']} (@{p.get('telegram_username','')})\n"
                     f"📌 {task['title']}",
                     reply_markup=InlineKeyboardMarkup([[
                         InlineKeyboardButton("✅ Принять", callback_data=f"approve_{sub_id}"),
                         InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{sub_id}"),
                     ]]))
        return

    # Одобрить / отклонить сдачу задачи
    if data.startswith("approve_") or data.startswith("reject_"):
        action, sub_id_str = data.split("_", 1)
        sub_id = int(sub_id_str)
        pending = get_pending_submissions()
        sub = next((s for s in pending if int(s.get("submission_id", 0)) == sub_id), None)
        if not sub:
            await query.edit_message_text("⚠️ Заявка уже обработана.")
            return

        p_tid = int(sub["participant_telegram_id"])
        if action == "approve":
            update_submission_status(sub_id, "approved")
            award_points(p_tid, POINTS_PER_TASK)
            await query.edit_message_text(
                f"✅ Принято! {sub['participant_name']} — *{sub['task_title']}*",
                parse_mode="Markdown",
            )
            await notify(p_tid,
                         f"🎉 Твоя задача *{sub['task_title']}* принята!\n"
                         f"⭐ +{POINTS_PER_TASK} баллов!")
        else:
            update_submission_status(sub_id, "rejected")
            await query.edit_message_text(
                f"❌ Отклонено: {sub['participant_name']} — *{sub['task_title']}*",
                parse_mode="Markdown",
            )
            await notify(p_tid,
                         f"😔 Задача *{sub['task_title']}* не принята.\n"
                         f"Обратись к организатору за деталями.")

    # Закрыть задачу (из панели организатора)
    elif data.startswith("admin_close_confirm_"):
        task_id = int(data.split("_")[-1])
        close_task(task_id)
        task = get_task_by_id(task_id)
        await query.edit_message_text(f"✅ Задача закрыта: *{task['title'] if task else task_id}*",
                                      parse_mode="Markdown")

    elif data.startswith("admin_close_"):
        task_id = int(data.split("_")[-1])
        task = get_task_by_id(task_id)
        name = task["title"] if task else str(task_id)
        await query.edit_message_text(
            f"Закрыть задачу *{name}*?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Да", callback_data=f"admin_close_confirm_{task_id}"),
                InlineKeyboardButton("❌ Нет", callback_data="cancel"),
            ]])
        )

    # Управление ролями
    elif data.startswith("admin_setrole_"):
        _, _, tid, role = data.split("_", 3)
        p = get_participant_by_telegram(int(tid))
        name = p["name"] if p else tid
        set_participant_role(int(tid), role)
        await query.edit_message_text(
            f"✅ {name} → *{role_label(role)}*", parse_mode="Markdown"
        )
        await notify(int(tid),
                     f"🎉 Твоя роль изменена на *{role_label(role)}*!\n"
                     + (f"Теперь тебе доступны задачи всех отделов 🚀"
                        if role == "member" else ""))

    elif data.startswith("admin_role_"):
        tid = data.split("_")[-1]
        p = get_participant_by_telegram(int(tid))
        name = p["name"] if p else tid
        await query.edit_message_text(
            f"Роль для {name}:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎓 Стажёр", callback_data=f"admin_setrole_{tid}_intern"),
                InlineKeyboardButton("👤 Участник", callback_data=f"admin_setrole_{tid}_member"),
                InlineKeyboardButton("⚙️ Админ", callback_data=f"admin_setrole_{tid}_admin"),
            ]])
        )

    elif data == "cancel":
        await query.edit_message_text("Отменено.")


# ── Основной хэндлер кнопок ──────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    telegram_id = user.id

    if text == "⚙️ Панель организатора" or text == "↩️ Главное меню":
        if text == "⚙️ Панель организатора":
            if telegram_id != ORGANIZER_TELEGRAM_ID:
                await update.message.reply_text("⛔ Нет доступа.")
                return
            await update.message.reply_text("⚙️ Панель организатора:",
                                            reply_markup=admin_menu())
        else:
            await update.message.reply_text("Главное меню:", reply_markup=main_menu(telegram_id))
        return

    if text == "🆔 Мой Telegram ID":
        await update.message.reply_text(
            f"Твой Telegram ID:\n`{telegram_id}`\n\nВведи его на сайте при записи на задачу.",
            parse_mode="Markdown", reply_markup=main_menu(telegram_id),
        )
        await update.message.reply_text("Записаться:", reply_markup=site_button())

    elif text == "👤 Профиль":
        await profile_cmd(update, context)

    elif text == "📋 Мои задачи":
        all_p = get_all_participants()
        my = [p for p in all_p if str(p["telegram_id"]) == str(telegram_id)]
        task_map = {str(t["task_id"]): t for t in get_all_tasks()}
        active = [task_map[str(p["task_id"])] for p in my
                  if str(p["task_id"]) in task_map
                  and str(task_map[str(p["task_id"])].get("status","")).lower() != "closed"]
        if not active:
            await update.message.reply_text(
                "❌ У тебя нет активных задач.\nЗайди на сайт и выбери задачу!",
                reply_markup=main_menu(telegram_id),
            )
            return
        msg = "📋 *Твои активные задачи:*\n\n"
        for task in active:
            cps = format_checkpoints(task.get("checkpoints", []))
            msg += f"📌 *{task['title']}*\n🏢 {task['department']}\n{cps}\n\n"
        await update.message.reply_text(msg, parse_mode="Markdown",
                                        reply_markup=main_menu(telegram_id))

    elif text == "📅 Ближайшие даты":
        all_p = get_all_participants()
        my = [p for p in all_p if str(p["telegram_id"]) == str(telegram_id)]
        task_map = {str(t["task_id"]): t for t in get_open_tasks()}
        msg = "📅 *Ближайшие даты:*\n\n"
        found = False
        for p in my:
            task = task_map.get(str(p["task_id"]))
            if task:
                found = True
                cps = format_checkpoints(task.get("checkpoints", []))
                msg += f"📌 *{task['title']}*\n{cps}\n\n"
        if not found:
            msg = "✅ Нет активных задач с датами."
        await update.message.reply_text(msg, parse_mode="Markdown",
                                        reply_markup=main_menu(telegram_id))

    elif text == "📁 История":
        all_p = get_all_participants()
        my = [p for p in all_p if str(p["telegram_id"]) == str(telegram_id)]
        task_map = {str(t["task_id"]): t for t in get_closed_tasks()}
        done = [task_map[str(p["task_id"])] for p in my
                if str(p["task_id"]) in task_map]
        if not done:
            await update.message.reply_text("📁 История пуста — выполненных задач ещё нет.",
                                            reply_markup=main_menu(telegram_id))
            return
        msg = "📁 *Выполненные задачи:*\n\n"
        for task in done:
            msg += f"✅ *{task['title']}* — {task['department']}\n"
        await update.message.reply_text(msg, parse_mode="Markdown",
                                        reply_markup=main_menu(telegram_id))

    elif text == "🏆 Рейтинг":
        lb = get_leaderboard()
        if not lb:
            await update.message.reply_text("Рейтинг пуст.", reply_markup=main_menu(telegram_id))
            return
        msg = "🏆 *Рейтинг участников:*\n\n"
        medals = ["🥇", "🥈", "🥉"]
        for i, entry in enumerate(lb[:10]):
            medal = medals[i] if i < 3 else f"{i+1}."
            msg += f"{medal} {entry['name']} — {entry['points']} ⭐ ({entry['tasks']} задач)\n"
        await update.message.reply_text(msg, parse_mode="Markdown",
                                        reply_markup=main_menu(telegram_id))

    elif text == "📤 Сдать задачу":
        all_p = get_all_participants()
        my = [p for p in all_p if str(p["telegram_id"]) == str(telegram_id)]
        task_map = {str(t["task_id"]): t for t in get_open_tasks()}
        active = [(p, task_map[str(p["task_id"])]) for p in my
                  if str(p["task_id"]) in task_map]
        if not active:
            await update.message.reply_text("У тебя нет активных задач.",
                                            reply_markup=main_menu(telegram_id))
            return
        buttons = [
            [InlineKeyboardButton(t["title"], callback_data=f"submit_confirm_{t['task_id']}")]
            for _, t in active
        ]
        await update.message.reply_text(
            "📤 Выбери задачу для сдачи:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    # ── Панель организатора: дополнительные кнопки ──
    elif text == "❌ Закрыть задачу":
        if telegram_id != ORGANIZER_TELEGRAM_ID:
            return
        tasks = get_open_tasks()
        if not tasks:
            await update.message.reply_text("Нет открытых задач.", reply_markup=admin_menu())
            return
        buttons = [
            [InlineKeyboardButton(t["title"], callback_data=f"admin_close_{t['task_id']}")]
            for t in tasks
        ]
        await update.message.reply_text("Выбери задачу для закрытия:",
                                        reply_markup=InlineKeyboardMarkup(buttons))

    elif text == "👑 Роли участников":
        if telegram_id != ORGANIZER_TELEGRAM_ID:
            return
        participants = get_unique_participants()
        if not participants:
            await update.message.reply_text("Участников пока нет.", reply_markup=admin_menu())
            return
        buttons = [
            [InlineKeyboardButton(
                f"{p['name']} [{role_label(p['role'])}]",
                callback_data=f"admin_role_{p['telegram_id']}"
            )]
            for p in participants[:20]  # показываем первые 20
        ]
        await update.message.reply_text("Выбери участника для смены роли:",
                                        reply_markup=InlineKeyboardMarkup(buttons))

    elif text == "📊 Статистика":
        if telegram_id != ORGANIZER_TELEGRAM_ID:
            return
        open_t = get_open_tasks()
        closed_t = get_closed_tasks()
        all_p = get_all_participants()
        failed = get_failed_participants()
        lb = get_leaderboard()
        top = lb[0] if lb else None
        msg = (
            f"📊 *Статистика*\n\n"
            f"📋 Задачи: {len(open_t)} открытых / {len(closed_t)} закрытых\n"
            f"👥 Участников: {len(set(str(p['telegram_id']) for p in all_p))}\n"
            f"❌ Не сдали: {len(failed)}\n"
        )
        if top:
            msg += f"\n🏆 Лидер: {top['name']} — {top['points']} ⭐"
        await update.message.reply_text(msg, parse_mode="Markdown",
                                        reply_markup=admin_menu())




# ──────────────────────────────────────────────
# WEBHOOK
# ──────────────────────────────────────────────
@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        tg_app = request.app.state.tg_app
        upd = Update.de_json(data, tg_app.bot)
        await tg_app.process_update(upd)
    except Exception as e:
        logger.error(f"Webhook упал: {e}")
    return {"ok": True}
