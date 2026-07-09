import os
import sqlite3
import logging
import asyncio
import re
import random
from datetime import datetime

import cv2
import numpy as np
from pyzbar.pyzbar import decode
from PIL import Image

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    MessageHandler, 
    CommandHandler, 
    ContextTypes, 
    CallbackQueryHandler, 
    filters
)

# =======================
# CONFIG
# =======================
TOKEN = os.getenv("BOT_TOKEN", "8611743019:AAGEHD_MZTciUYBVatUTcJC5uCw-OM5Ij3U")
ADMIN_ID = 5942828479  # ናይቲ ኣድሚን ID
MAX_TICKETS = 5000     # 🎯 ጠቅላላ የዕጣ ጣሪያ ወደ 5,000 ከፍ ብሏል

logging.basicConfig(level=logging.INFO)

# =======================
# DATABASE SETUP
# =======================
conn = sqlite3.connect("transactions.db", check_same_thread=False, timeout=30) # ⚡ እንዳይቆለፍ timeout ተጨምሯል
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT UNIQUE,
    qr_data TEXT,
    status TEXT,
    ticket_number TEXT,
    user_id TEXT,
    user_name TEXT,
    user_phone TEXT,
    created_at TEXT
)
""")
conn.commit()

# =======================
# HELPERS
# =======================
def generate_unique_tickets(count):
    """
    ከሉፕ ነፃ በሆነ መንገድ፣ በሴኮንድ ሩብ ውስጥ የቀሩትን ነፃ ቲኬቶች 
    ከ 1 እስከ 5000 ውስጥ መርጦ ያወጣል። (High Performance)
    """
    try:
        cursor.execute("SELECT ticket_number FROM transactions WHERE ticket_number IS NOT NULL")
        all_rows = cursor.fetchall()
        
        used_tickets = set()
        for row in all_rows:
            if row[0]:
                for num in row[0].split(","):
                    used_tickets.add(int(num.strip()))
        
        if len(used_tickets) + count > MAX_TICKETS:
            return []
            
        all_possible_tickets = set(range(1, MAX_TICKETS + 1))
        available_tickets = list(all_possible_tickets - used_tickets)
        
        # ሉፕ በሌለው መዋቅር በአንድ ጊዜ ነፃ ቁጥሮችን መውሰድ
        new_tickets = random.sample(available_tickets, count)
        return new_tickets
    except Exception as e:
        logging.error(f"Ticket error {e}")
        return []

def advanced_qr_reader(image_path):
    """
    በImo ወይም WhatsApp የተጨመቁ (Compress የሆኑ) ደካማ ፎቶዎችን 
    በ 3 የላቁ ማጣሪያዎች ፈልፍሎ የሚያነብ ኃይለኛ የQR አንባቢ።
    """
    # 1. መደበኛ ንባብ በ PyZbar መሞከር
    try:
        detected_qrs = decode(Image.open(image_path))
        if detected_qrs:
            return detected_qrs[0].data.decode('utf-8')
    except:
        pass

    # 2. ካልተነበበ ፎቶውን ወደ Black & White በመቀየር ማጥራት (OpenCV Thresholding)
    try:
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        detected_qrs = decode(thresh)
        if detected_qrs:
            return detected_qrs[0].data.decode('utf-8')
            
        # 3. በጥላ ወይም በብርሃን የተጋረደ ከሆነ ማስተካከል (Adaptive Thresholding)
        adaptive_thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        detected_qrs = decode(adaptive_thresh)
        if detected_qrs:
            return detected_qrs[0].data.decode('utf-8')
    except Exception as e:
        logging.error(f"Advanced QR processing error: {e}")
        
    return None

# =======================
# ADMIN COMMANDS (ትእዛዛት ኣድሚን)
# =======================
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        return
        
    cursor.execute("SELECT ticket_number FROM transactions WHERE ticket_number IS NOT NULL")
    all_rows = cursor.fetchall()
    
    total_sold = 0
    for row in all_rows:
        if row[0]:
            total_sold += len(row[0].split(","))
            
    total_remaining = MAX_TICKETS - total_sold
    
    status_msg = (
        f"📊 ሓፈሻዊ ኩነታት መሸጣ ዕጫ\n\n"
        f"🎟 ክሳብ ሕጂ ዝተሸጡ ዕጫታት `{total_sold}`\n"
        f"⏳ ዝተረፉ ዘይተሸጡ ዕጫታት `{total_remaining}`\n"
        f"📈 ጠቕላላ መጠን ዕጫታት `{MAX_TICKETS}`"
    )
    await update.message.reply_text(status_msg, parse_mode="Markdown")

async def search_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        return
        
    if not context.args:
        await update.message.reply_text("⚠️ በጃኹም ክትደልይዎ ዝደለኹም ቁፅሪ ዕጫ ኣተሓሒዝኩም ጸሓፉ። ንኣብነት /search 154")
        return
        
    search_num = context.args[0].strip()
    cursor.execute("SELECT user_name, user_phone, ticket_number, created_at, transaction_id FROM transactions")
    rows = cursor.fetchall()
    
    found = False
    for row in rows:
        tickets = [t.strip() for t in row[2].split(",")]
        if search_num in tickets:
            found = True
            await update.message.reply_text(
                f"🔍 ሓበሬታ ቁፅሪ ዕጫ ተረኺቡ ኣሎ\n\n"
                f"🎫 ቁፅሪ ዕጫ `【 {search_num} 】`\n"
                f"👤 ዋና (ስም) `{row[0]}`\n"
                f"📞 ቁፅሪ ስልኪ `{row[1]}`\n"
                f"🔢 ብሓባር ዝተወሃቡ ዕጫታት `{row[2]}`\n"
                f"📅 ዝተፈቐደሉ ዕለት {row[3]}\n"
                f"🔹 Ref ID `{row[4]}`",
                parse_mode="Markdown"
            )
            break
            
    if not found:
        await update.message.reply_text(f"❌ እቲ ቁፅሪ ዕጫ `{search_num}` ኣብ ዳታቤዝ ኣይተረኽበን።")

async def search_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        return
        
    if not context.args:
        await update.message.reply_text("⚠️ በጃኹም ክትደልይዎ ዝደለኹም ቁፅሪ ስልኪ ኣተሓሒዝኩም ጸሓፉ። ንኣብነት /user 0901268686")
        return
        
    search_phone = context.args[0].strip()
    cursor.execute("SELECT user_name, ticket_number, created_at FROM transactions WHERE user_phone = ?", (search_phone,))
    rows = cursor.fetchall()
    
    if rows:
        user_name_val = rows[0][0]
        msg = f"👤 ንቁፅሪ ስልኪ `{search_phone}` ዝተረኽቡ ሓበሬታታት\n\n"
        msg += f"👤 ስም ዓማዊል `{user_name_val}`\n\n"
        msg += "📋 ዝተወሃቡ ዕጫታት ዝርዝር\n"
        for i, row in enumerate(rows, 1):
            msg += f"{i}. 🎟 ቁፅሪታት `{row[1]}` (📅 {row[2]})\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ ብቁፅሪ ስልኪ `{search_phone}` ዝተመዝገበ ዓማዊል ኣይተረኽበን።")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        return
        
    if not context.args:
        await update.message.reply_text("⚠️ በጃኹም ንኹሎም ተጠቐምቲ ክሓልፍ ዝደለኹምዎ መልእኽቲ ኣተሓሒዝኩም ጸሓፉ።\nንኣብነት /broadcast ሰላም ኩላትኩም...")
        return
        
    broadcast_msg = update.message.text.split(None, 1)[1]
    cursor.execute("SELECT DISTINCT user_id FROM transactions WHERE user_id IS NOT NULL")
    users = cursor.fetchall()
    
    if not users:
        await update.message.reply_text("❌ ኣብ ዳታቤዝ ምንም ተጠቃሚ አልተገኘም።")
        return
        
    success_count = 0
    await update.message.reply_text(f"📢 ጽሑፍ መልእኽቲ ናብ {len(users)} ተጠቐምቲ ናይ ምልኣኽ ስራሕ ይጅመር ኣሎ...")
    
    for row in users:
        target_user = row[0]
        try:
            await context.bot.send_message(chat_id=int(target_user), text=broadcast_msg, parse_mode="Markdown")
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            continue
            
    await update.message.reply_text(f"✅ መልእኽቲ ብዓወት ተመሓላሊፉ ኣሎ።\n🎯 ዝበጽሖም ተጠቐምቲ ቁፅሪ {success_count}")

async def broadcast_photo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        return
        
    if not update.message.photo:
        await update.message.reply_text("⚠️ በጃኹም ፎቶ ምስ ጽሑፍ ኣተሓሒዝኩም ስደዱ። Caption ላይ /broadcast_photo ጽሑፍካ ኢልካ ጸሓፍ።")
        return
        
    caption_text = ""
    if update.message.caption:
        caption_parts = update.message.caption.split(None, 1)
        if len(caption_parts) > 1:
            caption_text = caption_parts[1]
            
    photo_file_id = update.message.photo[-1].file_id
    cursor.execute("SELECT DISTINCT user_id FROM transactions WHERE user_id IS NOT NULL")
    users = cursor.fetchall()
    
    if not users:
        await update.message.reply_text("❌ ኣብ ዳታቤዝ ምንም ተጠቃሚ አልተገኘም።")
        return
        
    success_count = 0
    await update.message.reply_text(f"📢 ፎቶ መልእኽቲ ናብ {len(users)} ተጠቐምቲ ናይ ምልኣኽ ስራሕ ይጅመር ኣሎ...")
    
    for row in users:
        target_user = row[0]
        try:
            await context.bot.send_photo(
                chat_id=int(target_user), 
                photo=photo_file_id, 
                caption=caption_text, 
                parse_mode="Markdown" if caption_text else None
            )
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            continue
            
    await update.message.reply_text(f"✅ ፎቶ መልእኽቲ ብዓወት ተመሓላሊፉ ኣሎ።\n🎯 ዝበጽሖም ተጠቐምቲ ቁፅሪ {success_count}")

# =======================
# USER HANDLERS (ንዓማዊል)
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [
        ['🏦 ሒሳብ ቁፅሪ ንምርካብ', '🧾 ደረሰኝ ንምልኣኽ'],
        ['🎟 ዕጫታት ዝርዝር', '🎫 ዕፃ ቁፅሪታተይ'],
        ['🎉 ተሸለምቲ 1ይ ዙር', '☎️ ብስልኪ ንምርካብ']
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "👋 ሰላም እንኳዕ ናብ ናይና online ዕፃ ብደሓን መጻእኩም\n\n"
        "👇 ካብቶም ታሕቲ ዘለዉ መማረጺታት ብምጥቃም ምሉእ ሓበሬታ ክትረኽቡን ናይ ክፍሊት ደረሰኝኩም ክትሰዱን ትኽእሉ ኢኹም።",
        reply_markup=markup
    )

async def handle_text_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.message.from_user.id
    
    # 1. አድሚኑ ቁጥር በእጁ የሚሞላበት ሁኔታ (Manual Ticket Allocation)
    admin_state = context.user_data.get(ADMIN_ID)
    if user_id == ADMIN_ID and admin_state and admin_state.get('step') == 'waiting_for_manual_ticket':
        if not text.isdigit() or not (1 <= int(text) <= MAX_TICKETS):
            await update.message.reply_text(f"⚠️ በጃኹም ካብ 1 ክሳብ {MAX_TICKETS} ዘሎ ትኽክለኛ ቁፅሪ ጥราይ የእትዉ።")
            return

        tx_id = admin_state['tx_id']
        target_user_id = admin_state['user_id']
        
        cursor.execute("SELECT ticket_number FROM transactions WHERE ticket_number IS NOT NULL")
        all_rows = cursor.fetchall()
        used_tickets = set()
        for row in all_rows:
            if row[0]:
                for num in row[0].split(","):
                    used_tickets.add(int(num.strip()))
                    
        if int(text) in used_tickets:
            await update.message.reply_text(f"❌ እቲ ቁፅሪ `{text}` ቅድሚ ሕጂ ተታሒዙ እዩ! በጃኹም ካልእ ቁፅሪ የእትዉ።")
            return
            
        cached = context.user_data.get(tx_id, {'qr': 'No Link', 'name': 'ዘይተፈልጠ', 'phone': 'ዘይተፈልጠ'})
        qr_data = cached.get('qr')
        u_name = cached.get('name')
        u_phone = cached.get('phone')
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            cursor.execute(
                "INSERT INTO transactions (transaction_id, qr_data, status, ticket_number, user_id, user_name, user_phone, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (tx_id, qr_data, "COMPLETED", text, target_user_id, u_name, u_phone, current_time)
            )
            conn.commit()
            
            await update.message.reply_text(f"✅ ቁፅሪ `{text}` ንተጠቃሚ `{u_name}` ብዓወት ተዋሂቡ ኣሎ።")
            
            user_msg = (
                f"✅ ናይ ክፍሊት መረጋገፂኹም ብዋናኡ ጸዲቑ ኣሎ\n\n"
                f"🎉 እንሆ ጽቡቕ ዜና! ብውሳነኹም መሰረት ዝተወሃበኩም ናይ ዕጫ ቁፅሪ፦\n\n"
                f"✨ ⟦ {text} ⟧ ✨\n\n"
                f"👋 ፅቡቅ ዕድል ይሃብኩም!"
            )
            await context.bot.send_message(chat_id=int(target_user_id), text=user_msg, parse_mode="Markdown")
            context.user_data.pop(ADMIN_ID, None)
        except sqlite3.IntegrityError:
            await update.message.reply_text("❌ እዚ ደረሰኝ እዚ ኣቐዲሙ ተመዝግቡ እዩ።")
        return

    # 2. የዋናው ማውጫ (Menu Buttons) ቼክ
    if text == '🏦 ሒሳብ ቁፅሪ ንምርካብ':
        context.user_data.pop(user_id, None)
        await update.message.reply_text(
            "🏦 ንግዲ ባንኪ ኢትዮጵያ (CBE)\n\n"
            "🔹 ቁፅሪ ኣካውንት `1000 77 0064 779`\n"
            "👤 ስም ኣካውንት Tamrat Amare / Amanuel Hiwet\n\n"
            "⚠️ መተሓሳሰቢ በጃኹም ኣብቲ ልክዕ ቁፅሪ ኣካውንት ምእታውኩም ኣረጋግጹ።"
        )
        return
        
    elif text == '🎟 ዕጫታት ዝርዝር':
        context.user_data.pop(user_id, None)
        await update.message.reply_text(
            "  ኣብ ቀደማይ ዙር ሒዝናዮም ዝመፃና ዕጫታት ዝርዝር\n\n"
            "🥇 1ይ ዕጫ BYD Seagull ዘመናዊት መኪና 🚙\n"
            "🥈 2ይ ዕጫ BYD Seagull ዘመናዊት መኪና 🚙\n"
            "🥉 3ይ ዕጫ BYD Seagull ዘመናዊት መኪና 🚙\n\n"
            "ዕድል ልልሞከረ እዩ 🙌! ይቁረፁ ይሸለሙ ።"
        )
        return
        
    elif text == '🎉 ተሸለምቲ 1ይ ዙር':
        context.user_data.pop(user_id, None)
        await update.message.reply_text(
            "📣 ዕላማ ተሸለምቲ 1ይ ዙር\n\n"
            "🔥 ቀደማይ ዙር ኣብ ቀረባ ግዘ ክወድቅ እዩ ! ዕድል ልልሞከረ እዩ ይቁረፁ ይተዓወቱ ።"
        )
        return
        
    elif text == '☎️ ብስልኪ ንምርካብ':
        context.user_data.pop(user_id, None)
        await update.message.reply_text(
            "📞 ብስልኪ ንምርካብ\n\n"
            "📱 `09 01 2686 86`\n\n"
            "💬 ዝኮነ ሕቶ ወይ ሓሳብ እንተሃልዩኩም ክትድውሉልና ትኽእሉ ኢኹም። ፅቡቅ ዕድል 🙏።"
        )
        return
        
    elif text == '🧾 ደረሰኝ ንምልኣኽ':
        context.user_data[user_id] = {'step': 'get_name'}
        await update.message.reply_text("👤 ደረሰኝቅድሚ ምልኣኽኩም በጃኹም መጀመርታ ምሉእ ስምኩም የእትዉ")
        return
        
    elif text == '🎫 ዕፃ ቁፅሪታተይ':
        context.user_data[user_id] = {'step': 'check_my_tickets'}
        await update.message.reply_text("📞 ዝተውሃቦም ዕፃ ቁፅሪ ንምፍላጥ ዝተመዝገብሉ ስልኪ የእትው ")
        return

    # 3. የሁኔታዎች (States) መቆጣጠሪያ - ስም፣ ስልክ እና ትኬት ፍለጋ
    state = context.user_data.get(user_id)
    if state:
        if state.get('step') == 'check_my_tickets':
            search_phone = text
            cursor.execute("SELECT ticket_number, created_at FROM transactions WHERE user_phone = ?", (search_phone,))
            rows = cursor.fetchall()
            
            if rows:
                msg = f"🎫 ንቁፅሪ ስልኪ `{search_phone}` ዝተውሃቦም ዕጫ ቁፅሪ ዝርዝር\n\n"
                all_tickets = []
                for row in rows:
                    if row[0]:
                        all_tickets.extend([t.strip() for t in row[0].split(",")])
                
                decorated_tickets = "  ".join([f"✨ ⟦ {tk} ⟧ ✨" for tk in all_tickets])
                msg += f"📊 ጠቅላላ ዝተውሃቦም ዕጫ ቁፅሪ `{len(all_tickets)}`\n\n"
                msg += f"📋 ቁፅሪታቶም\n{decorated_tickets}"
                await update.message.reply_text(msg, parse_mode="Markdown")
            else:
                await update.message.reply_text(f"❌ በስልክ ቁጥር `{search_phone}` የተመዘገበ ምንም የዕጣ ቁጥር አልተገኘም።\n⚠️ እባክዎ በትክክለኛው ስልክ ቁጥር እንደገና ይሞክሩ።")
            context.user_data.pop(user_id, None)
            return

        elif state.get('step') == 'get_name':
            context.user_data[user_id]['name'] = text
            context.user_data[user_id]['step'] = 'get_phone'
            await update.message.reply_text("📞 ቀፂልኩም ቁፅሪ ስልክኹም የእትዉ")
            return
            
        elif state.get('step') == 'get_phone':
            context.user_data[user_id]['phone'] = text
            context.user_data[user_id]['step'] = 'get_photo'
            await update.message.reply_text("🧾 ብትኽክል ተመዝጊቡ ኣሎ! ሕጂ ናይ ባንኪ ደረሰኝ ፎቶ (Screenshot) ብንፁር ስደዱልና")
            return

    # 4. Fallback (ከተገቢው ውጭ ሲጽፉ)
    reply_keyboard = [
        ['🏦 ሒሳብ ቁፅሪ ንምርካብ', '🧾 ደረሰኝ ንምልኣኽ'],
        ['🎟 ዕጫታት ዝርዝር', '🎫 ዕፃ ቁፅሪታተይ'],
        ['🎉 ተሸለምቲ 1ይ ዙር', '☎️ ብስልኪ ንምርካብ']
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "⚠️ **ጌጋ መልእኽቲ!**\n\n"
        "📱 በጃኹም ካብቶም ታሕቲ ዘለዉ ናይ **ማውጫ (Menu)** መማረጺታት ጥራይ ጠዊቕኩም ተጠቐሙ። ዝም ብልኩም ፅሑፍ ኣይእትዉ።",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# =======================
# 🚀 ኃይለኛው የፎቶ ማስተናገጃ (Handle Photo)
# =======================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state = context.user_data.get(user_id)
    
    if user_id == ADMIN_ID and update.message.caption and update.message.caption.startswith("/broadcast_photo"):
        await broadcast_photo_command(update, context)
        return

    if not state or state.get('step') != 'get_photo':
        await update.message.reply_text("⚠️ በጃኹም መጀመርታ ካብቲ ሜኑ '🧾 ደረሰኝ ንምልኣኽ' ዝብል ተጠዊቕኩም ስምኩምን ስልክኹምን የእትዉ።")
        return

    photo_file = update.message.photo[-1]
    # ⚡ Render ላይ በኔትወርክ እንዳይቆራረጥ የ 30 ሰከንድ Timeout ታክሏል
    file_info = await photo_file.get_file(read_timeout=30, write_timeout=30)
    photo_path = f"temp_{user_id}.jpg"
    await file_info.download_to_drive(photo_path)
    
    try:
        # 🌟 አዲሱን እና ኃይለኛውን የQR አንባቢ እዚህ ጋር እንጠራዋለን 🌟
        qr_data = advanced_qr_reader(photo_path)
        
        if not qr_data:
            await update.message.reply_text("⚠️ ኣብቲ ምስሊ ናይ QR ኮድ ክርከብ ኣይተኻእለን። በጃኹም እቲ QR ኮድ ብንፁር ዝረአ ምሉእ ፎቶ መሊስኩም ስደዱ።")
            return

        url_match = re.search(r'v2-([A-Za-z0-9]+)', qr_data)
        tx_id = url_match.group(1) if url_match else qr_data[-15:]
        
        cursor.execute("SELECT ticket_number FROM transactions WHERE transaction_id = ?", (tx_id,))
        result = cursor.fetchone()
        
        if result:
            tickets_formatted = " , ".join([f"✨ ⟦ {t.strip()} ⟧ ✨" for t in result[0].split(",")])
            await update.message.reply_text(
                f"❌ መጠንቀቕታ እዚ ደረሰኝ እዚ ቅድሚ ሕጂ ዝተመዝገበ እዩ\n\n"
                f"🏆 ዝነበረኩም ቁፅሪ ዕጫ {tickets_formatted} ነይሩ።"
            )
            context.user_data.pop(user_id, None)
            return

        u_name = state.get('name')
        u_phone = state.get('phone')
        context.user_data[tx_id] = {'qr': qr_data, 'name': u_name, 'phone': u_phone, 'photo_id': photo_file.file_id}

        keyboard = [
            [InlineKeyboardButton("🤖 ቦቱ ባዕሉ ይምረጸለይ (Auto)", callback_data=f"userchoice_auto_{tx_id}_{user_id}")],
            [InlineKeyboardButton("✍️ ኣነ ክምርፅ እደሊ (Manual)", callback_data=f"userchoice_manual_{tx_id}_{user_id}")]
        ]
        await update.message.reply_text(
            "⚡ ደረሰኝኹምን ሓበሬታኹምን ብሰላም በፂሑና ኣሎ!\n\n"
            "👇 በጃኹም ዕጫኹም ብኸመይ ክትመርፁ ከምእትደልዩ ምረጹ፦",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data.pop(user_id, None)
        
    except Exception as e:
        logging.error(f"Error {e}")
        await update.message.reply_text("❌ ነቲ ፎቶ ኣብ ምትእንጋድ ጌጋ አጋጢሙ።")
    finally:
        if os.path.exists(photo_path):
            os.remove(photo_path)

# =======================
# CALLBACK QUERY (አዝራሮች)
# =======================
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data.startswith("userchoice_"):
        _, method, tx_id, user_id = data.split("_")
        cached = context.user_data.get(tx_id)
        if not cached:
            await query.message.edit_text("❌ ሓበሬታ እዚ ደረሰኝ እዚ ጠፊኡ እዩ። በጃኹም ዳግማይ ፈትኑ።")
            return
            
        u_name = cached['name']
        u_phone = cached['phone']
        qr_data = cached['qr']
        photo_id = cached['photo_id']

        if method == "manual":
            await query.message.edit_text("✍️ 'ኣነ ክምርፅ እደሊ' መሪፅኩም ኣለኹም። ሕቶኹም ናብ ኣድሚን ተላኢኹ ኣሎ፤ በጃኹም ኣድሚን ቁፅሪ ክሳብ ዝህበኩም ተጸበዩ...")
            
            admin_keyboard = [
                [InlineKeyboardButton("✍️ ቁፅሪ ክመርፅ", callback_data=f"adminmanual_{tx_id}_{user_id}")],
                [InlineKeyboardButton("❌ ውድቅ ግበር", callback_data=f"rej_{tx_id}_{user_id}")]
            ]
            admin_caption = (
                f"🔔 ሓድሽ ናይ ደረሰኝ ሕቶ (ዓማዊል ባዕሉ ክመርጽ ደልዩ)\n\n"
                f"👤 ስም ዓማዊል `{u_name}`\n"
                f"📞 ቁፅሪ ስልኪ `{u_phone}`\n"
                f"🔹 Ref ID `{tx_id}`\n"
                f"🔗 [ሊንክ መረጋገፂ ባንኪ]({qr_data})\n\n"
                f"💡 በጃኹም ታሕቲ ዘሎ በተን ጠዊቕኩም ነጻ ቁፅሪ የእትዉሉ"
            )
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=admin_caption, reply_markup=InlineKeyboardMarkup(admin_keyboard), parse_mode="Markdown")
            
        elif method == "auto":
            await query.message.edit_text("🤖 'ቦቱ ባዕሉ ይምረጸለይ' መሪፅኩም ኣለኹም። ሕቶኹም ናብ ኣድሚን ተላኢኹ ኣሎ፤ መረጋገፂ ምስ ጸደቀ ዕጫኹም ክለኣኸልኩም እዩ።")
            
            admin_keyboard = [
                [
                    InlineKeyboardButton("🎟 1", callback_data=f"app_1_{tx_id}_{user_id}"),
                    InlineKeyboardButton("🎟 2", callback_data=f"app_2_{tx_id}_{user_id}"),
                    InlineKeyboardButton("🎟 3", callback_data=f"app_3_{tx_id}_{user_id}"),
                    InlineKeyboardButton("🎟 4", callback_data=f"app_4_{tx_id}_{user_id}"),
                    InlineKeyboardButton("🎟 5", callback_data=f"app_5_{tx_id}_{user_id}")
                ],
                [
                    InlineKeyboardButton("🎟 6", callback_data=f"app_6_{tx_id}_{user_id}"),
                    InlineKeyboardButton("🎟 7", callback_data=f"app_7_{tx_id}_{user_id}"),
                    InlineKeyboardButton("🎟 8", callback_data=f"app_8_{tx_id}_{user_id}"),
                    InlineKeyboardButton("🎟 9", callback_data=f"app_9_{tx_id}_{user_id}"),
                    InlineKeyboardButton("🎟 10", callback_data=f"app_10_{tx_id}_{user_id}")
                ],
                [InlineKeyboardButton("❌ ውድቅ ግበር", callback_data=f"rej_{tx_id}_{user_id}")]
            ]
            admin_caption = (
                f"🔔 ሓድሽ ናይ ደረሰኝ ሕቶ (ቦቱ ባዕሉ እንዲመርጥለት)\n\n"
                f"👤 ስም ዓማዊል `{u_name}`\n"
                f"📞 ቁፅሪ ስልኪ `{u_phone}`\n"
                f"🔹 Ref ID `{tx_id}`\n"
                f"🔗 [ሊንክ መረጋገፂ ባንኪ]({qr_data})\n\n"
                f"💡 በጃኹም መጠን ዕጫ በመምረጥ አጽድቁለት"
            )
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=admin_caption, reply_markup=InlineKeyboardMarkup(admin_keyboard), parse_mode="Markdown")
        return

    if data.startswith("adminmanual_"):
        _, tx_id, user_id = data.split("_")
        context.user_data[ADMIN_ID] = {'step': 'waiting_for_manual_ticket', 'tx_id': tx_id, 'user_id': user_id}
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"✍️ በጃኹም ነዚ ዓማዊል ክትህብዎ ዝደለኹምዎ ቁፅሪ (ካብ 1 - {MAX_TICKETS}) ጸሒፍኩም ስደዱ።")
        return

    if data.startswith("rej_"):
        _, tx_id, user_id = data.split("_")
        await query.message.edit_caption("❌ እዚ ደረሰኝ እዚ ብዋናኡ ውድቅ ተገይሩ ኣሎ።")
        try:
            await context.bot.send_message(
                chat_id=int(user_id), 
                text="❌ ይቕሬታ ዝለኣኽምዎ ደረሰኝ ውድቅ ተገይሩ ኣሎ。\n⚠️ በጃኹም ትኽክለኛ ደረሰኝ ምልኣኮም የረጋግፁ "
            )
        except:
            pass
        return

    if data.startswith("app_"):
        _, count_str, tx_id, user_id = data.split("_")
        count = int(count_str)
        
        cached = context.user_data.get(tx_id, {'qr': 'No Link', 'name': 'ዘይተፈልጠ', 'phone': 'ዘይተፈልጠ'})
        qr_data = cached.get('qr')
        u_name = cached.get('name')
        u_phone = cached.get('phone')
        
        tickets = generate_unique_tickets(count)
        if not tickets:
            await query.message.edit_caption(f"😔 ይቕሬታ እቶም {MAX_TICKETS} ቁፅሪታት ዕጫታት ተወዲኦም እዮም።")
            return
            
        tickets_str = ",".join(map(str, tickets))
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            cursor.execute(
                "INSERT INTO transactions (transaction_id, qr_data, status, ticket_number, user_id, user_name, user_phone, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (tx_id, qr_data, "COMPLETED", tickets_str, user_id, u_name, u_phone, current_time)
            )
            conn.commit()
            
            tickets_formatted = "  ".join([f"✨ ⟦ {t} ⟧ ✨" for t in tickets])
            
            await query.message.edit_caption(
                f"✅ ደረሰኝ ጸዲቑ ኣሎ\n"
                f"👤 ስም {u_name}\n"
                f"🔢 ዝተፈቐደ መጠን ዕጫ {count}\n"
                f"🎫 ዝተወሃቡ ቁፅሪታት `{tickets_str}`"
            )
            
            user_msg = (
                f"✅ ናይ ክፍሊት መረጋገፂኹም ብዋናኡ ጸዲቑ ኣሎ\n\n"
                f"🎉 እንሆ ጽቡቕ ዜና! ብውሳነ ዋና መሰረት ዝተወሃቡኹም {count} ቁፅሪታት ዕጫ\n\n"
                f"{tickets_formatted}\n\n"
                f"(እዞም ቁፅሪታት እዚኦም በፍፁም ኣይድገሙን፤ ብጥንቃቄ ሓዝዎም)"
            )
            await context.bot.send_message(chat_id=int(user_id), text=user_msg, parse_mode="Markdown")
            
        except sqlite3.IntegrityError:
            await query.message.edit_caption("❌ እዚ ደረሰኝ እዚ ኣቐዲሙ ተመዝግቡ እዩ።")

# =======================
# MAIN ASYNC FUNCTION
# =======================
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("search", search_ticket))
    app.add_handler(CommandHandler("user", search_user))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_buttons))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(admin_callback))
    
    print("ቦት በ Render ላይ ስራ ጀምሯል...")
    await app.initialize()
    await app.updater.start_polling()
    await app.start()
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
