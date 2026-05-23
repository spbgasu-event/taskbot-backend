import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import Update

from sheets import (
    get_departments, get_tasks_by_department, get_task_by_id,
    add_participant, get_participant_by_telegram,
    get_upcoming_checks, get_all_tasks, get_open_tasks, get_closed_tasks,
    get_participants_for_task, get_all_participants,
    get_checklist, update_checklist, close_task, get_failed_participants,
)

# ──────────────────────────────────────────────
# НАСТРОЙКИ
# ──────────────────────────────────────────────
TELEGRAM_TOKEN = "8930763288:AAH6VHTtUhRnlLWyLykd8OUkHxDVkIvyMB8"
ORGANIZER_TELEGRAM_ID = 1251988176
SITE_URL = "https://spbgasu-event.github.io/taskbot-site/"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_TOKEN)

# ──────────────────────────────────────────────
# LIFESPAN — запуск и остановка бота вместе с сервером
# ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- СТАРТ ---
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_reminders, "cron", hour=5, minute=0)  # 5:00 UTC = 8:00 МСК
    scheduler.start()
    logger.info("✅ Планировщик запущен")

    tg_app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .build()
    )
    tg_app.add_handler(CommandHandler("start", start_handler))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler))

    async def error_handler(update, context):
        logger.error("Telegram error: %s", context.error)

    tg_app.add_error_handler(error_handler)

    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    logger.info("✅ Telegram бот запущен")

    yield  # сервер работает

    # --- ОСТАНОВКА ---
    await tg_app.updater.stop()
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
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class RegisterRequest(BaseModel):
    name: str
    telegram_id: int
    telegram_username: str
    task_id: int

class ChecklistUpdate(BaseModel):
    updates: dict

# Отделы (только открытые задачи)
@app.get("/departments")
def departments():
    return {"departments": get_departments()}

# Задачи отдела (только открытые)
@app.get("/tasks/{department}")
def tasks_by_dept(department: str):
    return {"tasks": get_tasks_by_department(department)}

# Все задачи (для организатора)
@app.get("/tasks-all")
def all_tasks():
    return {"tasks": get_all_tasks()}

# Только открытые задачи (для сайта)
@app.get("/tasks-open")
def open_tasks():
    return {"tasks": get_open_tasks()}

# Только закрытые задачи
@app.get("/tasks-closed")
def closed_tasks():
    return {"tasks": get_closed_tasks()}

# Детали задачи
@app.get("/task/{task_id}")
def task_detail(task_id: int):
    task = get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return task

# Участники задачи
@app.get("/task/{task_id}/participants")
def task_participants(task_id: int):
    return {"participants": get_participants_for_task(task_id)}

# Закрыть задачу
@app.post("/task/{task_id}/close")
def close_task_endpoint(task_id: int):
    success = close_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return {"status": "ok"}

# Участник по Telegram ID
@app.get("/participant/{telegram_id}")
def get_participant(telegram_id: int):
    p = get_participant_by_telegram(telegram_id)
    return {"participant": p}

# Все участники
@app.get("/participants-all")
def all_participants():
    return {"participants": get_all_participants()}

# Чеклист
@app.get("/checklist")
def checklist():
    return {"checklist": get_checklist()}

# Обновить чеклист
@app.post("/checklist/update")
def checklist_update(req: ChecklistUpdate):
    update_checklist(req.updates)
    return {"status": "ok"}

# Статистика невыполненных
@app.get("/stats/failed")
def failed_stats():
    return {"failed": get_failed_participants()}

# Запись на задачу
@app.post("/register")
async def register(req: RegisterRequest):
    success, reason = add_participant(req.name, req.telegram_id, req.telegram_username, req.task_id)

    if not success:
        if reason == "already_registered":
            raise HTTPException(status_code=400, detail="Ты уже записан на эту задачу")
        raise HTTPException(status_code=400, detail="Нет свободных мест")

    task = get_task_by_id(req.task_id)
    participants = get_participants_for_task(req.task_id)

    tags = " ".join([f"@{p['telegram_username']}" for p in participants if p.get("telegram_username")])

    await notify(req.telegram_id,
        f"✅ Ты записался на задачу!\n\n"
        f"📌 *{task['title']}*\n"
        f"🏢 Отдел: {task['department']}\n"
        f"📅 Проверка 1: {task['check_date_1']}\n"
        f"📅 Проверка 2: {task['check_date_2']}\n"
        f"🏁 Дедлайн: {task['deadline']}\n\n"
        f"👥 Команда: {tags if tags else 'пока только ты'}"
    )

    new_tag = f"@{req.telegram_username}"
    for p in participants:
        if str(p["telegram_id"]) != str(req.telegram_id):
            await notify(int(p["telegram_id"]),
                f"👋 В вашу задачу *{task['title']}* добавился {new_tag}!\n\n"
                f"👥 Вся команда: {tags}"
            )

    await notify(ORGANIZER_TELEGRAM_ID,
        f"🔔 Новый участник!\n\n"
        f"👤 {req.name} ({new_tag})\n"
        f"📌 Задача: *{task['title']}*\n"
        f"🏢 Отдел: {task['department']}\n"
        f"👥 Всего: {len(participants)}/{task['max_participants']}"
    )

    return {"status": "ok"}


# ──────────────────────────────────────────────
# TELEGRAM БОТ
# ──────────────────────────────────────────────
async def notify(telegram_id: int, message: str):
    try:
        await bot.send_message(chat_id=telegram_id, text=message, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка отправки {telegram_id}: {e}")

def main_menu():
    keyboard = [
        [KeyboardButton("📋 Мои задачи")],
        [KeyboardButton("🆔 Мой Telegram ID")],
        [KeyboardButton("📅 Ближайшие даты")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def site_button():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🌐 Открыть сайт задач", url=SITE_URL)
    ]])

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\nЯ бот студсовета. Выбери что тебя интересует 👇",
        reply_markup=main_menu()
    )
    await update.message.reply_text("Чтобы записаться на задачу — заходи на сайт:", reply_markup=site_button())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    telegram_id = update.effective_user.id

    if text == "🆔 Мой Telegram ID":
        await update.message.reply_text(
            f"Твой Telegram ID:\n`{telegram_id}`\n\nВведи его на сайте при регистрации.",
            parse_mode="Markdown", reply_markup=main_menu()
        )
        await update.message.reply_text("Перейти на сайт:", reply_markup=site_button())

    elif text == "📋 Мои задачи":
        all_p = get_all_participants()
        my = [p for p in all_p if str(p["telegram_id"]) == str(telegram_id)]
        if not my:
            await update.message.reply_text(
                "❌ Ты ещё не записан ни на одну задачу.\nЗайди на сайт и выбери задачу!",
                reply_markup=main_menu()
            )
            return
        msg = "📋 *Твои задачи:*\n\n"
        for p in my:
            task = get_task_by_id(p["task_id"])
            if task:
                status = " 🔒 _закрыта_" if str(task.get("status", "")).lower() == "closed" else ""
                msg += (
                    f"📌 *{task['title']}*{status}\n"
                    f"🏢 {task['department']}\n"
                    f"📅 Проверка 1: {task['check_date_1']}\n"
                    f"📅 Проверка 2: {task['check_date_2']}\n"
                    f"🏁 Дедлайн: {task['deadline']}\n\n"
                )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu())

    elif text == "📅 Ближайшие даты":
        all_p = get_all_participants()
        my = [p for p in all_p if str(p["telegram_id"]) == str(telegram_id)]
        if not my:
            await update.message.reply_text("❌ Ты ещё не записан ни на одну задачу.", reply_markup=main_menu())
            return
        msg = "📅 *Ближайшие даты:*\n\n"
        for p in my:
            task = get_task_by_id(p["task_id"])
            if task and str(task.get("status", "")).lower() != "closed":
                msg += (
                    f"📌 *{task['title']}*\n"
                    f"🔍 Проверка 1: {task['check_date_1']}\n"
                    f"🔍 Проверка 2: {task['check_date_2']}\n"
                    f"🏁 Дедлайн: {task['deadline']}\n\n"
                )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu())


# ──────────────────────────────────────────────
# ПЛАНИРОВЩИК
# ──────────────────────────────────────────────
async def send_reminders():
    logger.info("Проверяем напоминания...")

    for item in get_upcoming_checks(days_ahead=3):
        if item["event"] == "deadline":
            p, task = item["participant"], item["task"]
            await notify(int(p["telegram_id"]),
                f"📌 Через 3 дня дедлайн по задаче *{task['title']}*!\nНе забудь.")

    for item in get_upcoming_checks(days_ahead=1):
        p, task, event = item["participant"], item["task"], item["event"]
        if event == "check_date_1":
            text = f"⏰ Завтра проверка 1 по задаче *{task['title']}*!\nБудь готов."
        elif event == "check_date_2":
            text = f"⏰ Завтра проверка 2 по задаче *{task['title']}*!\nБудь готов."
        elif event == "deadline":
            text = f"🚨 Завтра дедлайн по задаче *{task['title']}*!\nУспей сдать."
        else:
            continue
        await notify(int(p["telegram_id"]), text)

    for item in get_upcoming_checks(days_ahead=0):
        p, task, event = item["participant"], item["task"], item["event"]
        if event == "check_date_1":
            text = f"🔍 Сегодня проверка 1 по задаче *{task['title']}*!\nБудь готов."
        elif event == "check_date_2":
            text = f"🔍 Сегодня проверка 2 по задаче *{task['title']}*!\nБудь готов."
        elif event == "deadline":
            text = f"🚨 Сегодня дедлайн по задаче *{task['title']}*!\nПоследний день!"
        else:
            continue
        await notify(int(p["telegram_id"]), text)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/test-reminders")
async def test_reminders():
    await send_reminders()
    return {"status": "ok", "message": "Уведомления отправлены"}
