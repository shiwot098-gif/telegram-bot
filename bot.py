import os
import sqlite3
import re
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

from PIL import Image

# =======================
# CONFIG
# =======================
# Railway ላይ Variable ካልጨመርክ ቦቱ ይህንን ቶከን በቀጥታ ይጠቀማል
TOKEN = os.getenv("BOT_TOKEN", "8611743019:AAGEHD_MZTciUYBVatUTcJC5uCw-OM5Ij3U")

logging.basicConfig(level=logging.INFO)

# =======================
# DATABASE SETUP
# =======================
conn = sqlite3.connect("transactions.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT UNIQUE,
    qr_data TEXT UNIQUE,
    status TEXT,
    created_at TEXT
)
""")
conn.commit()

# =======================
# HANDLERS (የቦቱ ተግባራት)
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ሰላም! እንኳን ወደ ቦቱ በሰላም መጡ።")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # እዚህ ውስጥ ሌሎች መልእክቶችን የምታስተናግድበትን ኮድ መጻፍ ትችላለህ
    await update.message.reply_text("መልእክትዎን ተቀብያለሁ!")

# =======================
# MAIN APPLICATION
# =======================
if __name__ == "__main__":
    # ቦቱን የመቀስቀሻ ክፍል
    app = ApplicationBuilder().token(TOKEN).concurrent_updates(False).build()

    # ትዕዛዞችን ማገናኛ (Handlers)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("ቦቱ ሥራ ጀምሯል...")
    app.run_polling()
