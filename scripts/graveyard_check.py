import os
import asyncio
from supabase import create_client
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
bot = Bot(token=os.environ["TELEGRAM_TOKEN"])
chat_id = os.environ["TELEGRAM_CHAT_ID"]

async def graveyard_nudge():
    result = supabase.table("qa_flaw_deck")\
        .select("*")\
        .eq("status", "missed")\
        .order("delivered_at")\
        .limit(1)\
        .execute()

    if not result.data:
        return  # Silent — no nudge if graveyard is empty

    problem = result.data[0]

    message = (
        f"⚰️ *GRAVEYARD*\n\n"
        f"You missed this one before.\n\n"
        f"*Problem:* {problem['original_problem']}\n\n"
        f"Don't solve it. Just recall the trap mentally.\n\n"
        f"Reply *got it* if you remember, *nope* if it's still foggy."
    )

    await bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")

    # Write to graveyard_pending_id so handle_reply.py knows
    # which problem a "got it"/"nope" reply belongs to
    supabase.table("settings")\
        .upsert({"key": "graveyard_pending_id", "value": problem["id"]})\
        .execute()

    print(f"Graveyard nudge sent: {problem['id'][:8]}... ({problem['error_category']})")

asyncio.run(graveyard_nudge())
