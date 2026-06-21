import logging
import json
import random
import asyncio
import http.server
import threading
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import config

# Logging Configuration
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Data Files Loading (GitHub မှ ပါလာသော Local JSON ဖိုင်ကို တိုက်ရိုက်ဖတ်ခြင်း)
try:
    with open('tarot_data.json', 'r', encoding='utf-8') as f:
        TAROT_DATA = json.load(f)
    logger.info("tarot_data.json ကို GitHub ဖိုင်မှ အောင်မြင်စွာ ဖတ်ရှုပြီးပါပြီ။")
except Exception as e:
    logger.error(f"Error loading tarot_data.json: {e}")
    TAROT_DATA = {}

try:
    with open('myanmar_holidays.json', 'r', encoding='utf-8') as f:
        HOLIDAY_DATA = json.load(f)
except Exception as e:
    logger.error(f"Error loading myanmar_holidays.json: {e}")
    HOLIDAY_DATA = {}

USER_USAGE_LOG = {}
ALL_USERS = set()

# Image Assets Configuration
CARD_BACK_IMAGE = "https://raw.githubusercontent.com/ZawTheHmue/TarotReaderBot/refs/heads/main/reversed/back.png"
BOT_BACKGROUND_IMAGE = "https://raw.githubusercontent.com/ZawTheHmue/TarotReaderBot/refs/heads/main/reversed/bg.jpg"

RED_TEXT_START = "<code>"
RED_TEXT_END = "</code>"

# User Keyboard (အောက်ခြေတွင် အမြဲပေါ်နေမည့် ခလုတ်နှစ်ခု)
def get_user_reply_keyboard():
    keyboard = [
        [KeyboardButton("🔮 Tarot ဗေဒင်ဟောကိန်းရယူမည်")],
        [KeyboardButton("🔮 Contact with Tarot Fortune Teller")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Contact Inline Button Helper
def get_contact_inline_button():
    url = f"https://t.me/{config.CREATOR_USERNAME}" if config.CREATOR_USERNAME else "https://t.me/"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Contact with Tarot Fortune Teller🔮(10K💵)", url=url)]
    ])

# Dummy Web Server
def run_health_server():
    port = int(os.getenv("PORT", 10000))
    server_address = ('', port)
    class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Bot is alive and running!")
    httpd = http.server.HTTPServer(server_address, HealthCheckHandler)
    logger.info(f"Dummy Health Check Server Running on Port {port}...")
    
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

# နေ့စဉ် မြန်မာ့နေ့ထူးနေ့မြတ် ဆုတောင်းစာ Auto ပို့ပေးမည့် Background Task
async def daily_holiday_wishes(application: Application):
    while True:
        try:
            now = datetime.now()
            if now.hour == 8 and now.minute == 0:
                today_md = now.strftime("%m-%d")
                if today_md in HOLIDAY_DATA:
                    holiday_info = HOLIDAY_DATA[today_md]
                    wish_message = f"🌟 <b>{holiday_info['title']}</b> 🌟\n\n{holiday_info['wish_text']}"
                    for user_id in list(ALL_USERS):
                        try:
                            await application.bot.send_message(chat_id=user_id, text=wish_message, parse_mode="HTML")
                            await asyncio.sleep(0.05)
                        except Exception:
                            pass
                await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Error in daily holiday task: {e}")
        await asyncio.sleep(30)

async def post_init(application: Application) -> None:
    asyncio.create_task(daily_holiday_wishes(application))
    logger.info("Background holiday task successfully attached to Application Lifespan!")

# ကတ်ရွေးချယ်ခြင်း Setup ကို ပို့ပေးမည့် ဘုံ Function
async def send_tarot_setup(choice_user_id, chat_id, context: ContextTypes.DEFAULT_TYPE):
    today_str = datetime.now().strftime("%Y-%m-%d")
    if choice_user_id != config.CREATOR_ID:
        if USER_USAGE_LOG.get(choice_user_id) == today_str:
            reject_msg = f"<b>{RED_TEXT_START}😥၀မ်းနည်းပါတယ်ခင်ဗျာ...Tarot ဟောကိန်းများအား တစ်နေ့လျင် တစ်ကြိမ်သာ အသုံးပြုနိုင်မည် ဖြစ်ပါတယ်...😥{RED_TEXT_END}</b>"
            await context.bot.send_message(chat_id=chat_id, text=reject_msg, parse_mode="HTML")
            return

    # မက်ဆေ့ချ် (၃) ခု သီးသန့်ထွက်မည်
    msg1 = await context.bot.send_message(
        chat_id=chat_id, text="<b>သင့်မေးခွန်းကို အာရုံပြု၍ ကတ်အားရွေးချယ်ပါ</b>", parse_mode="HTML"
    )
    # ကတ်ကျောဖုံးပုံကို ပြသပေးခြင်း
    msg2 = await context.bot.send_photo(
        chat_id=chat_id, photo=CARD_BACK_IMAGE
    )
    
    inline_kb = [[InlineKeyboardButton("🃏ကတ်တစ်ကတ်ရွေးမည်🪄", callback_data="flip_card")]]
    msg3 = await context.bot.send_message(
        chat_id=chat_id, text="⬇️ကတ်ရွေးမည်⬇️", reply_markup=InlineKeyboardMarkup(inline_kb)
    )
    
    context.user_data['msgs_to_edit'] = [msg1.message_id, msg2.message_id, msg3.message_id]

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ALL_USERS.add(user_id)
    
    if user_id == config.CREATOR_ID:
        await update.message.reply_text("မင်္ဂလာပါ Creator ဆရာသမားဗျာ။ သင်သည် အကန့်အသတ်မရှိ အသုံးပြုနိုင်ပါသည်။", reply_markup=get_user_reply_keyboard())
    else:
        await update.message.reply_text("မင်္ဂလာပါဗျာ။ Tarot Reader Bot မှ ကြိုဆိုပါသည်။", reply_markup=get_user_reply_keyboard())
    
    inline_keyboard = [[InlineKeyboardButton("🔮 Tarot ဗေဒင်ဟောကိန်းရယူမည်", callback_data="start_tarot")]]
    await update.message.reply_text(
        "🔮 အောက်ပါခလုတ်ကိုနှိပ်၍ ဗေဒင်မေးမြန်းနိုင်ပါသည်။",
        reply_markup=InlineKeyboardMarkup(inline_keyboard)
    )

# Text Messages Handler (User Keyboard ခလုတ်များအတွက်)
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if text == "🔮 Tarot ဗေဒင်ဟောကိန်းရယူမည်":
        await send_tarot_setup(user_id, chat_id, context)
    elif text == "🔮 Contact with Astrologer":
        url = f"https://t.me/{config.CREATOR_USERNAME}" if config.CREATOR_USERNAME else "https://t.me/"
        await update.message.reply_text(
            "🔮 <b>Astrologer နှင့် တိုက်ရိုက်ဆွေးနွေးရန် အောက်ပါခလုတ်ကို နှိပ်ပါ</b> 🔮",
            reply_markup=get_contact_inline_button(),
            parse_mode="HTML"
        )

# Inline Keyboard Handlers
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    today_str = datetime.now().strftime("%Y-%m-%d")
    chat_id = query.message.chat_id
    
    if query.data == "start_tarot":
        await send_tarot_setup(user_id, chat_id, context)

    elif query.data == "flip_card":
        USER_USAGE_LOG[user_id] = today_str
        
        if not TAROT_DATA:
            await query.message.reply_text("⚠️ ဟောချက်ဒေတာဖိုင် (tarot_data.json) မရှိသေးပါသဖြင့် ခေတ္တာစောင့်ဆိုင်းပေးပါ။")
            return

        # Random ကတ် ရွေးချယ်ခြင်း Logic
        card_key = random.choice(list(TAROT_DATA.keys()))
        card = TAROT_DATA[card_key]
        is_upright = random.choice([True, False])
        
        base_name = card["name_upright"].replace(" (အတည်)", "").replace("(အတည်)", "").strip()
        card_name = base_name if is_upright else f"{base_name} (ပြောင်းပြန်)"
        
        card_image = card["image_upright"] if is_upright else card["image_reversed"]
        reading_data = card["upright"] if is_upright else card["reversed"]
        
        full_interpretation = (
            f"🃏 <b>{card_name}</b>\n\n"
            f"❤️ <b>အချစ်ရေး</b>\n{reading_data['love']}\n\n"
            f"💼 <b>စီးပွားရေး/အလုပ်အကိုင်</b>\n{reading_data['business']}\n\n"
            f"🎓 <b>ပညာရေး</b>\n{reading_data['education']}\n\n"
            f"🩺 <b>ကျန်းမာရေး</b>\n{reading_data['health']}\n\n"
            f"✨ <b>အနှစ်ချုပ်၊ ရှောင်ရန်ဆောင်ရန်နှင့် ထူးခြားချက်</b>\n{reading_data['summary']}"
        )
        
        msgs_to_edit = context.user_data.pop('msgs_to_edit', None)
        
        if msgs_to_edit and len(msgs_to_edit) == 3:
            m1_id, m2_id, m3_id = msgs_to_edit
            
            # ၁။ Card Name နှင့် Loading စာသား + Contact Button ကို ချက်ချင်းပြောင်းလဲခြင်း
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=m1_id, text=f"🃏 <b>{card_name}</b>", parse_mode="HTML"
                )
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=m3_id,
                    text="⏳ <b>Tarot ဟောကိန်းများအား ရယူနေသည် ခေတ္တာစောင့်ပါ⏳... Loading</b>",
                    reply_markup=get_contact_inline_button(),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Text Edit Error: {e}")

            # 🎯 ပုံပြောင်းလဲခြင်းလုပ်ငန်းကို Error ဒဏ်ခံနိုင်ရန် သီးသန့် try-except ခွဲထုတ်ခြင်း
            try:
                await context.bot.edit_message_media(
                    chat_id=chat_id, message_id=m2_id, media=InputMediaPhoto(media=card_image)
                )
            except Exception as media_err:
                logger.error(f"Media Link/Type Error (Wrong Content Type): {media_err}")
            
            # ⏱️ 3 စက္ကန့် စောင့်ဆိုင်းခြင်း
            await asyncio.sleep(3)
            
            # ၂။ ၅ စက္ကန့်ပြည့်ပါက Loading နေရာတွင် အဟောအပြည့်အစုံကို Edit ဖြင့် တည်ငြိမ်စွာ ချိန်းခြင်း
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=m3_id,
                    text=full_interpretation,
                    reply_markup=get_contact_inline_button(),
                    parse_mode="HTML"
                )
            except Exception as final_err:
                logger.error(f"Final Interpretation Edit Failure: {final_err}")

def main():
    if not config.BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN missing!")
        return

    run_health_server()

    application = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start))
    
    # User Reply Keyboard Handler
    from telegram.ext import MessageHandler, filters
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    application.add_handler(CallbackQueryHandler(handle_callback))

    print("Tarot Bot Is Running Successfully...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
