import os
import sqlite3
import logging
import asyncio
import re
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

import cv2
import numpy as np
import requests
from bs4 import BeautifulSoup

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
# HELPERS (የባንክ ሊንክ መተንተኛ)
# =======================
def check_and_save_qr(qr_text):
    try:
        cursor.execute("SELECT qr_data FROM transactions WHERE qr_data = ?", (qr_text,))
        result = cursor.fetchone()
        if result:
            return False
        else:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "INSERT INTO transactions (transaction_id, qr_data, status, created_at) VALUES (?, ?, ?, ?)",
                (qr_text[:20], qr_text, "COMPLETED", current_time)
            )
            conn.commit()
            return True
    except Exception as e:
        logging.error(f"Database error: {e}")
        return False

def scrape_cbe_details(url):
    """
    የንግድ ባንክን የሪሲት ሊንክ በመክፈት የብር መጠን፣ የላኪና ተቀባይ ስም ይፈልጋል
    """
    amount = "ያልታወቀ"
    sender = "ያልታወቀ"
    receiver = "ያልታወቀ"
    tx_id = "ያልታወቀ"
    
    try:
        # ሊንኩን መክፈት
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            page_text = soup.get_text()
            
            # በድረገጹ ላይ የገንዘብ መጠን መፈለጊያ (ምሳሌ፡ 2501.20 ETB)
            amt_match = re.search(r'([\d,]+\.\d{2})\s*(?:ETB|ብር)', page_text)
            if amt_match:
                amount = f"{amt_match.group(1)} ETB"
                
            # የግብይት ቁጥር መፈለጊያ (ምሳሌ፡ FT26173N55M2)
            id_match = re.search(r'(FT[A-Z0-9]{10,})', page_text)
            if id_match:
                tx_id = id_match.group(1)
                
            # ላኪና ተቀባይን ለመለየት መሞከሪያ (ይህ እንደ ባንኩ ድረገጽ አወቃቀር ይወሰናል)
            # ለጊዜው ከጽሑፉ ውስጥ ስሞችን ለመፈለግ እንዲረዳ
            lines = [line.strip() for line in page_text.split('\n') if line.strip()]
            for line in lines:
                if "From" in line or "Sender" in line:
                    sender = line
                if "To" in line or "Receiver" in line:
                    receiver = line
                    
    except Exception as e:
        logging.error(f"Scraping error: {e}")
        
    return amount, tx_id, sender, receiver

# =======================
# HANDLERS
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ሰላም! እባክዎ የግብይት ማረጋገጫ የQR ኮድ ፎቶ ይላኩ።")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ፎቶዎን ተቀብያለሁ! መረጃውን ከባንክ ሰርቨር ላይ በማንበብ ላይ ነኝ፣ እባክዎ ጥቂት ሰከንዶችን ይጠብቁ...")
    
    photo_file = await update.message.photo[-1].get_file()
    photo_path = "user_screenshot.jpg"
    await photo_file.download_to_drive(photo_path)
    
    try:
        img = cv2.imread(photo_path)
        detector = cv2.QRCodeDetector()
        qr_data, bbox, straight_qrcode = detector.detectAndDecode(img)
        
        if qr_data:
            # መረጃውን ከሊንኩ ላይ መፈልፈል
            amount, tx_id, sender, receiver = scrape_cbe_details(qr_data)
            
            # ድጋሚ መሆኑን መፈተሽ
            is_new = check_and_save_qr(qr_data)
            status_msg = "✅ **አዲስ የግብይት ማረጋገጫ!**" if is_new else "❌ **ማስጠንቀቂያ፦ ድጋሚ የተላከ (የቆየ) መረጃ!**"
            
            # ምላሽ ማዘጋጀት
            detailed_response = (
                f"{status_msg}\n\n"
                f"📊 **ከባንክ ማረጋገጫው የተገኘ ዝርዝር፦**\n"
                f"🔹 **የገንዘብ መጠን፦** {amount}\n"
                f"🔹 **የግብይት ቁጥር (ID)፦** {tx_id}\n"
                f"🔹 **ላኪ፦** {sender}\n"
                f"🔹 **ተቀባይ፦** {receiver}\n\n"
                f"📝 **የQR ሊንክ፦** [ሊንኩን ለመክፈት ይጫኑ]({qr_data})"
            )
            
            await update.message.reply_text(detailed_response, parse_mode="Markdown", disable_web_page_preview=True)
        else:
            await update.message.reply_text("⚠️ በፎቶው ላይ ምንም ዓይነት የQR ኮድ ማግኘት አልቻልኩም።")
            
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
    
    print("ቦቱ በድረገጽ መተንተኛው ሥራ ጀምሯል...")
    await app.initialize()
    await app.updater.start_polling()
    await app.start()
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
