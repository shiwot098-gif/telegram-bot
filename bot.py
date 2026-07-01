import os
import sqlite3
import logging
import asyncio
import re
import random
from datetime import datetime

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
    try:
        cursor.execute("SELECT ticket_number FROM transactions WHERE ticket_number IS NOT NULL")
        all_rows = cursor.fetchall()
        
        used_tickets = set()
        for row in all_rows:
            if row[0]:
                for num in row[0].split(","):
                    used_tickets.add(int(num.strip()))
        
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

# =======================
# ADMIN COMMANDS (ትእዛዛት ኣድሚን)
# =======================

# 📊 ኩነታት ዕጫታት መፈለጢ (ንኣድሚን ጥራይ)
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
            
    total_remaining = 3000 - total_sold
    
    status_msg = (
        f"📊 **ሓፈሻዊ ኩነታት መሸጣ ዕጫ**\n\n"
        f"🎟 **ክሳብ ሕጂ ዝተሸጡ ዕጫታት** `{total_sold}`\n"
        f"⏳ **ዝተረፉ ዘይተሸጡ ዕጫታት** `{total_remaining}`\n"
        f"📈 **ጠቕላላ መጠን ዕጫታት** `3000`"
    )
    await update.message.reply_text(status_msg, parse_mode="Markdown")

# 🔍 ብቑፅሪ ዕጫ መደለዪ (ንኣድሚን ጥራይ)
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
                f"🔍 **ሓበሬታ ቁፅሪ ዕጫ ተረኺቡ ኣሎ**\n\n"
                f"🎫 **ቁፅሪ ዕጫ** `【 {search_num} 】`\n"
                f"👤 **ዋና (ስም)** `{row[0]}`\n"
                f"📞 **ቁፅሪ ስልኪ** `{row[1]}`\n"
                f"🔢 ብሓባር ዝተወሃቡ ዕጫታት `{row[2]}`\n"
                f"📅 **ዝተፈቐደሉ ዕለት** {row[3]}\n"
                f"🔹 **Ref ID** `{row[4]}`",
                parse_mode="Markdown"
            )
            break
            
    if not found:
        await update.message.reply_text(f"❌ እቲ ቁፅሪ ዕጫ `{search_num}` ኣብ ዳታቤዝ ኣይተረኽበን።")

# 👤 ብቁፅሪ ስልኪ መደለዪ (ንኣድሚን ጥራይ)
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
        msg = f"👤 **ንቁፅሪ ስልኪ `{search_phone}` ዝተረኽቡ ሓበሬታታት**\n\n"
        msg += f"👤 **ስም ዓማዊል** `{user_name_val}`\n\n"
        msg += "📋 **ዝተወሃቡ ዕጫታት ዝርዝር**\n"
        for i, row in enumerate(rows, 1):
            msg += f"{i}. 🎟 ቁፅሪታት `{row[1]}` (📅 {row[2]})\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ ብቁፅሪ ስልኪ `{search_phone}` ዝተመዝገበ ዓማዊል ኣይተረኽበን።")

# =======================
# USER HANDLERS (ንዓማዊል)
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [
        ['🏦 ናይ ተቐባሊ ኣካውንት', '📸 ረሰይት ንምልኣኽ'],
        ['🎁 ሽልማቶች ዝርዝር', '📞 ብስልኪ ንምርካብ']
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "👋 **ሰላም! እንኳዕ ናብዚ ናይ ዕጫ መውጽኢ ቦት ብደሓን መጻእኩም።**\n\n"
        "👇 ካብቶም ታሕቲ ዘለዉ መማረጺታት ብምጥቃም ምሉእ ሓበሬታ ክትረኽቡን ናይ ክፍሊት ረሰይትኹም ክትሰዱን ትኽእሉ ኢኹም።",
        reply_markup=markup
    )

async def handle_text_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id
    
    if text == '🏦 ናይ ተቐባሊ ኣካውንት':
        context.user_data.pop(user_id, None)
        await update.message.reply_text(
            "🏦 **ንግዲ ባንኪ ኢትዮጵያ (CBE)**\n\n"
            "🔹 **ቁፅሪ ኣካውንት** `1000 77 0064 779`\n"
            "👤 **ስም ኣካውንት** Tamrat Amare / Amanuel Hiwet\n\n"
            "⚠️ *መተሓሳሰቢ በጃኹም ኣብቲ ልክዕ ቁፅሪ ኣካውንት ምእታውኩም ኣረጋግጹ።*"
        )
        return
        
    elif text == '🎁 ሽልማቶች ዝርዝር':
        context.user_data.pop(user_id, None)
        await update.message.reply_text(
            "🎁 **ክብረት ዝመልኦም ናይ ዕጫ ሽልማታት ዝርዝር**\n\n"
            "🥇 **1ይ ዕጫ** BYD Seagull ዘመናዊት መኪና 🚗\n"
            "🥈 **2ይ ዕጫ** BYD Seagull ዘመናዊት መኪና 🚗\n"
            "🥉 **3ይ ዕጫ** BYD Seagull ዘመናዊት መኪና 🚗\n\n"
            "🎉 *ፈጣሪ ጽቡቕ ዕድል ይሃብኩም! ንነፍሲ ወከፍ ዝገበርኩምዎ ክፍሊት ዝያዳ ዕጫታት ብምውሳድ ዕድልኩም ኣስፉሑ።*"
        )
        return
        
    elif text == '📞 ብስልኪ ንምርካብ':
        context.user_data.pop(user_id, None)
        await update.message.reply_text(
            "📞 **ብስልኪ ንምርካብ**\n\n"
            "📱 `09 01 2686 86`\n\n"
            "💬 ዝኮነ ሕቶ ወይ ሓሳብ እንተሃልዩኩም ክትድውሉልና ትኽእሉ ኢኹም። ንሕና ኩሉ ግዜ ንዓኹም ንምሕጋዝ ድሉዋት ኢና።"
        )
        return
        
    elif text == '📸 ረሰይት ንምልኣኽ':
        context.user_data[user_id] = {'step': 'get_name'}
        await update.message.reply_text("👤 **ረሰይት ቅድሚ ምልኣኽኩም በጃኹም መጀመርታ ምሉእ ስምኩም የእትዉ**")
        return

    state = context.user_data.get(user_id)
    if state:
        if state.get('step') == 'get_name':
            context.user_data[user_id]['name'] = text
            context.user_data[user_id]['step'] = 'get_phone'
            await update.message.reply_text("📞 **ቀፂልኩም ቁፅሪ ስልክኹም የእትዉ**")
            
        elif state and state.get('step') == 'get_phone':
            context.user_data[user_id]['phone'] = text
            context.user_data[user_id]['step'] = 'get_photo'
            await update.message.reply_text("📸 **ብትኽክል ተመዝጊቡ ኣሎ! ሕጂ ናይ ባንኪ ረሰይት ፎቶ (Screenshot) ብንፁር ስደዱልና**")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state = context.user_data.get(user_id)
    
    if not state or state.get('step') != 'get_photo':
        await update.message.reply_text("⚠️ በጃኹም መጀመርታ ካብቲ ሜኑ **'📸 ረሰይት ንምልኣኽ'** ዝብል ተጠዊቕኩም ስምኩምን ስልክኹምን የእትዉ።")
        return
        
    import cv2
    photo_file = update.message.photo[-1]
    file_info = await photo_file.get_file()
    photo_path = f"temp_{user_id}.jpg"
    await file_info.download_to_drive(photo_path)
    
    try:
        img = cv2.imread(photo_path)
        detector = cv2.QRCodeDetector()
        qr_data, _, _ = detector.detectAndDecode(img)
        
        if not qr_data:
            await update.message.reply_text("⚠️ ኣብቲ ምስሊ ናይ QR ኮድ ክርከብ ኣይተኻእለን። በጃኹም እቲ QR ኮድ ብንፁር ዝረአ ምሉእ ፎቶ መሊስኩም ስደዱ።")
            return

        url_match = re.search(r'v2-([A-Za-z0-9]+)', qr_data)
        tx_id = url_match.group(1) if url_match else qr_data[-15:]
        
        cursor.execute("SELECT ticket_number FROM transactions WHERE transaction_id = ?", (tx_id,))
        result = cursor.fetchone()
        
        if result:
            tickets_formatted = " , ".join([f"`【 {t.strip()} 】`" for t in result[0].split(",")])
            await update.message.reply_text(
                f"❌ **መጠንቀቕታ እዚ ረሰይት እዚ ቅድሚ ሕጂ ዝተመዝገበ እዩ**\n\n"
                f"🏆 ዝነበረኩም ቁፅሪ ዕጫ፦ {tickets_formatted} ነይሩ።"
            )
            context.user_data.pop(user_id, None)
            return

        await update.message.reply_text("⚡ ረሰይትኹምን ሓበሬታኹምን ብሰላም በፂሑና ኣሎ! ብዋናኡ ይረጋገፅ ስለዘሎ በጃኹም ሒደት ደቒቕ ተጸበዩ...")
        
        u_name = state.get('name')
        u_phone = state.get('phone')
        
        keyboard = [
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
            [
                InlineKeyboardButton("❌ ውድቅ ግበር", callback_data=f"rej_{tx_id}_{user_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        context.user_data[tx_id] = {'qr': qr_data, 'name': u_name, 'phone': u_phone}
        
        admin_caption = (
            f"🔔 **ሓድሽ ናይ ረሰይት ሕቶ መፂኡ ኣሎ**\n\n"
            f"👤 **ስም ዓማዊል** `{u_name}`\n"
            f"📞 **ቁፅሪ ስልኪ** `{u_phone}`\n"
            f"🔹 **Ref ID** `{tx_id}`\n"
            f"🔗 [ሊንክ መረጋገፂ ባንኪ]({qr_data})\n\n"
            f"💡 *በጃኹም ረሰይት ርኢኹም ካብቶም ታሕቲ ዘለዉ ቁፅሪታት ክንደይ ዕጫ ክወሃቦ ከምዘለዎ ይጫኑ*"
        )
        
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo_file.file_id,
            caption=admin_caption,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        context.user_data.pop(user_id, None)
        
    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("❌ ነቲ ፎቶ ኣብ ምትእንጋድ ጌጋ አጋጢሙ።")
    finally:
        if os.path.exists(photo_path):
            os.remove(photo_path)

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("rej_"):
        _, tx_id, user_id = data.split("_")
        await query.message.edit_caption("❌ እዚ ረሰይት እዚ ብዋናኡ ውድቅ ተገይሩ ኣሎ።")
        try:
            await context.bot.send_message(
                chat_id=int(user_id), 
                text="❌ **ይቕሬታ ዝለኣኽምዎ ረሰይት ብዋናኡ ውድቅ ተገይሩ ኣሎ።**\n⚠️ በጃኹም ትኽክለኛ ረሰይት ምልኣኽኩም ኣረጋግጹ።"
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
            await query.message.edit_caption("😔 ይቕሬታ እቶም 3000 ቁፅሪታት ዕጫታት ተወዲኦም እዮም።")
            return
            
        tickets_str = ",".join(map(str, tickets))
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            cursor.execute(
                "INSERT INTO transactions (transaction_id, qr_data, status, ticket_number, user_id, user_name, user_phone, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (tx_id, qr_data, "COMPLETED", tickets_str, user_id, u_name, u_phone, current_time)
            )
            conn.commit()
            
            tickets_formatted = " \n ".join([f"🏆 `【 {t} 】` 🏆" for t in tickets])
            
            await query.message.edit_caption(
                f"✅ **ረሰይት ጸዲቑ ኣሎ**\n"
                f"👤 ስም {u_name}\n"
                f"🔢 ዝተፈቐደ መጠን ዕጫ {count}\n"
                f"🎫 ዝተወሃቡ ቁፅሪታት `{tickets_str}`"
            )
            
            user_msg = (
                f"✅ **ናይ ክፍሊት መረጋገፂኹም ብዋናኡ ጸዲቑ ኣሎ**\n\n"
                f"🎉 **እንኳዕ ደስ በለኩም! ብውሳነ ዋና መሰረት ዝተወሃቡኹም {count} ቁፅሪታት ዕጫ፦**\n\n"
                f"{tickets_formatted}\n\n"
                f"*(እዞም ቁፅሪታት እዚኦም በፍፁም ኣይድገሙን፤ ብጥንቃቄ ሓዝዎም)*"
            )
            await context.bot.send_message(chat_id=int(user_id), text=user_msg, parse_mode="Markdown")
            
        except sqlite3.IntegrityError:
            await query.message.edit_caption("❌ እዚ ረሰይት እዚ ኣቐዲሙ ተመዝግቡ እዩ።")

# =======================
# MAIN ASYNC FUNCTION
# =======================
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("search", search_ticket))
    app.add_handler(CommandHandler("user", search_user))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_buttons))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(admin_callback))
    
    print("ቦት ብጽሩይ ትግርኛ ስርሑ ጀሚሩ ኣሎ...")
    await app.initialize()
    await app.updater.start_polling()
    await app.start()
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
