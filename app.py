import os
import threading
import asyncio
import nest_asyncio
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# حل مشكلة الحلقات في Flask
nest_asyncio.apply()

# ====== قراءة التوكن من متغيرات البيئة ======
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set in environment variables")

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ====== دالة التحميل مع خيارات الجودة ======
async def download_video(url, format_type):
    ydl_opts = {
        'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
        'progress_hooks': [lambda d: print(d['status'])],
    }
    
    if format_type == 'audio':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    elif format_type == 'video_1080':
        ydl_opts.update({
            'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
            'merge_output_format': 'mp4',
        })
    elif format_type == 'video_720':
        ydl_opts.update({
            'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
            'merge_output_format': 'mp4',
        })
    else:  # video_480
        ydl_opts.update({
            'format': 'bestvideo[height<=480]+bestaudio/best[height<=480]',
            'merge_output_format': 'mp4',
        })
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if format_type == 'audio':
                filename = filename.rsplit('.', 1)[0] + '.mp3'
            return filename, info.get('title', 'video')
    except Exception as e:
        return None, str(e)

# ====== أوامر البوت ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أرسل رابط يوتيوب، تيك توك، إنستغرام أو تويتر، وسأحمله لك!\n\n"
        "📌 اختر الجودة بعد إرسال الرابط."
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if any(site in url for site in ['youtube.com', 'youtu.be', 'tiktok.com', 'instagram.com', 'twitter.com', 'x.com', 'facebook.com']):
        context.user_data['url'] = url
        keyboard = [
            [InlineKeyboardButton("🎬 1080p", callback_data='video_1080')],
            [InlineKeyboardButton("🎬 720p", callback_data='video_720')],
            [InlineKeyboardButton("🎬 480p", callback_data='video_480')],
            [InlineKeyboardButton("🎵 MP3", callback_data='audio')]
        ]
        await update.message.reply_text("✅ اختر الجودة:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("⚠️ الرجاء إرسال رابط مدعوم (يوتيوب، تيك توك، إلخ).")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    url = context.user_data.get('url')
    if not url:
        await query.edit_message_text("❌ لم يتم العثور على رابط، أرسل الرابط أولاً.")
        return
    
    format_type = query.data
    await query.edit_message_text(f"⏳ جاري التحميل... (قد يستغرق دقيقة)")
    
    filename, title = await download_video(url, format_type)
    
    if filename and os.path.exists(filename):
        await query.edit_message_text(f"📤 جاري رفع: {title}")
        with open(filename, 'rb') as f:
            await query.message.reply_document(f, filename=os.path.basename(filename))
        os.remove(filename)
        await query.message.reply_text("✅ تم التحميل والإرسال بنجاح!")
    else:
        await query.edit_message_text(f"❌ فشل التحميل: {title}")

# ====== تشغيل البوت في Thread منفصل ======
def run_bot():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🤖 البوت يعمل...")
    app.run_polling()

# ====== Flask (لـ Render) ======
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Bot is running!"

@flask_app.route('/health')
def health():
    return "OK", 200

# ====== التشغيل الرئيسي ======
if __name__ == "__main__":
    # شغل البوت في خلفية
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # شغل Flask لتلبية منفذ Render
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)
