import os
import sqlite3
import logging
import asyncio
import re  # መረጃዎችን ለመፈልፈል የተጨመረ
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

import cv2
import numpy as np

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
# HELPERS (ዳታቤዝ መፈተኛ)
# =======================
def check_and_save_qr(qr_text):
    try:
        cursor.execute("SELECT qr_data FROM transactions WHERE qr_data = ?", (qr_text,))
        result = cursor.fetchone()
        
        if result:
            return False  # የቆየ ነው
        else:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "INSERT INTO transactions (transaction_id, qr_data, status, created_at) VALUES (?, ?, ?, ?)",
                (qr_text[:20], qr_text, "COMPLETED", current_time)
            )
            conn.commit()
            return True  # አዲስ ነው
    except Exception as e:
        logging.error(f"Database error: {e}")
        return False

def extract_qr_details(qr_text):
    """
    በQR ኮድ ውስጥ ያለውን ጽሑፍ በመመርመር የገንዘብ መጠን፣ ስም እና ID ለመለየት ይሞክራል
    """
    amount = "ያልታወቀ"
    tx_id = "ያልታወቀ"
    
    # በQR ውስጥ የገንዘብ መጠን (Amount) መኖር አለመኖሩን መፈለጊያ (ምሳሌ፡ am=100 ወይም amount=100)
    amt_match = re.search(r'(?:amt|amount|am)=([\d.]+)', qr_text, re.IGNORECASE)
    if amt_match:
        amount = f"{amt_match.group(1)} ETB"
        
    # የግብይት ቁጥር (Transaction ID) መፈለጊያ
    id_match = re.search(r'(?:tx|txn|id|ref)=([A-Z0-9]+)', qr_text, re.IGNORECASE)
    if id_match:
        tx_id = id_match.group(1)

    return amount, tx_id

# =======================
# HANDLERS (የቦቱ ዋና ተግባራት)
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ሰላም! እንኳን ወደ ቦቱ በሰላም መጡ። እባክዎ የግብይት ማረጋገጫ የQR ኮድ ፎቶ ይላኩ።")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ፎቶዎን ተቀብያለሁ! መረጃውን እያነበብኩ ነው...")
    
    photo_file = await update.message.photo[-1].get_file()
    photo_path = "user_screenshot.jpg"
    await photo_file.download_to_drive(photo_path)
    
    try:
        img = cv2.imread(photo_path)
        detector = cv2.QRCodeDetector()
        qr_data, bbox, straight_qrcode = detector.detectAndDecode(img)
        
        if qr_data:
            # በQR ውስጥ ያለውን ዝርዝር መረጃ መፈልፈል
            amount, tx_id = extract_qr_details(qr_data)
            
            # አዲስ ወይም አሮጌ መሆኑን መፈተሽ
            is_new = check_and_save_qr(qr_data)
            
            status_msg = "✅ **አዲስ የግብይት ማረጋገጫ!**" if is_new else "❌ **ማስጠንቀቂያ፦ ድጋሚ የተላከ (የቆየ) መረጃ!**"
            
            # ለተጠቃሚው ዝርዝሩን መናገር
            detailed_response = (
                f"{status_msg}\n\n"
                f"📊 **ከQR ኮዱ የተገኘ ዝርዝር መረጃ፦**\n"
                f"🔹 **የገንዘብ መጠን፦** {amount}\n"
                f"🔹 **የግብይት ቁጥር (ID)፦** {tx_id}\n\n"
                f"📝 **ሙሉ የQR ሊንክ/ጽሑፍ፦**\n`{qr_data}`"
            )
            
            await update.message.reply_text(detailed_response, parse_mode="Markdown")
        else:
            await update.message.reply_text(
                "⚠️ በፎቶው ላይ ምንም ዓይነት የQR ኮድ ማግኘት አልቻልኩም። እባክዎ የQR ኮዱ በግልጽ የሚታይበት ፎቶ ድጋሚ ይላኩ።"
            )
            
    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("❌ ፎቶውን በማንበብ ሂደት ላይ ስህተት አጋጥሟል።")
        
    finally:
        if os.path.exists(photo_path):
            os.remove(photo_path)

# =======================
# MAIN ASYNC FUNCTION
# =======================
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    print("ቦቱ በዝርዝር መረጃ መተንተኛው ሥራ ጀምሯል...")
    await app.initialize()
    await app.updater.start_polling()
    await app.start()
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
