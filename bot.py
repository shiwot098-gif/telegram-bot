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
ADMIN_ID = 5942828479  # የእርስዎ ID

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
# ADMIN COMMANDS
# =======================

# 📊 አዲስ፦ ስንት ዕጣ እንደተሸጠ እና እንደቀረ ማሳያ (ለአድሚን ብቻ)
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        return  # አድሚን ካልሆነ ምንም አይመልስም
        
    cursor.execute("SELECT ticket_number FROM transactions WHERE ticket_number IS NOT NULL")
    all_rows = cursor.fetchall()
    
    total_sold = 0
    for row in all_rows:
        if row[0]:
            total_sold += len(row[0].split(","))
            
    total_remaining = 3000 - total_sold
    
    status_msg = (
        f"📊 **የዕጣ ሽያጭ አጠቃላይ መረጃ፦**\n\n"
        f"🎟 **እስካሁን የተሸጡ ዕጣዎች፦** `{total_sold}`\n"
        f"⏳ **የቀሩ (ያልተሸጡ) ዕጣዎች፦** `{total_remaining}`\n"
        f"📈 **ጠቅላላ የዕጣ መጠን፦** `3000`"
    )
    await update.message.reply_text(status_msg, parse_mode="Markdown")

# 🔍 አዲስ፦ በትኬት ቁጥር መፈለጊያ ትዕዛዝ (ለአድሚን ብቻ)
async def search_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        return  # አድሚን ካልሆነ ምንም አይመልስም
        
    if not context.args:
        await update.message.reply_text("⚠️ እባክዎ የሚፈልጉትን የዕጣ ቁጥር አብረው ያስገቡ። ለምሳሌ፦ `/search 154`")
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
                f"🔍 **የዕጣ ቁጥር መረጃ ተገኝቷል፦**\n\n"
                f"🎫 **የዕጣ ቁጥር፦** `【 {search_num} 】`\n"
                f"👤 **ባለቤት (ስም)፦** `{row[0]}`\n"
                f"📞 **ስልክ ቁጥር፦** `{row[1]}`\n"
                f"🔢 አብረው የተሰጡ ዕጣዎች፦ `{row[2]}`\n"
                f"📅 **የተፈቀደበት ቀን፦** {row[3]}\n"
                f"🔹 **Ref ID፦** `{row[4]}`",
                parse_mode="Markdown"
            )
            break
            
    if not found:
        await update.message.reply_text(f"❌ የዕጣ ቁጥር `{search_num}` ዳታቤዝ ውስጥ አልተገኘም።")

# 👤 አዲስ፦ በስልክ ቁጥር መፈለጊያ ትዕዛዝ (ለአድሚን ብቻ)
async def search_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        return
        
    if not context.args:
        await update.message.reply_text("⚠️ እባክዎ የሚፈልጉትን ስልክ ቁጥር አብረው ያስገቡ። ለምሳሌ፦ `/user 0901268686`")
        return
        
    search_phone = context.args[0].strip()
    
    cursor.execute("SELECT user_name, ticket_number, created_at FROM transactions WHERE user_phone = ?", (search_phone,))
    rows = cursor.fetchall()
    
    if rows:
        msg = f"👤 **ለስልክ ቁጥር `{search_phone}` የተገኙ መረጃዎች፦**\n\n"
        msg += f"👤 **የደንበኛ ስም፦** `{rows[0][0]}`\n\n"
        msg += "📋 **የተሰጡ ዕጣዎች ዝርዝር፦**\n"
        for i, row in enumerate(rows, 1):
            msg += f"{i}. 🎟 ቁጥሮች፦ `{row[1]}` (📅 {row[2]})\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ በስልክ ቁጥር `{search_phone}` የተመዘገበ ምንም ደንበኛ አልተገኘም።")

# =======================
# USER HANDLERS
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [
        ['🏦 ሒሳብ ቁፅሪ ንምርካብ', '🧾 ደረሰኝ ንምልኣክ'],
        ['🎁 ዕፃታት', '☎️ ስልኪ ']
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "👋 ሰላም! እንኳዕ ብደሓን መፃኩም ! ኣብ ታሕቲ ብለሎ መማረፅታት ብምጥቃም ኣገልግሎት ትረክቡ ትክእሉ ።",
        reply_markup=markup
    )

async def handle_text_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id
    
    if text == '🏦 ሒሳብ ቁፅሪ ንምርካብ':
        context.user_data.pop(user_id, None)
        await update.message.reply_text(
            "🏦 የኢትዮጵያ ንግድ ባንክ (CBE)**\n\n"
            "🔹 ሒሳብ ቁፅሪ፦`1000 77 0064 779`\n"
            "👤 ስም፦ Tamrat Amare / Amanuel Hiwet\n\n"
            "⚠️ መተሓሳሰቢ፦ በይዘኦም ንብ ትክክለኛ ሒሳብ ከምዘእተኩም አረጋግፁ።"
        )
        return
        
    elif text == '🎁 ዕፃታት':
        context.user_data.pop(user_id, None)
        await update.message.reply_text(
            "🎁 ናይ ዕፃታት ዝርዝር፦**\n\n"
            "🥇 1ይ ዕፃ ፦ BYD Seagull መኪና\n"
            "🥈 2ኛ ዕፃ ፦ BYD Seagull መኪና\n"
            "🥉 3ኛ ዕፃ ፦ BYD Seagull መኪና\n\n"
            "🎉 ፅቡቅ ዕድል ! ዕድል ልልሞከረ እዩ ይቁረፁ ይሸለሙ።"
        )
        return
        
    elif text == '☎️ ስልኪ':
        context.user_data.pop(user_id, None)
        await update.message.reply_text(
            "☎️ ብስልኪ ንምርካብ ፦**\n\n"
            "📲 `09 01 2686 86 `\n\n"
            "💬 ልኮነ ዓይነት ጥያቄ ወይ ኣስተያየት ንምሃብ ይደዉሉ።"
        )
        return
        
    elif text == '🧾 ደረሰኝ ንምልኣክ':
        context.user_data[user_id] = {'step': 'get_name'}
        await update.message.reply_text("👤 ንምምዝጋብ ስም ይልኣኩ ፦**")
        return

    state = context.user_data.get(user_id)
    if state:
        if state.get('step') == 'get_name':
            context.user_data[user_id]['name'] = text
            context.user_data[user_id]['step'] = 'get_phone'
            await update.message.reply_text("📞 ብምቅፃል ስልኪ ቁፅሪ ይልኣኩ ፦**")
            
        elif state and state.get('step') == 'get_phone':
            context.user_data[user_id]['phone'] = text
            context.user_data[user_id]['step'] = 'get_photo'
            await update.message.reply_text("📸 **በአሪፉ ተመዝግቧል! አሁን የባንክ ሪሲቱን ፎቶ (Screenshot) ይላኩ፦**")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state = context.user_data.get(user_id)
    
    if not state or state.get('step') != 'get_photo':
        await update.message.reply_text("⚠️ በይዘኦም አብቲ መማረፂ ዘሎ '🧾 ደረሰኝ ንምልኣክ'*ዝብል ብምጥቃም ስም ስልኪ እና ደረሰኝ ይልኣኩ።")
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
            await update.message.reply_text("⚠️ ኣብዚ ፎቶ QR ኮድ ክርከብ ኣይከኣለይ። በይዛኩም QR ኮድ ብግልፂ ዘርኢ ፎቶ ደጊሞም ይልኣኩ።")
            return

        url_match = re.search(r'v2-([A-Za-z0-9]+)', qr_data)
        tx_id = url_match.group(1) if url_match else qr_data[-15:]
        
        cursor.execute("SELECT ticket_number FROM transactions WHERE transaction_id = ?", (tx_id,))
        result = cursor.fetchone()
        
        if result:
            tickets_formatted = " , ".join([f"`【 {t.strip()} 】`" for t in result[0].split(",")])
            await update.message.reply_text(
                f"❌ መጠንቀቅታ ፦ እዚ ደረሰኝ ቀዲሙ ተመዝጊቡ ኔሩ እዩ!**\n\n"
                f"👉 ዝነበረ ዕፃ ቁፅሪ፦ {tickets_formatted} እዩ።"
    )
            context.user_data.pop(user_id, None)
            return

        await update.message.reply_text("⚡ ደረሰኝ ተቀቢለ አለኩ! እናተረጋገፀ ስለ ዝኮነ ድሕሪ ዝተወሰነ ግዜ ዕፃ ክበፅሖም እዩ...")
        
        u_name = state.get('name')
        u_phone = state.get('phone')
        
        keyboard = [
            [
                InlineKeyboardButton("👍 1", callback_data=f"app_1_{tx_id}_{user_id}"),
                InlineKeyboardButton("👍 2", callback_data=f"app_2_{tx_id}_{user_id}"),
                InlineKeyboardButton("👍 3", callback_data=f"app_3_{tx_id}_{user_id}"),
                InlineKeyboardButton("👍 4", callback_data=f"app_4_{tx_id}_{user_id}"),
                InlineKeyboardButton("👍 5", callback_data=f"app_5_{tx_id}_{user_id}")
            ],
            [
                InlineKeyboardButton("👍 6", callback_data=f"app_6_{tx_id}_{user_id}"),
                InlineKeyboardButton("👍 7", callback_data=f"app_7_{tx_id}_{user_id}"),
                InlineKeyboardButton("👍 8", callback_data=f"app_8_{tx_id}_{user_id}"),
                InlineKeyboardButton("👍 9", callback_data=f"app_9_{tx_id}_{user_id}"),
                InlineKeyboardButton("👍 10", callback_data=f"app_10_{tx_id}_{user_id}")
            ],
            [
                InlineKeyboardButton("❌ ትክክል ኣይኮነን", callback_data=f"rej_{tx_id}_{user_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        context.user_data[tx_id] = {'qr': qr_data, 'name': u_name, 'phone': u_phone}
        
        admin_caption = (
            f"🔔 ሓዱሽ ጥያቄ መፂኡ!**\n\n"
            f"👤 ናደንበኛ ስም ፦ `{u_name}`\n"
            f"📞 ስልኪ ቁፅሪ ፦ `{u_phone}`\n"
            f"🔹 Ref ID ፦ `{tx_id}`\n"
            f"🔗 [የባንክ ማረጋገጫ ሊንክ]({qr_data})\n\n"
            f"💡 *ክንደይ ትኬት ክህቦ፦*"
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
        await update.message.reply_text("❌ ፎቶውን በማስተናገድ ላይ ስህተት አጋጥሟል።")
    finally:
        if os.path.exists(photo_path):
            os.remove(photo_path)

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("rej_"):
        _, tx_id, user_id = data.split("_")
        await query.message.edit_caption("❌ ደረሰኝ ውድ ተገይሩ ኣሎ።")
        try:
            await context.bot.send_message(
                chat_id=int(user_id), 
                text="❌ ይቅርታ ዝለኣክዎ ደረሰኝ ውድቅ ተገይሩ ኣሎ።**\n⚠️ በይዘኦም ትክክለኛ ደረሰኝ ደጊሞም ንምእታው ይሞክሩ"
            )
        except:
            pass
        return

    if data.startswith("app_"):
        _, count_str, tx_id, user_id = data.split("_")
        count = int(count_str)
        
        cached = context.user_data.get(tx_id, {'qr': 'No Link', 'name': 'ያልታወቀ', 'phone': 'ያልታወቀ'})
        qr_data = cached.get('qr')
        u_name = cached.get('name')
        u_phone = cached.get('phone')
        
        tickets = generate_unique_tickets(count)
        if not tickets:
            await query.message.edit_caption("😔 ይቅርታ፣ የ3000 ዕጣ ቁጥሮች አልቀዋል።")
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
                f"✅ ደረሰኝ ፀዲቁ ኣሎ!**\n"
                f"👤 ስም፦ {u_name}\n"
                f"🔢 ዝተፈቀደ በዝሒ ዕፃ ፦ {count}\n"
                f"🎫 ዝተውሃቡ ዕፃታት ፦ `{tickets_str}`"
            )
            
            user_msg = (
                f"✅ ደረሰኞም ፀዲቁ ኣሎ!**\n\n"
                f"🎉 እንኳዕ ደስ በለኩም! ዝተውሃብዎም በዝሒ ዕፃ {count} ዕፃ ቁፅሪ እዩ ፦**\n\n"
                f"{tickets_formatted}\n\n"
                f"*( ዕፃ ቁፅሪ ከይጠፍእ ከይርሳዕ )*"
            )
            await context.bot.send_message(chat_id=int(user_id), text=user_msg, parse_mode="Markdown")
            
        except sqlite3.IntegrityError:
            await query.message.edit_caption("❌ እዚ ደረሰኝ ኣቀዲሙ ተመዝጊቡ ዝነበረ እዩ ።")

# =======================
# MAIN ASYNC FUNCTION
# =======================
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    # ለአድሚን ብቻ የሚሠሩ ትዕዛዞች
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("search", search_ticket))
    app.add_handler(CommandHandler("user", search_user))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_buttons))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(admin_callback))
    
    print("እዚ ቦት ሙሉእ ንሙሉእ ስራሕ ጀሚሩ ኣሎ...")
    await app.initialize()
    await app.updater.start_polling()
    await app.start()
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
