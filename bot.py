import os
import sqlite3
import re
import logging
import asyncio  # ይህ አዲስ የተጨመረ ነው
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

from PIL import Image

# =======================
# CONFIG
# =======================
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
    await update.message.reply_text("መልእክትዎን ተቀብያለሁ!")

# =======================
# MAIN ASYNC FUNCTION
# =======================
async def main():
    # ለአዲሱ Python 3.13 እንዲስማማ ተደርጎ የተዋቀረ
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("ቦቱ ሥራ ጀምሯል...")
    
    # በውስጥ ለውስጥ የሚፈጠረውን የUpdater ችግር የሚፈታው ይሄኛው አወቃቀር ነው
    await app.initialize()
    await app.updater.start_polling()
    await app.start()
    
    # ቦቱ ሳይጠፋ እንዲቆይ ማድረግ
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    # Python 3.13 ላይ በሰላም እንዲነሳ loop ውስጥ እናስገድደዋለን
    asyncio.run(main())
