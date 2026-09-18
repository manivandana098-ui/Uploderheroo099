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
