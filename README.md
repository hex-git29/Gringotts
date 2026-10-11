# Gringotts

Gringotts is a Telegram bot for tracking personal expenses, splitting bills, scanning receipts, and receiving bill reminders. It stores expenses and reminders in a local SQLite database (`finance.db`). Receipt photos are analyzed with the Google Gemini API, and the user's share is added to their expense history.

## Requirements

- Python 3.10 or newer
- A Telegram bot token, created through [@BotFather](https://t.me/BotFather)
- A Google Gemini API key for receipt scanning

## Setup

1. Clone or download this project and open a terminal in its directory.
2. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   On Windows PowerShell, activate it with `.venv\Scripts\Activate.ps1`.

3. Install the packages used by the bot:

   ```bash
   python -m pip install "python-telegram-bot[job-queue]" google-genai python-dotenv
   ```

4. Create a `.env` file in the project directory:

   ```dotenv
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   GEMINI_API_KEY=your_google_gemini_api_key
   ```

   Keep `.env` private. It is excluded from Git. The Google GenAI client reads `GEMINI_API_KEY` from the environment.

## Run the bot

Start polling Telegram updates with:

```bash
python bot.py
```

The bot creates `finance.db` and its tables on startup if they do not already exist. Keep the process running to receive commands and reminders. Stop it with `Ctrl+C`.

## Telegram commands

| Command | Description | Example |
| --- | --- | --- |
| `/start` | Introduce the bot. | `/start` |
| `/help` | Show the available commands. | `/help` |
| `/spend <amount> <category>` | Record an expense in Philippine pesos. Categories may contain spaces. | `/spend 150 Lunch` |
| `/summary` | Show this month's recorded expenses. | `/summary` |
| `/summary all` | Show all-time recorded expenses. | `/summary all` |
| `/split <people> <total> <category>` | Divide a total evenly, then record your share as an expense. | `/split 3 1500 Dinner` |
| `/reminder <MM/DD/YYYY> <bill>` | Set a bill reminder for the given date. | `/reminder 10/15/2026 Internet Bill` |
| `/reset` | Delete your recorded expenses. | `/reset` |

You can also send a receipt photo. Add a caption with the number of people sharing it; for example, `3` splits the receipt equally among three people. To exclude items, include them after the number, such as `3 exclude beer and dessert`. The bot uses Gemini to read the receipt and logs your share. If no caption is provided, it assumes one person.

Reminders are checked about every 60 seconds while the bot is running. Due reminders are sent to the Telegram account that created them.

## Data and credentials

- `finance.db` contains the SQLite expense and reminder records and is local to the project directory.
- `.env` contains API credentials and should not be committed or shared.
- Receipt photos are downloaded temporarily for processing and removed afterward.

The optional `check_models.py` script contacts Google GenAI and prints the models available to the configured API key:

```bash
python check_models.py
```
