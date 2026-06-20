async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # ၁။ ဗေဒင်စတင်ရန် နှိပ်လိုက်ချိန် (ကတ်ကျောဘက်ပုံစစ်စစ်ကိုပဲ အရင်ဆုံးပြရမည်)
    if query.data == "start_tarot":
        if user_id != config.CREATOR_ID:
            if USER_USAGE_LOG.get(user_id) == today_str:
                reject_msg = f"<b>{RED_TEXT_START}😥၀မ်းနည်းပါတယ်ခင်ဗျာ...Tarot ဟောကိုန်းများအား တစ်နေ့လျင် တစ်ကြိမ်သာ အသုံးပြုနိုင်မည် ဖြစ်ပါတယ်...😥{RED_TEXT_END}</b>"
                await query.message.reply_text(reject_msg, parse_mode="HTML")
                return
        
        inline_kb = [[InlineKeyboardButton("🃏 ကတ်ကိုလှန်ပါ (Click to Flip)", callback_data="flip_card")]]
        reply_markup = InlineKeyboardMarkup(inline_kb)
        
        # [FIXED] စာသားသက်သက်မဟုတ်ဘဲ အပေါ်က ကတ်ကျောဘက်ပုံ (Card Back) ကို အရင်ဆုံး စနစ်တကျ ပို့ပေးခြင်း
        await query.message.reply_photo(
            photo=CARD_BACK_IMAGE,
            caption="<b>သင့်မေးခွန်းကိုအာရုံပြု၍ ကတ်အား ရွေးချယ်ပါ</b>",
            reply_markup=get_contact_button(),
            parse_mode="HTML"
        )
        # အောက်က ကတ်လှန်ရန် ခလုတ်ကိုပါ တွဲပြပေးထားမည်
        await query.message.reply_text("အထက်ပါကတ်ကို လှန်ရန် အောက်ပါခလုတ်ကို နှိပ်ပါ -", reply_markup=reply_markup)

    # ၂။ "ကတ်ကိုလှန်ပါ" ခလုတ်ကို နှိပ်လိုက်သည့်အချိန် (3D Flip Effect ကဲ့သို့ ပုံချင်း အစားထိုးလဲလှယ်မည်)
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
        
        # 🌟 [3D FLIP EFFECT LOGIC] 🌟
        # မက်ဆေ့ချ်အသစ် ထပ်မဆောက်ဘဲ အပေါ်က "ကတ်ကျောဘက်ပုံ" နေရာမှာ "ကတ်အလှန်ပုံ" ဖြင့် ချက်ချင်း ဖျက်ပြီး အစားထိုးလိုက်ခြင်း ဖြစ်သည်။
        from telegram import InputMediaPhoto
        try:
            # ခလုတ်နှိပ်လိုက်တဲ့ ကတ်ကျောဘက်ပုံရှိရာ စာမျက်နှာ (query.message) ရဲ့ Media ကို တိုက်ရိုက် လဲလှယ်ပစ်သည်
            loading_msg = await query.message.edit_media(
                media=InputMediaPhoto(media=card_image, caption=f"🃏 <b>{card_name}</b>\n\n⏳ ကံကြမ္မာဟောကိန်းများအား ခေတ္တာစောင့်ပါ...", parse_mode="HTML"),
                reply_markup=get_contact_button()
            )
        except Exception as e:
            logger.error(f"Flip error: {e}")
            # အကယ်၍ အကြောင်းအမျိုးမျိုးကြောင့် Edit လုပ်မရပါက Message အသစ်ဖြင့် ပုံအသစ်ပြသည်
            loading_msg = await query.message.reply_photo(
                photo=card_image,
                caption=f"🃏 <b>{card_name}</b>\n\n⏳ ကံကြမ္မာဟောကိန်းများအား ခေတ္တာစောင့်ပါ...",
                reply_markup=get_contact_button(),
                parse_mode="HTML"
            )
        
        # ၃ စက္ကန့် စောင့်ဆိုင်းခြင်း
        await asyncio.sleep(3)
        
        # ဟောပြောချက်စာသားများ အပြည့်အစုံ ပြင်ဆင်ခြင်း
        full_interpretation = (
            f"🃏 <b>{card_name}</b>\n\n"
            f"❤️ <b>အချစ်ရေး</b>\n{reading_data['love']}\n\n"
            f"💼 <b>စီးပွားရေး/အလုပ်အကိုင်</b>\n{reading_data['business']}\n\n"
            f"🎓 <b>ပညာရေး</b>\n{reading_data['education']}\n\n"
            f"🩺 <b>ကျန်းမာရေး</b>\n{reading_data['health']}\n\n"
            f"✨ <b>အနှစ်ချုပ်၊ ရှောင်ရန်ဆောင်ရန်နှင့် ထူးခြားချက်</b>\n{reading_data['summary']}"
        )
        
        # Loading စာသားနေရာတွင် ဟောချက်များဖြင့် အပြီးသတ် အစားထိုးခြင်း
        await loading_msg.edit_caption(
            caption=full_interpretation,
            reply_markup=get_contact_button(),
            parse_mode="HTML"
        )
