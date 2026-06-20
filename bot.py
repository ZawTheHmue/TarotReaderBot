import logging
import json
import random
import asyncio
import http.server
import threading
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import config

# Logging Configuration
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Tarot Data Load လုပ်ခြင်း
try:
    with open('tarot_data.json', 'r', encoding='utf-8') as f:
        TAROT_DATA = json.load(f)
except Exception as e:
    logger.error(f"Error loading tarot_data.json: {e}")
    TAROT_DATA = {}

# User များ၏ နေ့စဉ်ဗေဒင်မေးထားသော မှတ်တမ်း
USER_USAGE_LOG = {}

# Bot ထဲသို့ ဝင်ရောက်လာသော User IDs များကို သိမ်းဆည်းခြင်း
ALL_USERS = set()

# 🛑 [FIXED] Telegram မှ တိုက်ရိုက်ဖတ်နိုင်သော စိတ်ချရသည့် ကတ်ကျောဘက်ပုံ Direct URL အား ပြောင်းလဲခြင်း
CARD_BACK_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/2/2b/Tarot_Back_RWS.jpg"

# HTML custom styling သုံး၍ အနီရောင် စာသားထွက်ပေါ်စေရန် သုံးသော စာလုံးပုံစံ
RED_TEXT_START = "<code>"
RED_TEXT_END = "</code>"

# Dummy Web Server (Render Port Timeout Check ကျော်ရန်)
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
    httpd.serve_forever()

# Contact with Astrologer Button
def get_contact_button():
    url = f"https://t.me/{config.CREATOR_USERNAME}" if config.CREATOR_USERNAME else "https://t.me/"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Contact with Astrologer(10000MMK)", url=url)]
    ])

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ALL_USERS.add(user_id)
    
    if user_id == config.CREATOR_ID:
        keyboard = [['📢 Send Notification (Broadcast)']]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("မင်္ဂလာပါ Creator ဗျာ။ သင်သည် အကန့်အသတ်မရှိ အသုံးပြုနိုင်ပါသည်။", reply_markup=reply_markup)
    
    inline_keyboard = [[InlineKeyboardButton("🔮 Tarot ဗေဒင်ဟောကိန်းရယူမယ်", callback_data="start_tarot")]]
    await update.message.reply_text(
        "🔮 Tarot Reader Bot မှ ကြိုဆိုပါတယ်ဗျာ။ အောက်ပါခလုတ်ကိုနှိပ်၍ ဗေဒင်မေးမြန်းနိုင်ပါသည်။",
        reply_markup=InlineKeyboardMarkup(inline_keyboard)
    )

# General User များ စာသားပေးပို့ခြင်းကို ပိတ်ပင်ခြင်း
async def restrict_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id == config.CREATOR_ID and context.user_data.get('waiting_for_broadcast'):
        context.user_data['waiting_for_broadcast'] = False
        broadcast_text = update.message.text
        count = 0
        for uid in ALL_USERS:
            try:
                await context.bot.send_message(chat_id=uid, text=f"📢 <b>အကြောင်းကြားစာ -</b>\n\n{broadcast_text}", parse_mode="HTML")
                count += 1
            except Exception:
                pass
        await update.message.reply_text(f"User စုစုပေါင်း {count} ယောက်ထံ စာပို့ပြီးပါပြီ။")
        return
    return

# Creator Admin Menu ขခလုတ်
async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == config.CREATOR_ID:
        if update.message.text == '📢 Send Notification (Broadcast)':
            context.user_data['waiting_for_broadcast'] = True
            await update.message.reply_text("User အားလုံးထံ ပေးပို့လိုမည့် စာသားကို ရိုက်နှိပ်ပေးပို့ပါ။")

# Inline Keyboard Handlers
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if query.data == "start_tarot":
        if user_id != config.CREATOR_ID:
            if USER_USAGE_LOG.get(user_id) == today_str:
                reject_msg = f"<b>{RED_TEXT_START}😥၀မ်းနည်းပါတယ်ခင်ဗျာ...Tarot ဟောကိုန်းများအား တစ်နေ့လျင် တစ်ကြိမ်သာ အသုံးပြုနိုင်မည် ဖြစ်ပါတယ်...😥{RED_TEXT_END}</b>"
                await query.message.reply_text(reject_msg, parse_mode="HTML")
                return
        
        inline_kb = [[InlineKeyboardButton("🃏 ကတ်ကိုလှန်ပါ (Click to Flip)", callback_data="flip_card")]]
        reply_markup = InlineKeyboardMarkup(inline_kb)
        
        # 🛑 [FIXED] ဓာတ်ပုံပေးပို့ရာတွင် ပုံစံလွဲမှားမှုမရှိစေရန် တိကျစွာ ပို့ဆောင်ခြင်း
        try:
            await query.message.reply_photo(
                photo=CARD_BACK_IMAGE,
                caption="<b>သင့်မေးခွန်းကိုအာရုံပြု၍ ကတ်အား ရွေးချယ်ပါ</b>",
                reply_markup=get_contact_button(),
                parse_mode="HTML"
            )
            await query.message.reply_text("အထက်ပါကတ်ကျောဘက်ကို နှိုက်ရန် အောက်ပါခလုတ်ကိုနှိပ်ပါ-", reply_markup=reply_markup)
        except Exception as img_err:
            logger.error(f"Error sending back image: {img_err}")
            # အကယ်၍ ပုံပို့ရခက်ခဲပါက Text စနစ်ဖြင့် အရန်အနေဖြင့် ပြသပေးခြင်း
            await query.message.reply_text(
                "<b>သင့်မေးခွန်းကိုအာရုံပြု၍ ကတ်အား ရွေးချယ်ပါ (🃏)</b>", 
                reply_markup=reply_markup, 
                parse_mode="HTML"
            )

    elif query.data == "flip_card":
        USER_USAGE_LOG[user_id] = today_str
        
        if not TAROT_DATA:
            await query.message.reply_text("⚠️ ဟောချက်ဒေတာဖိုင် (tarot_data.json) မရှိသေးပါသဖြင့် ခေတ္တာစောင့်ဆိုင်းပေးပါ။")
            return

        card_key = random.choice(list(TAROT_DATA.keys()))
        card = TAROT_DATA[card_key]
        is_upright = random.choice([True, False])
        
        card_name = card["name_upright"] if is_upright else card["name_reversed"]
        card_image = card["image_upright"] if is_upright else card["image_reversed"]
        reading_data = card["upright"] if is_upright else card["reversed"]
        
        # 🛑 [FIXED] ကတ်ပုံအသစ်များ၏ URL များအား အမှားကင်းစင်အောင် ပေးပို့ခြင်း
        try:
            loading_msg = await query.message.reply_photo(
                photo=card_image,
                caption=f"🃏 <b>{card_name}</b>\n\n⏳ ကံကြမ္မာဟောကိန်းများအား ခေတ္တာစောင့်ပါ...",
                reply_markup=get_contact_button(),
                parse_mode="HTML"
            )
        except Exception:
            # အကယ်၍ ဖြည့်စွက်ထားသော ပုံ Link ပျက်နေပါက Wikipedia ပုံစံဖြင့် လှမ်းပြောင်းပေးခြင်း
            fallback_img = "https://upload.wikimedia.org/wikipedia/commons/9/90/RWS_Tarot_00_Fool.jpg"
            loading_msg = await query.message.reply_photo(
                photo=fallback_img,
                caption=f"🃏 <b>{card_name}</b>\n\n⏳ ကံကြမ္မာဟောကိန်းများအား ခေတ္တာစောင့်ပါ...",
                reply_markup=get_contact_button(),
                parse_mode="HTML"
            )
        
        await asyncio.sleep(3)
        
        full_interpretation = (
            f"🃏 <b>{card_name}</b>\n\n"
            f"❤️ <b>အချစ်ရေး</b>\n{reading_data['love']}\n\n"
            f"💼 <b>စီးပွားရေး/အလုပ်အကိုင်</b>\n{reading_data['business']}\n\n"
            f"🎓 <b>ပညာရေး</b>\n{reading_data['education']}\n\n"
            f"🩺 <b>ကျန်းမာရေး</b>\n{reading_data['health']}\n\n"
            f"✨ <b>အနှစ်ချုပ်၊ ရှောင်ရန်ဆောင်ရန်နှင့် ထူးခြားချက်</b>\n{reading_data['summary']}"
        )
        
        await loading_msg.edit_caption(
            caption=full_interpretation,
            reply_markup=get_contact_button(),
            parse_mode="HTML"
        )

def main():
    if not config.BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN missing!")
        return

    threading.Thread(target=run_health_server, daemon=True).start()

    application = Application.builder().token(config.BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, admin_buttons), group=1)
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, restrict_text_messages), group=2)

    print("Tarot Bot Is Running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
