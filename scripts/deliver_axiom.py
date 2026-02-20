import os
import asyncio
from supabase import create_client
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
bot = Bot(token=os.environ["TELEGRAM_TOKEN"])
chat_id = os.environ["TELEGRAM_CHAT_ID"]

async def deliver_axiom():
    result = supabase.table("settings")\
        .select("value")\
        .eq("key", "todays_axiom")\
        .execute()

    axiom = result.data[0]["value"] if result.data else None

    if not axiom:
        return

    await bot.send_message(
        chat_id=chat_id,
        text=f"🌙 *Tonight's Axiom*\n\n_{axiom}_\n\nSleep on it.",
        parse_mode="Markdown"
    )

asyncio.run(deliver_axiom())
