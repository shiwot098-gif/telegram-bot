import os
import sqlite3
import logging
import asyncio
import re
import random
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

# ዳታቤዙ የዕጣ ቁጥርን (ticket_number) ጭምር እንዲይዝ መፍጠር
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
    ከ1 እስከ 3000 ባለው ክልል ውስጥ ያልተደገመ የዕጣ ቁጥር ይፈልጋል
    """
    try:
        cursor.execute("SELECT ticket_number FROM transactions WHERE ticket_number IS NOT NULL")
        used_tickets = {row[0] for row in cursor.fetchall()}
        
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
    ግብይቱ አዲስ ከሆነ ይመዘግባል፣ የዕጣ ቁጥርም አብሮ ይሰጣል
    """
    try:
        cursor.execute("SELECT transaction_id, ticket_number FROM transactions WHERE transaction_id = ?", (tx_id,))
        result = cursor.fetchone()
        
        if result:
            return False, result[1]  # የቆየ ነው፣ የነበረውን የዕጣ ቁጥር ይመልሳል
        
        ticket_number = generate_unique_ticket()
        if ticket_number is None:
            return "FULL", None
            
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO transactions (transaction_id, qr_data, status, ticket_number, created_at) VALUES (?, ?, ?, ?, ?)",
            (tx_id, qr_text, "COMPLETED", ticket_number, current_time)
        )
        conn.commit()
        return True, ticket_number  # አዲስ ነው
    except Exception as e:
        logging.error(f"Database error: {e}")
        return False, None

# =======================
# HANDLERS
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ሰላም! እባክዎ የባንክ ማረጋገጫ የQR ኮድ ፎቶ (Screenshot) በመላክ የዕጣ ቁጥርዎን ይቀበሉ።")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ፎቶዎን ተቀብያለሁ! መረጃውን በፍጥነት እያረጋገጥኩ ነው...")
    
    photo_file = await update.message.photo[-1].get_file()
    photo_path = "user_screenshot.jpg"
    await photo_file.download_to_drive(photo_path)
    
    try:
        # የQR ኮዱን በፍጥነት ማንበብ
        img = cv2.imread(photo_path)
        detector = cv2.QRCodeDetector()
        qr_data, _, _ = detector.detectAndDecode(img)
        
        if qr_data:
            # ከባንክ የQR ሊንክ ላይ ልዩ መለያ ቁጥሩን መቁረጥ (ለምሳሌ፡ ከ v2-hfHCx... ላይ 'hfHCx...' ይወስዳል)
            url_match = re.search(r'v2-([A-Za-z0-9]+)', qr_data)
            if url_match:
                tx_id = url_match.group(1)
            else:
                # ሊንኩ የንግድ ባንክ ካልሆነ የሊንኩን መጨረሻ 15 ፊደላት እንደ መለያ ይወስዳል
                tx_id = qr_data[-15:]

            # በዳታቤዝ ውስጥ ማረጋገጥ እና የዕጣ ቁጥር መስጠት
            is_new, ticket_no = check_and_save_tx(tx_id, qr_data)
            
            if is_new == "FULL":
                await update.message.reply_text("😔 ይቅርታ፣ ሁሉም የ3000 ዕጣ ቁጥሮች አልቀዋል።")
                return
                
            if is_new:
                status_msg = "✅ **አዲስ የግብይት ማረጋገጫ ተረጋግጧል!**"
                ticket_msg = (
                    f"🎉 **እንኳን ደስ አለዎት! የእርስዎ ልዩ የዕጣ ቁጥር፦**\n"
                    f"👇👇👇👇👇👇\n"
                    f"🏆 `【 {ticket_no} 】` 🏆\n"
                    f"👆👆👆👆👆👆\n"
                    f"*(ይህ ቁጥር በፍጹም አይደገምም፤ በጥንቃቄ ይያዙት)*"
                )
            else:
                status_msg = "❌ **ማስጠንቀቂያ፦ ይህ ፎቶ/ግብይት ከዚህ በፊት ተልኳል!**"
                ticket_msg = f"⚠️ ይህ የQR ኮድ ቀደም ሲል ተመዝግቧል። የነበረዎት የዕጣ ቁጥር፦ `【 {ticket_no} 】` ነበር።"
            
            detailed_response = (
                f"{status_msg}\n\n"
                f"🔗 **የባንክ ማረጋገጫ ሊንክ፦**\n`{qr_data}`\n\n"
                f"ℹ️ *ማሳሰቢያ፦ ከላይ ያለውን ሊንክ በመንካት የተላለፈውን የብር መጠን እና የተቀባዩን ስም ማረጋገጥ ይችላሉ።*\n\n"
                f"{ticket_msg}"
            )
            await update.message.reply_text(detailed_response, parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ በምስሉ ላይ የQR ኮድ ማግኘት አልተቻለም። እባክዎ የQR ኮዱ በግልጽ የሚታይበት ሙሉ ፎቶ ይላኩ።")
            
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
    
    print("ቦቱ በከፍተኛ ፍጥነትና በዕጣ ሲስተም ሥራ ጀምሯል...")
    await app.initialize()
    await app.updater.start_polling()
    await app.start()
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
