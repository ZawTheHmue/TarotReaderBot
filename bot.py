import logging
import json
import random
import asyncio
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

# User များ၏ နေ့စဉ်ဗေဒင်မေးထားသော မှတ်တမ်း (Memory တွင် ခေတ္တသိမ်းသည်)
# Format: {user_id: "YYYY-MM-DD"}
USER_USAGE_LOG = {}

# Bot ထဲသို့ ဝင်ရောက်လာသော User IDs များကို Broadcast ရန်အတွက် သိမ်းဆည်းခြင်း
ALL_USERS = set()

# ကတ်ကျောဘက်မျက်နှာပြင်ပုံ (GIF သို့မဟုတ် 3D Flip သဏ္ဌာန်ပြရန် သင့်တော်ရာ URL)
CARD_BACK_IMAGE = "https://raw.githubusercontent.com/ColCard Tarot/CardBack/main/back.png" # ဥပမာကျောဘက်ပုံ

# HTML custom styling သုံး၍ အနီရောင် စာသားထွက်ပေါ်စေရန် သုံးသော စာလုံးပုံစံ (Telegram Custom Emoji format သို့မဟုတ် code တုံး)
RED_TEXT_START = "<code>"
RED_TEXT_END = "</code>"

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
    
    # Creator ဆိုလျှင် Admin Keyboard ပြမည်
    if user_id == config.CREATOR_ID:
        keyboard = [['📢 Send Notification (Broadcast)']]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("မင်္ဂလာပါ Creator ဗျာ။ သင်သည် အကန့်အသတ်မရှိ အသုံးပြုနိုင်ပါသည်။", reply_markup=reply_markup)
    
    # Tarot စတင်ရန် Inline Button ပြခြင်း
    inline_keyboard = [[InlineKeyboardButton("🔮 Tarot ဗေဒင်ဟောကိန်းရယူမယ်", callback_data="start_tarot")]]
    await update.message.reply_text(
        "🔮 Tarot Reader Bot မှ ကြိုဆိုပါတယ်ဗျာ။ အောက်ပါခလုတ်ကိုနှိပ်၍ ဗေဒင်မေးမြန်းနိုင်ပါသည်။",
        reply_markup=InlineKeyboardMarkup(inline_keyboard)
    )

# General User များ စာသားပေးပို့ခြင်းကို ပိတ်ပင်ခြင်း (Restriction)
async def restrict_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Creator က Broadcast လုပ်ရန် စာသားပို့ခြင်းကို ခွင့်ပြုသည်
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

    # ပုံမှန် User များ စာရိုက်လာပါက တုံ့ပြန်မှု မလုပ်ဘဲ လျစ်လျူရှု (သို့မဟုတ်) သတိပေးချက်ထုတ်သည်
    # ဤနေရာတွင် User အား မည်သည့်အရာမျှ မလုပ်ဆောင်စေရန် လျစ်လျူရှုခြင်းဖြင့် စည်းကမ်းသတ်မှတ်ပါသည်
    return

# Creator Admin Menu ခလုတ် နှိပ်ခြင်း
async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == config.CREATOR_ID:
        if update.message.text == '📢 Send Notification (Broadcast)':
            context.user_data['waiting_for_broadcast'] = True
            await update.message.reply_text("User အားလုံးထံ ပေးပို့လိုမည့် စာသားကို ရိုက်နှိပ်ပေးပို့ပါ။")

# Inline Keyboard ရဲ့ လုပ်ဆောင်ချက်များ
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # ၁။ Tarot ဗေဒင်စတင်ရန် ခလုတ်နှိပ်ခြင်း
    if query.data == "start_tarot":
        # Rate Limit စစ်ဆေးခြင်း (Creator ဆိုလျှင် ကျော်သွားမည်)
        if user_id != config.CREATOR_ID:
            if USER_USAGE_LOG.get(user_id) == today_str:
                # အနီရောင် Bold Text ဖြင့် ပြသခြင်း (Monospace text format ဖြင့် ထင်ရှားအောင်ပြသ)
                reject_msg = f"<b>{RED_TEXT_START}😥၀မ်းနည်းပါတယ်ခင်ဗျာ...Tarot ဟောကိုန်းများအား တစ်နေ့လျင် တစ်ကြိမ်သာ အသုံးပြုနိုင်မည် ဖြစ်ပါတယ်...😥{RED_TEXT_END}</b>"
                await query.message.reply_text(reject_msg, parse_mode="HTML")
                return
        
        # ကတ်ကျောဘက်ပုံနှင့် အစောပိုင်းစာသားပြခြင်း
        inline_kb = [[InlineKeyboardButton("🃏 ကတ်ကိုလှန်ပါ (Click to Flip)", callback_data="flip_card")]]
        reply_markup = InlineKeyboardMarkup(inline_kb)
        
        await query.message.reply_photo(
            photo=CARD_BACK_IMAGE,
            caption="<b>သင့်မေးခွန်းကိုအာရုံပြု၍ ကတ်အား ရွေးချယ်ပါ</b>",
            reply_markup=get_contact_button(), # အောက်ခြေတွင် Contact with Astrologer ပါရှိရမည်
            parse_mode="HTML"
        )
        # အောက်က Flip ခလုတ်တွဲလျက် ပို့ပေးခြင်း (ပုံကို တိုက်ရိုက်ကလစ်နှိပ်ခြင်းသဏ္ဌာန်ဖြစ်စေရန်)
        await query.message.reply_text("အထက်ပါကတ်ကျောဘက်ကို နှိုက်ရန် အောက်ပါခလုတ်ကိုနှိပ်ပါ-", reply_markup=reply_markup)

    # ၂။ ကတ်ကို လှန်လိုက်သည့် အဆင့်
    elif query.data == "flip_card":
        # မေးမြန်းမှုအောင်မြင်သဖြင့် ရက်စွဲမှတ်တမ်းသွင်းသည်
        USER_USAGE_LOG[user_id] = today_str
        
        # Random ကတ် နှင့် အတည့်/ပြောင်းပြန် ရွေးချယ်ခြင်း
        card_key = random.choice(list(TAROT_DATA.keys()))
        card = TAROT_DATA[card_key]
        is_upright = random.choice([True, False])
        
        card_name = card["name_upright"] if is_upright else card["name_reversed"]
        card_image = card["image_upright"] if is_upright else card["image_reversed"]
        reading_data = card["upright"] if is_upright else card["reversed"]
        
        # ယခင်ကတ်အပေါ်မှ စာသားကိုဖျက်ပြီး Random Card Name ကိုပြခြင်း၊ Loading text ပြခြင်း
        # 3D Flip animation ကဲ့သို့ခံစားရစေရန် လှန်ထားသော ကတ်ပုံအသစ်ကို ပို့ပေးမည်
        loading_msg = await query.message.reply_photo(
            photo=card_image,
            caption=f"🃏 <b>{card_name}</b>\n\n⏳ ကံကြမ္မာဟောကိန်းများအား ခေတ္တာစောင့်ပါ...",
            reply_markup=get_contact_button(),
            parse_mode="HTML"
        )
        
        # ၃ စက္ကန့် စောင့်ဆိုင်းခြင်း
        await asyncio.sleep(3)
        
        # ဟောပြောချက် အပြည့်အစုံကို ပြင်ဆင်ခြင်း
        full_interpretation = (
            f"🃏 <b>{card_name}</b>\n\n"
            f"❤️ <b>အချစ်ရေး</b>\n{reading_data['love']}\n\n"
            f"💼 <b>စီးပွားရေး/အလုပ်အကိုင်</b>\n{reading_data['business']}\n\n"
            f"🎓 <b>ပညာရေး</b>\n{reading_data['education']}\n\n"
            f"🩺 <b>ကျန်းမာရေး</b>\n{reading_data['health']}\n\n"
            f"✨ <b>အနှစ်ချုပ်၊ ရှောင်ရန်ဆောင်ရန်နှင့် ထူးခြားချက်</b>\n{reading_data['summary']}"
        )
        
        # Loading text နေရာတွင် ဟောပြောချက်စာသားများဖြင့် အစားထိုးလဲလှယ်ခြင်း (Caption ကို Edit လုပ်သည်)
        await loading_msg.edit_caption(
            caption=full_interpretation,
            reply_markup=get_contact_button(),
            parse_mode="HTML"
        )

def main():
    if not config.BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN missing!")
        return

    application = Application.builder().token(config.BOT_TOKEN).build()

    # Handlers တည်ဆောက်ခြင်း
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Creator Admin Commands
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, admin_buttons), group=1)
    # ပုံမှန်စာသားများ ပိတ်ပင်တားဆီးရန် Handler
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, restrict_text_messages), group=2)

    print("Tarot Bot Is Running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
