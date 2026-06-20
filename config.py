import os
from dotenv import load_dotenv

load_dotenv()

# Render Variables မှ ဖတ်ယူခြင်း
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CREATOR_ID = os.getenv("CREATOR_ID")  # ဖန်တီးသူ၏ Telegram User ID (ဥပမာ- 12345678)
CREATOR_USERNAME = os.getenv("CREATOR_USERNAME")  # တိုက်ရိုက်ဆက်သွယ်ရန် Username (မပါဘဲ t.me/)

if CREATOR_ID:
    try:
        CREATOR_ID = int(CREATOR_ID)
    except ValueError:
        pass
