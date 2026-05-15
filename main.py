import asyncio
import logging
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
    get_upcoming_checks, get_all_tasks, get_participants_for_task,
    get_all_participants, get_checklist, update_checklist,
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
# FASTAPI
# ──────────────────────────────────────────────
app = FastAPI(title="TaskBot API")

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

@app.get("/departments")
def departments():
    return {"departments": get_departments()}

@app.get("/tasks/{department}")
def tasks_by_dept(department: str):
    return {"tasks": get_tasks_by_department(department)}

@app.get("/tasks-all")
def all_tasks():
    return {"tasks": get_all_tasks()}

@app.get("/task/{task_id}")
def task_detail(task_id: int):
    task = get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return task

@app.get("/task/{task_id}/participants")
def task_participants(task_id: int):
    participants = get_participants_for_task(task_id)
    return {"participants": participants}

@app.get("/participant/{telegram_id}")
def get_participant(telegram_id: int):
    p = get_participant_by_telegram(telegram_id)
    return {"participant": p}

@app.get("/checklist")
def checklist():
    return {"checklist": get_checklist()}

class ChecklistUpdate(BaseModel):
    updates: dict

@app.post("/checklist/update")
def checklist_update(req: ChecklistUpdate):
    update_checklist(req.updates)
    return {"status": "ok"}

@app.post("/register")
async def register(req: RegisterRequest):
    success, reason = add_participant(req.name, req.telegram_id, req.telegram_username, req.task_id)

    if not success:
        if reason == "already_registered":
            raise HTTPException(status_code=400, detail="Ты уже записан на эту задачу")
        raise HTTPException(status_code=400, detail="Нет свободных мест")

    task = get_task_by_id(req.task_id)
    participants = get_participants_for_task(req.task_id)

    # Формируем список участников с тегами
    tags = " ".join([
        f"@{p['telegram_username']}" for p in participants
        if p.get("telegram_username")
    ])

    # Уведомление новому участнику
    await notify(
        req.telegram_id,
        f"✅ Ты записался на задачу!\n\n"
        f"📌 *{task['title']}*\n"
        f"🏢 Отдел: {task['department']}\n"
        f"📅 Проверка 1: {task['check_date_1']}\n"
        f"📅 Проверка 2: {task['check_date_2']}\n"
        f"🏁 Дедлайн: {task['deadline']}\n\n"
        f"👥 Команда: {tags if tags else 'пока только ты'}"
    )

    # Уведомление остальным участникам задачи о новом члене команды
    new_tag = f"@{req.telegram_username}"
    for p in participants:
        if str(p["telegram_id"]) != str(req.telegram_id):
            await notify(
                int(p["telegram_id"]),
                f"👋 В вашу задачу *{task['title']}* добавился новый участник {new_tag}!\n\n"
                f"👥 Вся команда: {tags}"
            )

    # Уведомление организатору
    await notify(
        ORGANIZER_TELEGRAM_ID,
        f"🔔 Новый участник!\n\n"
        f"👤 {req.name} ({new_tag})\n"
        f"📌 Задача: *{task['title']}*\n"
        f"🏢 Отдел: {task['department']}\n"
        f"👥 Всего в задаче: {len(participants)}/{task['max_participants']}"
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
    await update.message.reply_text(
        "Чтобы записаться на задачу — заходи на сайт:",
        reply_markup=site_button()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    telegram_id = update.effective_user.id

    if text == "🆔 Мой Telegram ID":
        await update.message.reply_text(
            f"Твой Telegram ID:\n`{telegram_id}`\n\n"
            f"Введи его на сайте при регистрации.",
            parse_mode="Markdown", reply_markup=main_menu()
        )
        await update.message.reply_text(
            "Перейти на сайт:",
            reply_markup=site_button()
        )

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
                msg += (
                    f"📌 *{task['title']}*\n"
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
            if task:
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
@app.get("/test-reminders")
async def test_reminders():
    await send_reminders()
    return {"status": "ok", "message": "Уведомления отправлены"}
async def send_reminders():
    logger.info("Проверяем напоминания...")

    # За 3 дня до дедлайна
    for item in get_upcoming_checks(days_ahead=3):
        if item["event"] == "deadline":
            p, task = item["participant"], item["task"]
            await notify(int(p["telegram_id"]),
                f"📌 Через 3 дня дедлайн по задаче *{task['title']}*!\nНе забудь.")

    # За 1 день до проверки или дедлайна
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

    # В день дедлайна
    for item in get_upcoming_checks(days_ahead=0):
        if item["event"] == "deadline":
            p, task = item["participant"], item["task"]
            await notify(int(p["telegram_id"]),
                f"🚨 Сегодня дедлайн по задаче *{task['title']}*!\nПоследний день!")


# ──────────────────────────────────────────────
# ЗАПУСК
# ──────────────────────────────────────────────
async def main():
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
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()
    logger.info("✅ Telegram бот запущен")

    import uvicorn
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    logger.info("✅ FastAPI сервер запущен на http://localhost:8000")
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
