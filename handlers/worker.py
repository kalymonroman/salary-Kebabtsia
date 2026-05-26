def fill_conv():
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📝 Заповнити день$"), fill_start)],
        states={
            LOC:     [MessageHandler(filters.TEXT & ~filters.COMMAND, fill_loc)],
            RATE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, fill_rate)],
            HOURS:   [MessageHandler(filters.TEXT & ~filters.COMMAND, fill_hours)],
            REVENUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, fill_revenue)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", cancel),
        ],
    )

def edit_conv():
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^✏️ Змінити запис$"), edit_start)],
        states={
            EDIT_DATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_date)],
            EDIT_PICK:  [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_pick)],
            EDIT_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_field)],
            EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", cancel),
        ],
    )

def add_day_conv():
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Додати день$"), add_day_start)],
        states={
            ADD_DATE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_day_date)],
            ADD_LOC:     [MessageHandler(filters.TEXT & ~filters.COMMAND, add_day_loc)],
            ADD_RATE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_day_rate)],
            ADD_HOURS:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_day_hours)],
            ADD_REVENUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_day_revenue)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", cancel),
        ],
    )

def del_day_conv():
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🗑 Видалити день$"), del_day_start)],
        states={
            DEL_DATE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, del_day_date)],
            DEL_PICK:    [MessageHandler(filters.TEXT & ~filters.COMMAND, del_day_pick)],
            DEL_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, del_day_confirm)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", cancel),
        ],
    )
