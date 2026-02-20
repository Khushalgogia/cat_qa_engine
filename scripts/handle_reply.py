import os
import asyncio
from supabase import create_client
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
bot = Bot(token=os.environ["TELEGRAM_TOKEN"])
chat_id = os.environ["TELEGRAM_CHAT_ID"]

async def handle():
    # Get recent messages from bot
    updates = await bot.get_updates(limit=10)
    
    reply = None
    for update in reversed(updates):
        if update.message and update.message.text:
            text = update.message.text.lower().strip()
            if text in ["caught", "missed", "got it", "nope"]:
                reply = text
                break

    if not reply:
        return

    caught = reply in ["caught", "got it"]

    # Get today's problem id
    result = supabase.table("settings")\
        .select("value")\
        .eq("key", "todays_problem_id")\
        .execute()

    problem_id = result.data[0]["value"] if result.data else None
    if not problem_id:
        return

    new_status = "caught" if caught else "missed"

    supabase.table("qa_flaw_deck")\
        .update({"status": new_status})\
        .eq("id", problem_id)\
        .execute()

    supabase.table("daily_log")\
        .update({"caught": caught})\
        .eq("problem_id", problem_id)\
        .execute()

    # If missed, status stays 'missed' — graveyard_check.py will query this

asyncio.run(handle())
