import os
import sqlite3
import logging
import asyncio
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

import cv2  # QR ኮዱን በቀጥታ ከፎቶው ላይ ለማንበብ የሚረዳን
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
# HELPERS (ዳታቤዝ መፈተኛ ፎርሙላዎች)
# =======================
def check_and_save_qr(qr_text):
    """
    የQR ኮድ መረጃውን ዳታቤዝ ውስጥ ይፈትሻል።
    ከሌለ ይመዘግባል (True ይመልሳል)፣ ከነበረ ግን False ይመልሳል ማለት ነው።
    """
    try:
        cursor.execute("SELECT qr_data FROM transactions WHERE qr_data = ?", (qr_text,))
        result = cursor.fetchone()
        
        if result:
            return False  # ከዚህ በፊት ተልኳል (የድሮ ነው)
        else:
            # አዲስ ስለሆነ በዳታቤዙ ውስጥ እናስቀምጠዋለን
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # ለጊዜው transaction_id እና qr_data አንድ አይነት አድርገን እንመዝግበው
            cursor.execute(
                "INSERT INTO transactions (transaction_id, qr_data, status, created_at) VALUES (?, ?, ?, ?)",
                (qr_text[:20], qr_text, "COMPLETED", current_time)
            )
            conn.commit()
            return True  # አዲስ ግብይት ነው
    except Exception as e:
        logging.error(f"Database error: {e}")
        return False

# =======================
# HANDLERS (የቦቱ ዋና ተግባራት)
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ሰላም! እንኳን ወደ ቦቱ በሰላም መጡ። እባክዎ የግብይት ማረጋገጫ የQR ኮድ ፎቶ (Screenshot) ይላኩ።")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ፎቶዎን ተቀብያለሁ! መረጃውን በማንበብ ላይ ነኝ፣ እባክዎ ትንሽ ይጠብቁ...")
    
    # ፎቶውን ማውረድ
    photo_file = await update.message.photo[-1].get_file()
    photo_path = "user_screenshot.jpg"
    await photo_file.download_to_drive(photo_path)
    
    try:
        # OpenCV ን በመጠቀም የQR ኮዱን ማንበብ
        img = cv2.imread(photo_path)
        detector = cv2.QRCodeDetector()
        qr_data, bbox, straight_qrcode = detector.detectAndDecode(img)
        
        if qr_data:
            # በዳታቤዝ ውስጥ መፈተሽ
            is_new = check_and_save_qr(qr_data)
            
            if is_new:
                await update.message.reply_text(
                    f"✅ **አዲስ የግብይት ማረጋገጫ!**\n\n"
                    f"የQR መረጃ፦ `{qr_data[:50]}...`\n"
                    f"ይህ መረጃ ከዚህ በፊት አልተላከም፤ አዲስ ነው። በተሳካ ሁኔታ ተመዝግቧል።",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    f"❌ **ማስጠንቀቂያ፦ ድጋሚ የተላከ መረጃ!**\n\n"
                    f"ይህ የQR ኮድ/ግብይት ከዚህ በፊት ተልኮ የተመዘገበ ነው። እባክዎ ትክክለኛውን አዲስ ፎቶ ይላኩ።"
                )
        else:
            await update.message.reply_text(
                "⚠️ በፎቶው ላይ ምንም ዓይነት የQR ኮድ ማግኘት አልቻልኩም። እባክዎ የQR ኮዱ በግልጽ የሚታይበት ፎቶ ድጋሚ ይላኩ።"
            )
            
    except Exception as e:
        logging.error(f"Error processing image: {e}")
        await update.message.reply_text("❌ ፎቶውን በማንበብ ሂደት ላይ ስህተት አጋጥሟል። እባክዎ ድጋሚ ይሞክሩ።")
        
    finally:
        # የወረደውን ጊዜያዊ ፋይል ማጽዳት
        if os.path.exists(photo_path):
            os.remove(photo_path)

# =======================
# MAIN ASYNC FUNCTION
# =======================
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    print("ቦቱ ከነሙሉ መለያ አመክንዮው ሥራ ጀምሯል...")
    
    await app.initialize()
    await app.updater.start_polling()
    await app.start()
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
