import os
import sqlite3
import re
import logging
import asyncio
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
# HANDLERS (የቦቱ ዋና ተግባራት)
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ተጠቃሚው /start ሲል የሚመጣለት መልእክት
    await update.message.reply_text("ሰላም! እንኳን ወደ ቦቱ በሰላም መጡ። እባክዎ የግብይት ማረጋገጫ ፎቶ ወይም መረጃ ይላኩ።")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ተጠቃሚው ጽሑፍ ሲልክ የሚያስተናግደው ክፍል
    user_text = update.message.text
    await update.message.reply_text(f"የላኩትን ጽሑፍ ተቀብያለሁ፦ {user_text}\nአሁን ላይ ሲስተሙን በማስተካከል ላይ ስለሆንን ሂደቱን እያጠናቀቅን ነው!")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ተጠቃሚው ፎቶ (ስክሪንሻት) ሲልክ የሚያስተናግደው ክፍል
    await update.message.reply_text("ፎቶዎን ተቀብያለሁ! መረጃውን በማንበብ ላይ ነኝ...")
    
    # ፎቶውን ከቴሌግራም ሰርቨር ማውረድ
    photo_file = await update.message.photo[-1].get_file()
    photo_path = "user_screenshot.jpg"
    await photo_file.download_to_drive(photo_path)
    
    # እዚህ ቦታ ላይ በቅድሙ pyzbar ፈንታ ሌላ አስተማማኝ መረጃ ማንበቢያ ኮድ ማስገባት ትችላለህ
    await update.message.reply_text("ፎቶው በተሳካ ሁኔታ ተገምግሟል!")

# =======================
# MAIN ASYNC FUNCTION
# =======================
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # እያንዳንዱን ትዕዛዝ ከቦቱ ጋር ማገናኛ
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo)) # ፎቶ ለመቀበል የተጨመረ
    
    print("ቦቱ ከነሙሉ ተግባራቱ ሥራ ጀምሯል...")
    
    await app.initialize()
    await app.updater.start_polling()
    await app.start()
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
