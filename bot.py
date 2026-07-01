import os
import sqlite3
import logging
import asyncio
import re
import random  # ለዕጣ ቁጥር የተጨመረ
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

import cv2
import numpy as np
import easyocr

# =======================
# CONFIG
# =======================
TOKEN = os.getenv("BOT_TOKEN", "8611743019:AAGEHD_MZTciUYBVatUTcJC5uCw-OM5Ij3U")
logging.basicConfig(level=logging.INFO)

# OCR አንባቢን ማዘጋጀት
reader = easyocr.Reader(['en'], gpu=False)

# =======================
# DATABASE SETUP
# =======================
conn = sqlite3.connect("transactions.db", check_same_thread=False)
cursor = conn.cursor()

# ዳታቤዙ ዕጣ ቁጥርን ጭምር እንዲይዝ አድርገን እናሻሽለዋለን
cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT UNIQUE,
    qr_data TEXT UNIQUE,
    status TEXT,
    ticket_number INTEGER UNIQUE,
    created_at TEXT
)
""")
conn.commit()

# =======================
# HELPERS
# =======================
def generate_unique_ticket():
    """
    ከ1 እስከ 3000 ባለው ክልል ውስጥ በዳታቤዝ ውስጥ የሌለ (ያልተደገመ) የዕጣ ቁጥር ይፈልጋል
    """
    try:
        # ሁሉንም እስካሁን የተሰጡ የዕጣ ቁጥሮች ከዳታቤዝ ማውጣት
        cursor.execute("SELECT ticket_number FROM transactions WHERE ticket_number IS NOT NULL")
        used_tickets = {row[0] for row in cursor.fetchall()}
        
        # ሁሉም 3000 ዕጣዎች አልቀው ከሆነ ቁጥር አይሰጥም
        if len(used_tickets) >= 3000:
            return None
            
        while True:
            num = random.randint(1, 3000)
            if num not in used_tickets:
                return num
    except Exception as e:
        logging.error(f"Ticket generation error: {e}")
        return random.randint(1, 3000)

def check_and_save_tx(tx_id, qr_text):
    """
    ግብይቱ አዲስ ከሆነ ይመዘግባል፣ ያልተደገመ የዕጣ ቁጥርም አብሮ ይሰጣል
    """
    try:
        cursor.execute("SELECT transaction_id, ticket_number FROM transactions WHERE transaction_id = ?", (tx_id,))
        result = cursor.fetchone()
        
        if result:
            return False, result[1]  # የቆየ ነው፣ የድሮ ዕጣ ቁጥሩን ይመልሳል
        
        # አዲስ ከሆነ ያልተደገመ ዕጣ ቁጥር ማመንጨት
        ticket_number = generate_unique_ticket()
        
        if ticket_number is None:
            return "FULL", None
            
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO transactions (transaction_id, qr_data, status, ticket_number, created_at) VALUES (?, ?, ?, ?, ?)",
            (tx_id, qr_text, "COMPLETED", ticket_number, current_time)
        )
        conn.commit()
        return True, ticket_number  # አዲስ ነው፣ አዲሱን ዕጣ ቁጥር ይመልሳል
    except Exception as e:
        logging.error(f"Database error: {e}")
        return False, None

def parse_image_text(image_path):
    try:
        results = reader.readtext(image_path, detail=0)
        full_text = " ".join(results)
        
        amount = "ያልታወቀ"
        sender = "ያልታወቀ"
        receiver = "ያልታወቀ"
        tx_id = "ያልታወቀ"
        
        # 1. የብር መጠን መፈለጊያ
        amt_match = re.search(r'(?:Debited|Amount|Total)[:\s]*([\d,]+\.\d{2})', full_text, re.IGNORECASE)
        if amt_match:
            amount = f"{amt_match.group(1)} ETB"
        else:
            amt_match2 = re.search(r'([\d,]+\.\d{2})\s*ETB', full_text)
            if amt_match2:
                amount = f"{amt_match2.group(1)} ETB"

        # 2. የግብይት ቁጥር (Transaction ID) መፈለጊያ
        id_match = re.search(r'(FT[A-Z0-9]{10,})', full_text)
        if id_match:
            tx_id = id_match.group(1)
            
        # 3. ላኪ እና ተቀባይ መፈለጊያ
        sender_match = re.search(r'from\s+([A-Za-z\s\/]+)(?:ETB|for)', full_text, re.IGNORECASE)
        if sender_match:
            sender = sender_match.group(1).strip()
            
        receiver_match = re.search(r'for\s+([A-Za-z\s&]+)(?:ETB|on|Ref)', full_text, re.IGNORECASE)
        if receiver_match:
            receiver = receiver_match.group(1).strip()
            
        return amount, tx_id, sender, receiver
    except Exception as e:
        logging.error(f"OCR Error: {e}")
        return "ያልታወቀ", "ያልታወቀ", "ያልታወቀ", "ያልታወቀ"

# =======================
# HANDLERS
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ሰላም! እባክዎ የባንክ ማረጋገጫ ፎቶ (Screenshot) በመላክ የዕጣ ቁጥርዎን ይቀበሉ።")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ፎቶዎን ተቀብያለሁ! መረጃውን እያረጋገጥኩ ነው፣ እባክዎ ጥቂት ሰከንዶችን ይጠብቁ...")
    
    photo_file = await update.message.photo[-1].get_file()
    photo_path = "user_screenshot.jpg"
    await photo_file.download_to_drive(photo_path)
    
    try:
        # 1. ከፎቶው ላይ ጽሑፎቹን ማንበብ
        amount, tx_id, sender, receiver = parse_image_text(photo_path)
        
        # 2. የQR ኮዱን መፈለግ
        img = cv2.imread(photo_path)
        detector = cv2.QRCodeDetector()
        qr_data, _, _ = detector.detectAndDecode(img)
        
        # የQR ሊንክ ካለና ID ካልተገኘ ከሊንኩ ላይ መለየት
        if qr_data and tx_id == "ያልታወቀ":
            url_match = re.search(r'v2-([A-Za-z0-9]+)', qr_data)
            if url_match:
                tx_id = url_match.group(1)[:12].upper()

        if tx_id != "ያልታወቀ":
            # በዳታቤዝ ውስጥ ማረጋገጥ እና የዕጣ ቁጥር መቀበል
            is_new, ticket_no = check_and_save_tx(tx_id, qr_data if qr_data else "No QR")
            
            if is_new == "FULL":
                await update.message.reply_text("😔 ይቅርታ፣ ሁሉም የ3000 ዕጣ ቁጥሮች አልቀዋል።")
                return
                
            if is_new:
                status_msg = "✅ **አዲስ የግብይት ማረጋገጫ ተረጋግጧል!**"
                ticket_msg = f"🎉 **እንኳን ደስ አለዎት! የእርስዎ ልዩ የዕጣ ቁጥር፦** `【 {ticket_no} 】` \n*(ይህ ቁጥር በፍጹም አይደገምም፤ በጥንቃቄ ይያዙት)*"
            else:
                status_msg = "❌ **ማስጠንቀቂያ፦ ይህ ፎቶ/ግብይት ከዚህ በፊት ተልኳል!**"
                ticket_msg = f"⚠️ ይህ ግብይት ቀደም ሲል ተመዝግቧል። የነበረዎት የዕጣ ቁጥር፦ `【 {ticket_no} 】` ነበር።"
            
            detailed_response = (
                f"{status_msg}\n\n"
                f"📊 **የተገኘ የሪሲት ዝርዝር፦**\n"
                f"Ref ID፦ `{tx_id}`\n"
                f"💰 የገንዘብ መጠን፦ `{amount}`\n"
                f"👤 ላኪ፦ `{sender}`\n"
                f"🏢 ተቀባይ፦ `{receiver}`\n\n"
                f"{ticket_msg}"
            )
            await update.message.reply_text(detailed_response, parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ ሪሲቱን ማንበብ አልተቻለም። እባክዎ የግብይት ቁጥሩ (Ref ID) በግልጽ የሚታይበት ትክክለኛ ፎቶ ይላኩ።")
            
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
    
    print("ቦቱ ከነሙሉ የዕጣ ሲስተሙ ሥራ ጀምሯል...")
    await app.initialize()
    await app.updater.start_polling()
    await app.start()
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
