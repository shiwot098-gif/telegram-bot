import os
import sqlite3
import re
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

from PIL import Image
import pytesseract
from pyzbar.pyzbar import decode

# =======================
# CONFIG
# =======================
TOKEN = os.getenv("8611743019:AAGEHD_MZTciUYBVatUTcJC5uCw-OM5Ij3U")

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
# HELPERS
# =======================
def extract_transaction_id(text):
    pattern = r"[A-Z0-9]{10,}"
    match = re.findall(pattern, text.upper())
    return match[0] if match else None


def scan_qr(image_path):
    img = Image.open(image_path)
    qr_codes = decode(img)
    if qr_codes:
        return qr_codes[0].data.decode("utf-8")
    return None


def check_duplicate(tx_id, qr):
    cursor.execute("SELECT * FROM transactions WHERE transaction_id=? OR qr_data=?", (tx_id, qr))
    return cursor.fetchone()


def save_transaction(tx_id, qr, status):
    cursor.execute(
        "INSERT OR IGNORE INTO transactions (transaction_id, qr_data, status, created_at) VALUES (?, ?, ?, ?)",
        (tx_id, qr, status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()

# =======================
# BOT HANDLERS
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome!\nSend receipt image to verify transaction."
    )


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()

    file_path = "image.jpg"
    await file.download_to_drive(file_path)

    # OCR
    text = pytesseract.image_to_string(Image.open(file_path))
    tx_id = extract_transaction_id(text)

    # QR scan
    qr_data = scan_qr(file_path)

    if not tx_id or not qr_data:
        await update.message.reply_text("⚠️ Could not read QR or Transaction ID")
        return

    # check duplicate
    exists = check_duplicate(tx_id, qr_data)

    if exists:
        result = "❌ DUPLICATE TRANSACTION"
        status = "DUPLICATE"
    else:
        result = "✅ NEW VALID TRANSACTION"
        status = "NEW"
        save_transaction(tx_id, qr_data, status)

    await update.message.reply_text(
        f"{result}\n\nTX ID: {tx_id}\nQR: {qr_data}"
    )


# =======================
# MAIN
# =======================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.PHOTO, handle_image))

app.run_polling()
