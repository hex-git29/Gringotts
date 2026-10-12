import os
import random
from datetime import datetime, timedelta
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    constants,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv
load_dotenv() 

### List of Gringgots' like quotes to be displayed when bots return to main menu
GRINGGOTS_QUOTES = [
    "🏦 Gringgots: Your gold is safe... probably.",
    "✨ Another day, another Galleon.",
    "🐉 The dragon says your balance looks healthy.",
    "💰 Please keep your hands, wands, and coins inside the vault.",
    "🪙 Every Knut counts. Even the suspicious ones.",
    "🔐 Vault secured. Goblins mildly satisfied.",
    "📜 Your financial destiny awaits, dear wizard.",
    "🐉 Reminder: dragons are expensive to feed.",
    "💎 Wealth is temporary. Goblin bookkeeping is forever.",
    "🧙 Welcome back! Try not to spend it all on potions.",
    "🏦 Gringgots Bank: We count every last Knut.",
    "✨ May your vault overflow and your debts disappear.",
    "🔑 Your vault awaits. The goblins are watching.",
    "💸 A fool and their Galleons are soon parted.",
    "📊 Even magic cannot fix poor budgeting.",
]

### Randomize gringootts quote to be displayed based on list above
def random_gringgots_quote():
    return random.choice(GRINGGOTS_QUOTES)

### Inline keyboard markup for Telegram bot
def keyboard(rows):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text, callback_data=data) 
            for text, data in row] 
        for row in rows
    ])

def main_menu():
    rows = [
        [("🎯 Track", "track"), ("🧾 Split", "split"), ("🗓️ Reminder", "reminder")],
        [("ℹ️ About", "about")],
    ]
    return keyboard(rows)

def track_menu():
    rows = [
        [("💰 Deposit", "deposit"), ("↪️ Transfer", "transfer"), ("💸 Expense", "expense"), ("📊 Summary", "summary")],
        [("🔙 Back to Main Menu", "home")],
    ]
    return keyboard(rows)

def wallet_menu():
    # TODO: Implement wallet menu to be used for deposit and transfer for tracking cash flows, add option for wallet enrollment
    return None

def reminder_menu():
    rows = [
        [("⏰ One-time", "once"), ("🔁 Recurring", "recurring")],
        [("🔙 Back to Main Menu", "home")],
    ]
    return keyboard(rows)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_photo(
        photo="https://static.wikia.nocookie.net/harrypotter/images/6/69/Unidentified_goblin-_HL.jpeg/revision/latest?cb=20230214183715",
        caption="🏦 <b>Welcome to Gringgots, esteemed account holder.</b>\n\n"
                "💰 Your gold is your business. Keeping it accounted for is ours.\n\n"
                "📊 <b>Expenses & Deposits</b> — Every Galleon shall be accounted for.\n\n"
                "🧾 <b>Split Bills</b> — Settle your debts. Goblins forget nothing.\n\n"
                "⏰ <b>Reminders</b> — A missed payment is most... unfortunate.\n\n"
                "🔐 <i>Your vault awaits. Choose your business below, and do mind the gold.</i>\n\n",
        parse_mode=constants.ParseMode.HTML,
        reply_markup=main_menu(),
    )

async def show_menu(query, text, markup):  
    if query.message.photo:
        await query.message.delete()
        await query.message.reply_text(
            text=text,
            reply_markup=markup,
            parse_mode=constants.ParseMode.HTML,
        )
        return

    await query.edit_message_text(
        text=text,
        reply_markup=markup,
        parse_mode=constants.ParseMode.HTML,
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data
    data = context.user_data

    if choice == "home":
        data.clear()
        await show_menu(query, random_gringgots_quote(), main_menu())
        return

    if choice == "track":
        await show_menu(query, "🏦 <b>Track Your Finances</b>", track_menu())
        return

    if choice in ("deposit", "transfer", "expense"):
        data.clear()
        data["flow"] = "transaction"
        data["transaction_type"] = choice
        data["step"] = "amount"

        await show_menu(
            query,
            f"💰 <b>{choice.capitalize()}</b>\n\nEnter the amount:",
            keyboard([[('Cancel', 'home')]]),
        )
        return

    if choice == "summary":
        transactions = data.get("transactions", [])
        if not transactions:
            text = "No transactions recorded in this session yet."
        else:
            lines = [
                f"{item['type'].title()}: {item['amount']:.2f} — {item['note']}"
                for item in transactions
            ]
            text = "📊 <b>Session summary</b>\n\n" + "\n".join(lines)
        await show_menu(
            query, text,
            keyboard([[('🔙 Back to Track', 'track'), ('Home', 'home')]]),
        )
        return

    if choice == "about":
        await show_menu(
            query,
            "🏦 <b>About Gringgots</b>\n\n"
            "Track deposits, transfers and expenses, split a bill, or set a reminder.",
            keyboard([[('🔙 Back to Main Menu', 'home')]]),
        )
        return

    if choice == "split":
        data.clear()
        data["flow"] = "split"
        data["step"] = "receipt"

        await show_menu(
            query,
            "🧾 Send a receipt\n\n"
            "Please upload a receipt photo or image document.",
            keyboard([[("Cancel", "home")]]),
        )
        return

    if choice == "reminder":
        data.clear()
        await show_menu(query, "⏰ Choose a reminder type:", reminder_menu())
        return

    if choice in ("once", "recurring"):
        data.clear()
        data["flow"] = "reminder"
        data["reminder_type"] = choice
        data["step"] = "title"

        await show_menu(
            query,
            "Enter a title for your reminder:",
            keyboard([[("Cancel", "home")]]),
        )
        return

    if choice in ("daily", "weekly", "every15", "custom"):
        if choice == "custom":
            data["step"] = "custom_days"
            await show_menu(
                query,
                "Repeat every how many days? Enter a whole number:",
                keyboard([[("Cancel", "home")]]),
            )
            return

        data["interval_days"] = {
            "daily": 1,
            "weekly": 7,
            "every15": 15,
        }[choice]

        data["step"] = "reminder_time"
        await show_menu(
            query,
            "What time should I remind you? Use 24-hour HH:MM format.\n"
            "Example: 09:00",
            keyboard([[("Cancel", "home")]]),
        )
        return

    await show_menu(
        query,
        "That option isn't available yet.",
        keyboard([[('🔙 Back to Main Menu', 'home')]]),
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    data = context.user_data
    flow = data.get("flow")
    step = data.get("step")

    if not flow or not step:
        await message.reply_text(
            "Choose an action from /start.",
            reply_markup=main_menu(),
        )
        return

    # Receipt upload
    if flow == "split" and step == "receipt":
        if message.photo:
            file_id = message.photo[-1].file_id
        elif message.document and message.document.mime_type == "image/jpeg":
            file_id = message.document.file_id
        elif message.document and message.document.mime_type and \
                message.document.mime_type.startswith("image/"):
            file_id = message.document.file_id
        else:
            await message.reply_text(
                "Please send a photo or image file."
            )
            return

        data["receipt_file_id"] = file_id
        data["step"] = "split_amount"
        await message.reply_text("Receipt received! Enter the total bill amount.")
        return

    if flow == "transaction":
        if not message.text:
            await message.reply_text("Please enter a text value.")
            return

        if step == "amount":
            try:
                amount = float(message.text)
                if amount <= 0:
                    raise ValueError
            except ValueError:
                await message.reply_text("Enter a valid amount greater than zero.")
                return
            data["amount"] = amount
            data["step"] = "note"
            await message.reply_text("Add a note or description for this transaction:")
            return

        if step == "note":
            transactions = data.setdefault("transactions", [])
            transaction = {
                "type": data["transaction_type"],
                "amount": data["amount"],
                "note": message.text.strip(),
            }
            transactions.append(transaction)
            await message.reply_text(
                "✅ Transaction recorded!\n\n"
                f"Type: {transaction['type'].title()}\n"
                f"Amount: {transaction['amount']:.2f}\n"
                f"Note: {transaction['note']}",
                reply_markup=main_menu(),
            )
            data.clear()
            data["transactions"] = transactions
            return

    if flow == "split" and step == "split_amount":
        try:
            amount = float(message.text)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            await message.reply_text("Enter a valid total amount greater than zero.")
            return
        data["split_amount"] = amount
        data["step"] = "participants"
        await message.reply_text("Enter the number of people splitting the bill:")
        return

    if flow == "split" and step == "participants":
        try:
            people = int(message.text)
            if people < 2:
                raise ValueError
        except (ValueError, TypeError):
            await message.reply_text("Enter a whole number of at least 2.")
            return
        amount = data["split_amount"]
        share = amount / people
        data.clear()
        await message.reply_text(
            "✅ Bill split calculated!\n\n"
            f"Total: {amount:.2f}\nPeople: {people}\n"
            f"Each person pays: {share:.2f}",
            reply_markup=main_menu(),
        )
        return

    if flow == "reminder":
        if not message.text:
            await message.reply_text("Please send a text reply.")
            return

        if step == "title":
            data["title"] = message.text.strip()
            data["step"] = "description"
            await message.reply_text("Enter a description:")
            return

        if step == "description":
            data["description"] = message.text.strip()
            if data["reminder_type"] == "once":
                data["step"] = "reminder_datetime"
                await message.reply_text(
                    "Enter the date and time as YYYY-MM-DD HH:MM.\n"
                    "Example: 2026-10-15 09:30"
                )
            else:
                data["step"] = "recurrence_choice"
                await message.reply_text(
                    "Choose a recurrence:",
                    reply_markup=keyboard([
                        [("Every day", "daily"), ("Every week", "weekly")],
                        [("Every 15 days", "every15"), ("Custom X days", "custom")],
                        [("Cancel", "home")],
                    ]),
                )
            return

        if step == "reminder_datetime":
            try:
                target = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
            except ValueError:
                await message.reply_text("Invalid format. Use YYYY-MM-DD HH:MM.")
                return
            delay = (target - datetime.now()).total_seconds()
            if delay <= 0:
                await message.reply_text("Please choose a future date and time.")
                return
            title, description = data["title"], data["description"]
            context.job_queue.run_once(
                send_reminder, when=delay, chat_id=update.effective_chat.id,
                data={"title": title, "description": description},
                name=f"once_{update.effective_user.id}_{target.timestamp()}",
            )
            data.clear()
            await message.reply_text(
                f"✅ Reminder scheduled for {target:%Y-%m-%d %H:%M}.\nTitle: {title}",
                reply_markup=main_menu(),
            )
            return

        if step == "custom_days":
            try:
                days = int(message.text)
                if days < 1:
                    raise ValueError
            except ValueError:
                await message.reply_text("Enter a whole number of at least 1.")
                return
            data["interval_days"] = days
            data["step"] = "reminder_time"
            await message.reply_text("What time? Use 24-hour HH:MM format, e.g. 09:00.")
            return

        if step == "reminder_time":
            try:
                reminder_time = datetime.strptime(message.text, "%H:%M").time()
            except ValueError:
                await message.reply_text("Enter a valid time like 09:00.")
                return
            now = datetime.now()
            first = datetime.combine(now.date(), reminder_time)
            if first <= now:
                first += timedelta(days=1)
            title, description = data["title"], data["description"]
            interval_days = data["interval_days"]
            context.job_queue.run_repeating(
                send_reminder, interval=interval_days * 86400,
                first=(first - now).total_seconds(),
                chat_id=update.effective_chat.id,
                data={"title": title, "description": description},
                name=f"repeat_{update.effective_user.id}_{now.timestamp()}",
            )
            data.clear()
            await message.reply_text(
                "🔁 Recurring reminder scheduled!\n\n"
                f"Title: {title}\nRepeats every {interval_days} day(s), at {reminder_time:%H:%M}.",
                reply_markup=main_menu(),
            )
            return

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    await context.bot.send_message(
        chat_id=job.chat_id,
        text=f"⏰ Reminder: {job.data['title']}\n\n{job.data['description']}",
    )

async def process_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # TODO: Implement receipt processing logic using Gemini
    return

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Cancelled. Use /start to open the menu.",
        reply_markup=main_menu(),
    )

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Please set the TELEGRAM_BOT_TOKEN environment variable."
        )

    app = (
        Application.builder()
        .token(token)
        .concurrent_updates(False)
        .build()
    )
    if app.job_queue is None:
        raise RuntimeError(
            'Reminder scheduling requires the JobQueue extra. '
            'Install dependencies with: pip install -r requirements.txt'
        )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(
        MessageHandler(
            (filters.TEXT & ~filters.COMMAND) | filters.PHOTO | filters.Document.IMAGE,
            handle_message,
        )
    )

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
