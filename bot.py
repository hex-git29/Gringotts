import os
import json
import logging
import sqlite3
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Import the new Gemini SDK modules
from google import genai
from google.genai import types

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

gemini_client = genai.Client()

# ==========================================
# PHASE 2 & 4: DATABASE SETUP
# ==========================================
def init_db():
    """Creates the SQLite database for expenses and reminders if they don't exist."""
    conn = sqlite3.connect('finance.db')
    cursor = conn.cursor()

    # Expenses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            category TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Reminders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            due_date DATE,
            description TEXT,
            is_sent BOOLEAN DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

# ==========================================
# BASIC COMMAND HANDLERS
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Hello {user.first_name}! I am your financial tracking and bill-splitting bot.\n\n"
        "Send /help to see available commands."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "Available commands:\n"
        "/spend <amount> <category> - Log an expense\n"
        "/summary - View total expenses\n"
        "/reminder MM/DD/YYYY <Bill Name> - Set a reminder\n\n"
	"/spend <amount> <category> - Log a personal expense\n"
        "/split <heads> <amount> <category> - Manually split a bill\n"
        "📸 *Receipt Splitting*: Send a photo of a receipt with a number in the caption to split the bill."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

# ==========================================
# PHASE 2: FINANCIAL TRACKING HANDLERS
# ==========================================
async def spend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /spend command. Expected format: /spend 150 Lunch"""
    try:
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /spend <amount> <category>\nExample: /spend 150 Lunch")
            return

        amount = float(context.args[0])
        category = " ".join(context.args[1:]) # Joins multi-word categories
        user_id = update.effective_user.id

        # Insert into database
        conn = sqlite3.connect('finance.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO expenses (user_id, amount, category) VALUES (?, ?, ?)",
                       (user_id, amount, category))
        conn.commit()
        conn.close()

        await update.message.reply_text(f"✅ Logged: ₱{amount:.2f} for {category}")

    except ValueError:
        await update.message.reply_text("Error: Amount must be a number.")
    except Exception as e:
        logger.error(f"Database error: {e}")
        await update.message.reply_text("An error occurred while saving the expense.")

async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Calculates expenses. Defaults to current month. Use /summary all for lifetime."""
    user_id = update.effective_user.id
    show_all = len(context.args) > 0 and context.args[0].lower() == 'all'

    conn = sqlite3.connect('finance.db')
    cursor = conn.cursor()

    if show_all:
        cursor.execute("SELECT SUM(amount) FROM expenses WHERE user_id = ?", (user_id,))
        timeframe = "All-time"
    else:
        cursor.execute("""
            SELECT SUM(amount) FROM expenses
            WHERE user_id = ? AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now', 'localtime')
        """, (user_id,))
        timeframe = "This month's"
    
    total = cursor.fetchone()[0]
    conn.close()

    if total is None:
        total = 0.0

    await update.message.reply_text(f"📊 {timeframe} total expenses: *₱{total:.2f}*", parse_mode='Markdown')

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wipes all expense data for the user to start a fresh session."""
    user_id = update.effective_user.id

    conn = sqlite3.connect('finance.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text("🗑️ All previous expense data cleared. Starting a fresh session!")

# ==========================================
# PHASE 2.5: MANUAL BILL SPLITTING
# ==========================================
async def manual_split(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles manual splitting without a receipt. Usage: /split <heads> <total_amount> <category>"""
    try:
        # Check if the user provided enough arguments
        if len(context.args) < 3:
            await update.message.reply_text(
                "Usage: /split <heads> <total_amount> <category>\n"
                "Example: /split 3 1500 Dinner at Jollibee"
            )
            return

        heads = int(context.args[0])
        total_amount = float(context.args[1])
        category = " ".join(context.args[2:])
        user_id = update.effective_user.id

        if heads < 1:
            await update.message.reply_text("The number of people (heads) must be at least 1.")
            return

        # Calculate the split
        split_cost = total_amount / heads

        # Insert into database
        conn = sqlite3.connect('finance.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO expenses (user_id, amount, category) VALUES (?, ?, ?)",
                       (user_id, split_cost, f"Split: {category}"))
        conn.commit()
        conn.close()

        summary_text = (
            f"💸 *{category}*\n"
            f"Total: ₱{total_amount:.2f}\n"
            f"Split by: {heads} person(s)\n"
            f"👉 *Your Share: ₱{split_cost:.2f}*\n\n"
            f"✅ Logged ₱{split_cost:.2f} to your budget."
        )
        await update.message.reply_text(summary_text, parse_mode='Markdown')

    except ValueError:
        await update.message.reply_text("Error: <heads> must be a whole number and <total_amount> must be a number.")
    except Exception as e:
        logger.error(f"Manual Split Error: {e}")
        await update.message.reply_text("An error occurred while saving the expense.")


# ==========================================
# PHASE 3: RECEIPT OCR AND BILL SPLITTING
# ==========================================
async def process_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles uploaded photos, reads the receipt via Gemini, and logs the expense with optional exclusions."""
    user_id = update.effective_user.id
    caption = update.message.caption.strip() if update.message.caption else "1"

    # Parse caption for heads and exclusions (e.g., "3 exclude beers" or "3 minus desserts")
    parts = caption.split(maxsplit=1)
    try:
        heads = int(parts[0])
        exclusions = parts[1] if len(parts) > 1 else None
    except ValueError:
        await update.message.reply_text("Invalid caption. Please start with a number for the split (e.g., '3' or '3 exclude alcohol'). Defaulting to 1.")
        heads = 1
        exclusions = None

    processing_msg = await update.message.reply_text("📸 Scanning receipt and crunching numbers... please wait.")

    photo_file = await update.message.photo[-1].get_file()
    local_path = f"temp_receipt_{user_id}.jpg"
    await photo_file.download_to_drive(local_path)

    try:
        with open(local_path, "rb") as image_file:
            image_bytes = image_file.read()

        # Build dynamic prompt based on whether there are exclusions
        prompt = f"""
        Analyze this receipt.
        1. Find the store name.
        2. Find the grand total amount.
        """
        
        if exclusions:
            prompt += f"""
        3. The user wants to EXCLUDE these items: "{exclusions}". Find these items on the receipt and sum their prices to get the excluded amount.
        4. Subtract the excluded amount from the grand total to get the adjusted total.
        5. Divide the adjusted total by {heads}.
        """
        else:
            prompt += f"""
        3. The excluded amount is 0. The adjusted total is the grand total.
        4. Divide the adjusted total by {heads}.
        """

        prompt += """
        Return the result strictly as a JSON object with exactly these keys:
        - "store_name": string
        - "original_total": float
        - "excluded_amount": float
        - "adjusted_total": float
        - "split_amount": float
        """

        config = types.GenerateContentConfig(
            response_mime_type="application/json"
        )

        for attempt in range(3):
            try:
                response = gemini_client.models.generate_content(
                    model='gemini-2.5-flash-lite',
                    contents=[
                        types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                        prompt
                    ],
                    config=config
                )
                break
            except Exception as api_error:
                if attempt < 2:
                    logger.warning(f"Network drop. Retrying in 2 seconds... (Attempt {attempt + 1}/3)")
                    await asyncio.sleep(2)
                else:
                    raise api_error
        
        receipt_data = json.loads(response.text)
        store = receipt_data.get("store_name", "Unknown Store")
        orig_total = receipt_data.get("original_total", 0.0)
        excluded = receipt_data.get("excluded_amount", 0.0)
        adj_total = receipt_data.get("adjusted_total", 0.0)
        split_cost = receipt_data.get("split_amount", 0.0)

        conn = sqlite3.connect('finance.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO expenses (user_id, amount, category) VALUES (?, ?, ?)",
                       (user_id, split_cost, f"Receipt: {store}"))
        conn.commit()
        conn.close()

        # Build the summary text
        summary_text = f"🧾 *{store}*\nOriginal Total: ₱{orig_total:.2f}\n"
        if exclusions and excluded > 0:
            summary_text += f"➖ Excluded ({exclusions}): -₱{excluded:.2f}\n"
            summary_text += f"⚖️ Adjusted Total: ₱{adj_total:.2f}\n"
        
        summary_text += (
            f"👥 Split by: {heads} person(s)\n"
            f"👉 *Your Share: ₱{split_cost:.2f}*\n\n"
            f"✅ Logged ₱{split_cost:.2f} to your budget."
        )
        await processing_msg.edit_text(summary_text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"OCR Error: {e}")
        await processing_msg.edit_text("Sorry, I couldn't read that receipt clearly or there was an API error.")
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)


# ==========================================
# PHASE 4: REMINDERS
# ==========================================
async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sets a bill reminder. Usage: /reminder MM/DD/YYYY <Bill Name>"""
    try:
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /reminder MM/DD/YYYY <Bill Name>\nExample: /reminder 10/15/2026 Internet Bill")
            return

        due_date_str = context.args[0]
        description = " ".join(context.args[1:])
        user_id = update.effective_user.id

        # Parse the MM/DD/YYYY format (Capital Y)
        parsed_date = datetime.strptime(due_date_str, "%m/%d/%Y")

        # Convert back to YYYY-MM-DD for the database
        db_date_str = parsed_date.strftime("%Y-%m-%d")

        conn = sqlite3.connect('finance.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO reminders (user_id, due_date, description) VALUES (?, ?, ?)",
                       (user_id, db_date_str, description))
        conn.commit()
        conn.close()

        await update.message.reply_text(f"⏰ Reminder set! I will remind you about '{description}' on {due_date_str}.")

    except ValueError:
        await update.message.reply_text("Error: Date must be in exact MM/DD/YYYY format (e.g., 10/15/2026).")
    except Exception as e:
        logger.error(f"Reminder Error: {e}")
        await update.message.reply_text("An error occurred while saving the reminder.")

async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Background job that runs every 60 seconds to check for due reminders."""
    conn = sqlite3.connect('finance.db')
    cursor = conn.cursor()
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Select reminders where the due date is today or earlier and hasn't been sent
    cursor.execute("SELECT id, user_id, description FROM reminders WHERE due_date <= ? AND is_sent = 0", (today_str,))
    due_reminders = cursor.fetchall()

    for r_id, user_id, description in due_reminders:
        try:
            await context.bot.send_message(
                chat_id=user_id, 
                text=f"🚨 *BILL REMINDER*: Your bill for '{description}' is due!",
                parse_mode='Markdown'
            )
            # Mark as sent
            cursor.execute("UPDATE reminders SET is_sent = 1 WHERE id = ?", (r_id,))
        except Exception as e:
            logger.error(f"Failed to send reminder to {user_id}: {e}")

    conn.commit()
    conn.close()

# ==========================================
# MAIN APP EXECUTION
# ==========================================
if __name__ == '__main__':
    init_db()
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        print("CRITICAL ERROR: TELEGRAM_BOT_TOKEN not found in .env file.")
        exit(1)

    app = ApplicationBuilder().token(token).build()

    # Register Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("spend", spend))
    app.add_handler(CommandHandler("split", manual_split))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("reminder", set_reminder))
    app.add_handler(MessageHandler(filters.PHOTO, process_receipt))

    # Background Job
    job_queue = app.job_queue
    job_queue.run_repeating(check_reminders, interval=60, first=10)

    print("Bot is fully running with all features...")
    app.run_polling()
