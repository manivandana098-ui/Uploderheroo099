import logging
import sqlite3
import asyncio
import random
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8967644405:AAG240zwz591Sm4rLBscVt9E9q2BbAtbqJs"
ADMIN_ID = 7652646233

# Helper function to ensure Telegram channel IDs have the mandatory '-100' prefix
def format_tg_id(channel_id: int) -> int:
    str_id = str(channel_id)
    if not str_id.startswith("-100"):
        raw_id = str_id.lstrip("-")
        return int(f"-100{raw_id}")
    return channel_id

# Configured Channel Pairs
RAW_CHANNEL_PAIRS = [
    [-3283636038, -3240248684],  # Pair 1
    [-3854115136, -2386439443],  # Pair 2
    [-2941230737, -3986889384],  # Pair 3
    [-3269447321, -3850962058],  # Pair 4
    [-3449764121, -3722960006],  # Pair 5
    [-3791628873, -3986889384],  # Pair 6
]

CHANNEL_PAIRS = [[format_tg_id(cid) for cid in pair] for pair in RAW_CHANNEL_PAIRS]

BATCH_SIZE_PER_PAIR = 25          # Har pair me 25 posts jayengi
BREAK_AFTER_ALL_PAIRS_HOURS = 4  # All pairs complete hone ke baad 4 hrs cooldown

# Human-like delay range (Seconds)
MIN_HUMAN_DELAY = 3
MAX_HUMAN_DELAY = 7
# =======================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def init_db():
    conn = sqlite3.connect('scheduler.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_type TEXT,
            text TEXT,
            file_id TEXT,
            caption TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS tracker (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_pointer INTEGER DEFAULT 0
        )
    ''')
    c.execute("INSERT OR IGNORE INTO tracker (id, last_pointer) VALUES (1, 0)")
    conn.commit()
    conn.close()

init_db()

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "🤖 **Channel Automation Bot Active!**\n\n"
        "Mujhe Posts/Videos/Photos/Text send karein. Main queue me save karta rahunga.\n\n"
        "**Commands:**\n"
        "• /status - Queue aur current post pointer check karein\n"
        "• /post_now - Manually abhi posting cycle start karein\n"
        "• /clear_queue - Saari saved posts delete karein\n"
        "• /reset_pointer - Loop ko post #1 par reset karein"
    )

async def add_to_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    msg = update.message
    conn = sqlite3.connect('scheduler.db')
    c = conn.cursor()

    if msg.photo:
        file_id = msg.photo[-1].file_id
        caption = msg.caption or ""
        c.execute("INSERT INTO queue (message_type, file_id, caption) VALUES (?, ?, ?)", ('photo', file_id, caption))
    elif msg.video:
        file_id = msg.video.file_id
        caption = msg.caption or ""
        c.execute("INSERT INTO queue (message_type, file_id, caption) VALUES (?, ?, ?)", ('video', file_id, caption))
    elif msg.document:
        file_id = msg.document.file_id
        caption = msg.caption or ""
        c.execute("INSERT INTO queue (message_type, file_id, caption) VALUES (?, ?, ?)", ('document', file_id, caption))
    elif msg.text:
        c.execute("INSERT INTO queue (message_type, text) VALUES (?, ?)", ('text', msg.text))

    conn.commit()
    conn.close()
    await update.message.reply_text("📥 Saved to Queue!")

async def run_full_posting_cycle(context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('scheduler.db')
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM queue")
    total_posts = c.fetchone()[0]

if total_posts == 0:
        logging.info("Queue is empty. Waiting for posts...")
        conn.close()
        return

    c.execute("SELECT last_pointer FROM tracker WHERE id = 1")
    current_pointer = c.fetchone()[0]

    for pair_index, channel_group in enumerate(CHANNEL_PAIRS, start=1):
        c.execute("SELECT id, message_type, text, file_id, caption FROM queue WHERE id > ? ORDER BY id ASC LIMIT ?", 
                  (current_pointer, BATCH_SIZE_PER_PAIR))
        posts = c.fetchall()

        if len(posts) < BATCH_SIZE_PER_PAIR:
            needed = BATCH_SIZE_PER_PAIR - len(posts)
            c.execute("SELECT id, message_type, text, file_id, caption FROM queue ORDER BY id ASC LIMIT ?", (needed,))
            extra_posts = c.fetchall()
            posts.extend(extra_posts)

        if not posts:
            continue

        logging.info(f"Publishing Batch for Pair {pair_index}...")

        for post in posts:
            post_id, msg_type, text, file_id, caption = post

            for channel_id in channel_group:
                try:
                    if msg_type == 'text':
                        await context.bot.send_message(chat_id=channel_id, text=text)
                    elif msg_type == 'photo':
                        await context.bot.send_photo(chat_id=channel_id, photo=file_id, caption=caption)
                    elif msg_type == 'video':
                        await context.bot.send_video(chat_id=channel_id, video=file_id, caption=caption)
                    elif msg_type == 'document':
                        await context.bot.send_document(chat_id=channel_id, document=file_id, caption=caption)
                    
                    await asyncio.sleep(random.uniform(MIN_HUMAN_DELAY, MAX_HUMAN_DELAY))

                except Exception as e:
                    logging.error(f"Error posting item {post_id} to channel {channel_id}: {e}")

            current_pointer = post_id

        c.execute("UPDATE tracker SET last_pointer = ? WHERE id = 1", (current_pointer,))
        conn.commit()

    conn.close()

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"✅ **Full Cycle Completed (Pair 1 to Pair 6)!**\n"
                 f"Cooldown Active: Agla batch {BREAK_AFTER_ALL_PAIRS_HOURS} ghante me start hoga."
        )
    except Exception as e:
        logging.error(f"Failed to alert admin: {e}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    conn = sqlite3.connect('scheduler.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM queue")
    total = c.fetchone()[0]

    c.execute("SELECT last_pointer FROM tracker WHERE id = 1")
    pointer = c.fetchone()[0]
    conn.close()

    await update.message.reply_text(
        f"📊 **Bot Status:**\n\n"
        f"📦 Total Posts in Queue: `{total}`\n"
        f"📍 Current Pointer: Post #{pointer}\n"
        f"🔄 Configured Pairs: `{len(CHANNEL_PAIRS)}`\n"
        f"⏳ Cooldown Interval: Every {BREAK_AFTER_ALL_PAIRS_HOURS} Hours"
    )

async def force_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("🚀 Manual cycle trigger kar di gayi hai...")
    await run_full_posting_cycle(context)

async def clear_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    conn = sqlite3.connect('scheduler.db')
    c = conn.cursor()
    c.execute("DELETE FROM queue")
    c.execute("UPDATE tracker SET last_pointer = 0 WHERE id = 1")
    conn.commit()
    conn.close()

    await update.message.reply_text("🗑 Queue clear kar di gayi aur pointer #0 par reset kar diya gaya.")

async def reset_pointer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

conn = sqlite3.connect('scheduler.db')
    c = conn.cursor()
    c.execute("UPDATE tracker SET last_pointer = 0 WHERE id = 1")
    conn.commit()
    conn.close()

    await update.message.reply_text("🔄 Pointer reset! Ab agli posting Post #1 se shuru hogi.")

if name == 'main':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    job_queue = app.job_queue
    job_queue.run_repeating(
        run_full_posting_cycle, 
        interval=BREAK_AFTER_ALL_PAIRS_HOURS * 3600, 
        first=10
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("post_now", force_post))
    app.add_handler(CommandHandler("clear_queue", clear_queue))
    app.add_handler(CommandHandler("reset_pointer", reset_pointer))

    app.add_handler(MessageHandler(
        (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL) & (~filters.COMMAND),
        add_to_queue
    ))

    print("Bot is running with 6 configured pairs and 4-hour cooldown...")
    app.run_polling()
