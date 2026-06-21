import logging
import json
import random
import asyncio
import http.server
import threading
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import config

# Logging Configuration
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Data Files Loading
try:
    with open('tarot_data.json', 'r', encoding='utf-8') as f:
        TAROT_DATA = json.load(f)
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

CARD_BACK_IMAGE = "https://images.unsplash.com/photo-1579783902614-a3fb3927b6a5?q=80&w=500&auto=format&fit=crop"
RED_TEXT_START = "<code>"
RED_TEXT_END = "</code>"

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

# Bot စတင်ချိန်တွင် Background Task ကို ချိတ်ဆက်ပေးမည့် Post Init
async def post_init(application: Application) -> None:
    asyncio.create_task(daily_holiday_wishes(application))
    logger.info("Background holiday task successfully attached to Application Lifespan!")

# Contact with Astrologer Button
def get_contact_button():
    url = f"https://t.me/{config.CREATOR_USERNAME}" if config.CREATOR_USERNAME else "https://t.me/"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Contact with Astrologer🔮 (10K💵)", url=url)]
    ])

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ALL_USERS.add(user_id)
    
    if user_id == config.CREATOR_ID:
        await update.message.reply_text("မင်္ဂလာပါ Creator ဆရာသမားဗျာ။ သင်သည် အကန့်အသတ်မရှိ အသုံးပြုနိုင်ပါသည်။", reply_markup=ReplyKeyboardRemove())
    
    inline_keyboard = [[InlineKeyboardButton("🔮 Tarot ဗေဒင်ဟောကိန်းရယူမည်", callback_data="start_tarot")]]
    await update.message.reply_text(
        "🔮 Tarot Reader Bot မှ ကြိုဆိုပါတယ်ဗျာ။ အောက်ပါခလုတ်ကိုနှိပ်၍ ဗေဒင်မေးမြန်းနိုင်ပါသည်။",
        reply_markup=InlineKeyboardMarkup(inline_keyboard)
    )

# Inline Keyboard Handlers
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # ၁။ "🔮 Tarot ဗေဒင်ဟောကိန်းရယူမည်" ကို နှိပ်လိုက်ချိန်
    if query.data == "start_tarot":
        if user_id != config.CREATOR_ID:
            if USER_USAGE_LOG.get(user_id) == today_str:
                reject_msg = f"<b>{RED_TEXT_START}😥၀မ်းနည်းပါတယ်ခင်ဗျာ...Tarot ဟောကိုန်းများအား တစ်နေ့လျင် တစ်ကြိမ်သာ အသုံးပြုနိုင်မည် ဖြစ်ပါတယ်...😥{RED_TEXT_END}</b>"
                await query.message.reply_text(reject_msg, parse_mode="HTML")
                return
        
        # 🛑 [FIXED] မလိုတဲ့ စာသားမက်ဆေ့ချ်တွေအကုန်ဖြုတ်ပြီး ပုံအောက်မှာ ခလုတ်ကို တခါတည်း တွဲလျက်ကပ်ထည့်ခြင်း
        inline_kb = [[InlineKeyboardButton("🃏ကတ်တစ်ကတ်ရွေးမည်🃏", callback_data="flip_card")]]
        reply_markup = InlineKeyboardMarkup(inline_kb)
        
        await query.message.reply_photo(
            photo=CARD_BACK_IMAGE,
            caption="<b>သင့်မေးခွန်းကို အာရုံပြု၍ ကတ်အားရွေးချယ်ပါ</b>",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

    # ၂။ "🃏ကတ်တစ်ကတ်ရွေးမည်🃏" ခလုတ်ကို နှိပ်လိုက်သည့်အချိန်
    elif query.data == "flip_card":
        USER_USAGE_LOG[user_id] = today_str
        
        if not TAROT_DATA:
            await query.message.reply_text("⚠️ ဟောချက်ဒေတာဖိုင် (tarot_data.json) မရှိသေးပါသဖြင့် ခေတ္တာစောင့်ဆိုင်းပေးပါ။")
            return

        # Random ကတ် ရွေးချယ်ခြင်း
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
        
        # 🛑 [3D FLIP SIMULATION EFFECT] Message ကို မဖျက်တော့ဘဲ မူရင်းပုံနေရာမှာတင် ပုံအသစ်နဲ့ လဲလှယ်ခြင်း
        try:
            await query.message.edit_media(
                media=InputMediaPhoto(
                    media=card_image, 
                    caption=f"🃏 <b>{card_name}</b>\n\n⏳ <b>Tarot ဟောကိန်းများအား ရယူနေသည် ခေတ္တာစောင့်ပါ⏳... Loading</b>", 
                    parse_mode="HTML"
                )
            )
            
            # ၅ စက္ကန့် တိတိ စောင့်ဆိုင်းခြင်း
            await asyncio.sleep(5)
            
            # ၅ စက္ကန့်ပြည့်ပါက Loading နေရာတွင် အဟောထွက်လာပြီး အောက်၌ Contact Button ပါရှိခြင်း
            await query.message.edit_caption(
                caption=full_interpretation, 
                reply_markup=get_contact_button(), 
                parse_mode="HTML"
            )
            
        except Exception as img_err:
            logger.error(f"Image Edit Error: {img_err}")
            fallback_card_img = "https://upload.wikimedia.org/wikipedia/commons/9/90/RWS_Tarot_00_Fool.jpg"
            try:
                await query.message.edit_media(
                    media=InputMediaPhoto(
                        media=fallback_card_img, 
                        caption=f"🃏 <b>{card_name}</b>\n\n⏳ <b>Tarot ဟောကိန်းများအား ရယူနေသည် ခေတ္တာစောင့်ပါ⏳... Loading</b>", 
                        parse_mode="HTML"
                    )
                )
                await asyncio.sleep(5)
                await query.message.edit_caption(caption=full_interpretation, reply_markup=get_contact_button(), parse_mode="HTML")
            except Exception:
                pass

def main():
    if not config.BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN missing!")
        return

    run_health_server()

    application = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))

    print("Tarot Bot Is Running Successfully...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
