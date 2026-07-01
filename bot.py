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
ADMIN_ID = 5942828479  # ያቀረቡት የእርስዎ ID

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
# HANDLERS
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # የታችኛው ሜኑ አዝራሮች (Keyboard Buttons)
    reply_keyboard = [
        ['🏦 የተቀባይ አካውንት', '📸 ሪሲት ለመላክ'],
        ['🎁 ሽልማቶች', '📞 በስልክ ለማግኘት']
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "👋 ሰላም! እንኳን ወደ ዕጣ ማውጫ ቦት በደህና መጡ። ከታች ያሉትን አማራጮች በመጠቀም መረጃ ማግኘትና ሪሲት መላክ ይችላሉ።",
        reply_markup=markup
    )

async def handle_text_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id
    
    if text == '🏦 የተቀባይ አካውንት':
        await update.message.reply_text(
            "🏦 **የኢትዮጵያ ንግድ ባንክ (CBE)**\n\n"
            "🔹 **የአካውንት ቁጥር፦** `1000 77 0064 779`\n"
            "👤 **የአካውንት ስም፦** Tamrat Amare / Amanuel Hiwet\n\n"
            "⚠️ *ማሳሰቢያ፦ እባክዎ በትክክለኛው አካውንት ላይ ማስገባትዎን ያረጋግጡ።*"
        )
        
    elif text == '🎁 ሽልማቶች':
        await update.message.reply_text(
            "🎁 **የዕጣ ሽልማቶች ዝርዝር፦**\n\n"
            "🥇 **1ኛ ዕጣ፦** BYD Seagull መኪና\n"
            "🥈 **2ኛ ዕጣ፦** BYD Seagull መኪና\n"
            "🥉 **3ኛ ዕጣ፦** BYD Seagull መኪና\n\n"
            "🎉 *መልካም ዕድል! ለየእያንዳንዱ ግብይትዎ ዕጣዎችን ያግኙ።*"
        )
        
    elif text == '📞 በስልክ ለማግኘት':
        await update.message.reply_text(
            "📞 **በስልክ ለማግኘት፦**\n\n"
            "📱 `09 01 2686 86`\n\n"
            "💬 ማንኛውም ጥያቄ ካለዎት መደወል ይችላሉ።"
        )
        
    elif text == '📸 ሪሲት ለመላክ':
        context.user_data[user_id] = {'step': 'get_name'}
        await update.message.reply_text("👤 **ሪሲት ለመላክ መጀመሪያ ሙሉ ስምዎን ያስገቡ፦**")
        
    else:
        # የባለብዙ ደረጃ (Form) አሞላል ሂደት
        state = context.user_data.get(user_id)
        if state and state.get('step') == 'get_name':
            context.user_data[user_id]['name'] = text
            context.user_data[user_id]['step'] = 'get_phone'
            await update.message.reply_text("📞 **በመቀጠል ስልክ ቁጥርዎን ያስገቡ፦**")
            
        elif state and state.get('step') == 'get_phone':
            context.user_data[user_id]['phone'] = text
            context.user_data[user_id]['step'] = 'get_photo'
            await update.message.reply_text("📸 **በጣም ጥሩ! አሁን የባንክ ሪሲቱን ፎቶ (Screenshot) ይላኩ፦**")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state = context.user_data.get(user_id)
    
    # መጀመሪያ ስምና ስልክ ማስገባታቸውን ማረጋገጥ
    if not state or state.get('step') != 'get_photo':
        await update.message.reply_text("⚠️ እባክዎ መጀመሪያ ሜኑ ላይ ያለውን **'📸 ሪሲት ለመላክ'** የሚለውን ቁልፍ ተጭነው ስምና ስልክዎን ያስገቡ።")
        return
        
    import cv2
    photo_file = update.message.photo[-1]
    file_info = await photo_file.get_file()
    photo_path = f"temp_{user_id}.jpg"
    await file_info.download_to_drive(photo_path)
    
    try:
        # 1. የQR ኮዱን ማንበብ
        img = cv2.imread(photo_path)
        detector = cv2.QRCodeDetector()
        qr_data, _, _ = detector.detectAndDecode(img)
        
        if not qr_data:
            await update.message.reply_text("⚠️ በምስሉ ላይ የQR ኮድ ማግኘት አልተቻለም። እባክዎ የQR ኮዱ በግልጽ የሚታይበት ሙሉ ፎቶ መልሰው ይላኩ።")
            return

        url_match = re.search(r'v2-([A-Za-z0-9]+)', qr_data)
        tx_id = url_match.group(1) if url_match else qr_data[-15:]
        
        # 2. የተደገመ መሆኑን ማረጋገጥ
        cursor.execute("SELECT ticket_number FROM transactions WHERE transaction_id = ?", (tx_id,))
        result = cursor.fetchone()
        
        if result:
            # 🔄 የተደገመ ከሆነ ለላኪው የነበረውን ዕጣ መናገር
            tickets_formatted = " , ".join([f"`【 {t.strip()} 】`" for t in result[0].split(",")])
            await update.message.reply_text(
                f"❌ **ማስጠንቀቂያ፦ ይህ ሪሲት ከዚህ በፊት ተመዝግቧል!**\n\n"
                f"🏆 የነበረዎት የዕጣ ቁጥር፦ {tickets_formatted} ነበር።"
            )
            # ሁኔታውን ማጽዳት
            context.user_data.pop(user_id, None)
            return

        # 3. አዲስ ከሆነ መረጃውን ወደ እርስዎ (Admin) መላክ
        await update.message.reply_text("⚡ ሪሲትዎ እና መረጃዎ ደርሶኛል! በባለቤቱ እየተረጋገጠ ስለሆነ ጥቂት ደቂቃዎችን ይጠብቁ...")
        
        u_name = state.get('name')
        u_phone = state.get('phone')
        
        # የአስተዳዳሪ ውሳኔ ቁልፎች
        keyboard = [
            [
                InlineKeyboardButton("🎟 1 ዕጣ ስጥ", callback_data=f"app_1_{tx_id}_{user_id}"),
                InlineKeyboardButton("🎟 2 ዕጣ ስጥ", callback_data=f"app_2_{tx_id}_{user_id}")
            ],
            [
                InlineKeyboardButton("🎟 3 ዕጣ ስጥ", callback_data=f"app_3_{tx_id}_{user_id}"),
                InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"rej_{tx_id}_{user_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # በጊዚያዊነት የQR እና የደንበኛ መረጃዎችን መያዝ
        context.user_data[tx_id] = {'qr': qr_data, 'name': u_name, 'phone': u_phone}
        
        admin_caption = (
            f"🔔 **አዲስ የሪሲት ጥያቄ መጥቷል!**\n\n"
            f"👤 **የደንበኛ ስም፦** `{u_name}`\n"
            f"📞 **ስልክ ቁጥር፦** `{u_phone}`\n"
            f"🔹 **Ref ID፦** `{tx_id}`\n"
            f"🔗 [የባንክ ማረጋገጫ ሊንክ]({qr_data})\n\n"
            f"💡 *እባክዎ ሪሲቱን አይተው ከታች ካሉት አማራጮች ስንት ዕጣ እንደሚገባው ይፍቀዱለት፦*"
        )
        
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo_file.file_id,
            caption=admin_caption,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        # የተጠቃሚውን የደረጃ ሁኔታ ማጽዳት
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
        await query.message.edit_caption("❌ ይህ ሪሲት በርስዎ ውድቅ ተደርጓል።")
        try:
            await context.bot.send_message(
                chat_id=int(user_id), 
                text="❌ **ይቅርታ፣ የላኩት ሪሲት በባለቤቱ ውድቅ ተደርጓል።**\n⚠️ እባክዎ ትክክለኛ ሪሲት መላክዎን ያረጋግጡ።"
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
        
        # የዕጣ ቁጥሮችን በዘፈቀደ (Randomly) መፍጠር
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
            
            # ለአንተ (Admin) የሚታይ
            await query.message.edit_caption(
                f"✅ **ሪሲቱ ጸድቋል!**\n"
                f"👤 ስም፦ {u_name}\n"
                f"🔢 የተፈቀደ የዕጣ ብዛት፦ {count}\n"
                f"🎫 የተሰጡ ቁጥሮች፦ `{tickets_str}`"
            )
            
            # ለደንበኛው የሚላክ
            user_msg = (
                f"✅ **የገንዘብ ማረጋገጫዎ በባለቤቱ ጽድቋል!**\n\n"
                f"🎉 **እንኳን ደስ አለዎት! በባለቤቱ ውሳኔ መሠረት የተሰጡዎት {count} የዕጣ ቁጥሮች፦**\n\n"
                f"{tickets_formatted}\n\n"
                f"*(እነዚህ ቁጥሮች በፍጹም አይደገሙም፤ በጥንቃቄ ይያዙ)*"
            )
            await context.bot.send_message(chat_id=int(user_id), text=user_msg, parse_mode="Markdown")
            
        except sqlite3.IntegrityError:
            await query.message.edit_caption("❌ ይህ ሪሲት አስቀድሞ ተመዝግቧል።")

# =======================
# MAIN ASYNC FUNCTION
# =======================
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex('^(🏦 የተቀባይ አካውንት|📸 ሪሲት ለመላክ|🎁 ሽልማቶች|📞 በስልክ ለማግኘት)$') | filters.TEXT & ~filters.COMMAND, handle_text_buttons))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(admin_callback))
    
    print("ቦቱ በአዝራሮች ሜኑ እና በአስተዳዳሪ ፈቃድ ሥርዓት ሥራ ጀምሯል...")
    await app.initialize()
    await app.updater.start_polling()
    await app.start()
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
