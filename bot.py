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

cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT,
    qr_data TEXT,
    status TEXT,
    ticket_number INTEGER,
    created_at TEXT
)
""")
conn.commit()

# =======================
# HELPERS
# =======================
def generate_multiple_tickets(count):
    try:
        cursor.execute("SELECT ticket_number FROM transactions WHERE ticket_number IS NOT NULL")
        used_tickets = {row[0] for row in cursor.fetchall()}
        
        if len(used_tickets) + count > 3000:
            return []
            
        new_tickets = []
        while len(new_tickets) < count:
            num = random.randint(1, 3000)
            if num not in used_tickets and num not in new_tickets:
                new_tickets.append(num)
        return new_tickets
    except Exception as e:
        logging.error(f"Ticket error: {e}")
        return [random.randint(1, 3000) for _ in range(count)]

def check_and_save_tickets(tx_id, qr_text, amount_value):
    try:
        cursor.execute("SELECT ticket_number FROM transactions WHERE transaction_id = ?", (tx_id,))
        results = cursor.fetchall()
        
        if results:
            return False, [row[0] for row in results]
        
        # ለእያንዳንዱ 2500 ብር 1 ትኬት ማሰላት
        ticket_count = int(amount_value // 2500)
        if ticket_count < 1:
            ticket_count = 1
            
        ticket_numbers = generate_multiple_tickets(ticket_count)
        if not ticket_numbers:
            return "FULL", None
            
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for t_num in ticket_numbers:
            cursor.execute(
                "INSERT INTO transactions (transaction_id, qr_data, status, ticket_number, created_at) VALUES (?, ?, ?, ?, ?)",
                (tx_id, qr_text, "COMPLETED", t_num, current_time)
            )
        conn.commit()
        return True, ticket_numbers
    except Exception as e:
        logging.error(f"Database error: {e}")
        return False, []

def parse_image_details(image_path):
    try:
        # ለፍጥነት ሲባል ምስሉን በስተጀርባ ማሳነስ (Optimize image for faster OCR)
        img = cv2.imread(image_path)
        height, width = img.shape[:2]
        if height > 1000 or width > 1000:
            img = cv2.resize(img, (800, int(800 * height / width)))
            cv2.imwrite(image_path, img)

        results = reader.readtext(image_path, detail=0)
        full_text = " ".join(results)
        
        amount_num = 2500.00
        amount_str = "2,500.00 ETB"
        sender = "በሊንኩ ያረጋግጡ"
        receiver = "ያልታወቀ"
        tx_id = "ያልታወቀ"
        
        # 1. የብር መጠን መፈለጊያ
        amt_match = re.search(r'(?:Debited|Amount|Total)[:\s]*([\d,]+\.\d{2})', full_text, re.IGNORECASE)
        if amt_match:
            clean_amt = amt_match.group(1).replace(',', '')
            amount_num = float(clean_amt)
            amount_str = f"{amt_match.group(1)} ETB"
        else:
            amt_match2 = re.search(r'([\d,]+\.\d{2})\s*ETB', full_text)
            if amt_match2:
                clean_amt = amt_match2.group(1).replace(',', '')
                amount_num = float(clean_amt)
                amount_str = f"{amt_match2.group(1)} ETB"

        # 2. የግብይት ቁጥር (Ref ID) መፈለጊያ
        id_match = re.search(r'(FT[A-Z0-9]{10,})', full_text)
        if id_match:
            tx_id = id_match.group(1)
            
        # 3. ላኪ መፈለጊያ
        sender_match = re.search(r'from\s+([A-Za-z\s\/]+)(?:ETB|for)', full_text, re.IGNORECASE)
        if sender_match:
            sender = sender_match.group(1).strip()
            
        # 4. የተቀባይ ስም መፈለጊያ (Amanuel Hiwet በ 'e' ፊደል ተስተካክሏል)
        if re.search(r'Tamrat\s+Amare', full_text, re.IGNORECASE):
            receiver = "Tamrat Amare"
        elif re.search(r'Amanuel\s+Hiw[oe]t', full_text, re.IGNORECASE):
            receiver = "Amanuel Hiwet"
        else:
            for word in results:
                w_low = word.lower()
                if "tamrat" in w_low or "amare" in w_low:
                    receiver = "Tamrat Amare"
                    break
                if "amanuel" in w_low or "hiw" in w_low:
                    receiver = "Amanuel Hiwet"
                    break
            
        return amount_num, amount_str, tx_id, sender, receiver
    except Exception as e:
        logging.error(f"OCR Error: {e}")
        return 2500.00, "2,500.00 ETB", "ያልታወቀ", "በሊንኩ ያረጋግጡ", "ያልታወቀ"

# =======================
# HANDLERS
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ሰላም! እባክዎ ለ Tamrat Amare ወይም Amanuel Hiwet የተላለፈበትን ትክክለኛ የባንክ ሪሲት ፎቶ ይላኩ።")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ፎቶዎን ተቀብያለሁ! መረጃውን (የተቀባይ ስም፣ የብር መጠንና ዕጣ) በፍጥነት እያረጋገጥኩ ነው...")
    
    photo_file = await update.message.photo[-1].get_file()
    photo_path = "user_screenshot.jpg"
    await update.message.photo[-1].get_file()
    await photo_file.download_to_drive(photo_path)
    
    try:
        # 1. መረጃዎችን ከፎቶው ላይ ማንበብ
        amount_num, amount_str, tx_id, sender, receiver = parse_image_details(photo_path)
        
        # 2. የQR ኮዱን ማንበብ
        img = cv2.imread(photo_path)
        detector = cv2.QRCodeDetector()
        qr_data, _, _ = detector.detectAndDecode(img)
        
        if qr_data and tx_id == "ያልታወቀ":
            url_match = re.search(r'v2-([A-Za-z0-9]+)', qr_data)
            if url_match:
                tx_id = url_match.group(1)[:12].upper()
            else:
                tx_id = qr_data[-15:]

        # 🛑 ጥብቅ ማጣሪያ፦ የተቀባይ ስም ማረጋገጫ (ወደ ሌላ ሰው ከተላከ የሚሰጠው ምላሽ)
        if receiver == "ያልታወቀ":
            await update.message.reply_text(
                "❌ **ይቅርታ፣ ይህ ሪሲት ተቀባይነት የለውም!**\n\n"
                "⚠️ ሪሲቱ ለ **Tamrat Amare** ወይም ለ **Amanuel Hiwet** የተላከ መሆኑን ቦቱ ማረጋገጥ አልቻለም።\n\n"
                "💡 **እባክዎ ትክክለኛ አካውንት ተጠቅማችሁ ወደ Tamrat Amare ወይም Amanuel Hiwet ያስገቡ።**"
            )
            return

        if tx_id == "ያልታወቀ":
            if qr_data:
                tx_id = qr_data[-15:]
            else:
                await update.message.reply_text("⚠️ ሪሲቱን ማስተናገድ አልተቻለም። እባክዎ የግብይት ቁጥሩ (Ref ID) በግልጽ የሚታይበት ትክክለኛ ፎቶ ይላኩ።")
                return

        # 3. በዳታቤዝ ውስጥ ማረጋገጥና የዕጣ ቁጥሮችን መስጠት
        is_new, tickets = check_and_save_tickets(tx_id, qr_data if qr_data else "No QR", amount_num)
        
        if is_new == "FULL":
            await update.message.reply_text("😔 ይቅርታ፣ ሁሉም የ3000 ዕጣ ቁጥሮች አልቀዋል።")
            return
            
        if is_new:
            status_msg = "✅ **አዲስ የግብይት ማረጋገጫ ተረጋግጧል!**"
            tickets_formatted = " \n ".join([f"🏆 `【 {t} 】` 🏆" for t in tickets])
            ticket_msg = (
                f"🎉 **እንኳን ደስ አለዎት! በከፈሉት ብር መጠን ልክ የተሰጡዎት {len(tickets)} የዕጣ ቁጥሮች፦**\n\n"
                f"{tickets_formatted}\n\n"
                f"*(እነዚህ ቁጥሮች በፍጹም አይደገምም፤ በጥንቃቄ ይያዙ)*"
            )
        else:
            status_msg = "❌ **ማስጠንቀቂያ፦ ድጋሚ የተላከ (የቆየ) መረጃ!**"
            tickets_formatted = " , ".join([f"`【 {t} 】`" for t in tickets])
            ticket_msg = f"⚠️ ይህ ሪሲት ቀደም ሲል ተመዝግቧል። የነበሩዎት የዕጣ ቁጥሮች፦ {tickets_formatted} ነበሩ።"
        
        link_str = f"[ሊንኩን ለመክፈት እዚህ ይጫኑ]({qr_data})" if qr_data else "የQR ኮድ የለም"
        
        detailed_response = (
            f"{status_msg}\n\n"
            f"📊 **የተገኘ የሪሲት ዝርዝር፦**\n"
            f"🔹 **Ref ID፦** `{tx_id}`\n"
            f"🔹 **የገንዘብ መጠን፦** `{amount_str}`\n"
            f"🔹 **ላኪ፦** `{sender}`\n"
            f"🔹 **ተቀባይ፦** `✅ {receiver}`\n"
            f"🔗 **የባንክ ማረጋገጫ፦** {link_str}\n\n"
            f"{ticket_msg}"
        )
        await update.message.reply_text(detailed_response, parse_mode="Markdown")
            
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
    
    print("ቦቱ በጥብቅ ስም ማጣሪያና በዕጣ ሲስተም ሥራ ጀምሯል...")
    await app.initialize()
    await app.updater.start_polling()
    await app.start()
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
