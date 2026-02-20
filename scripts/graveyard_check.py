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
        await bot.send_message(
            chat_id=chat_id,
            text="🪦 Graveyard is empty. You've caught everything so far."
        )
        return

    problem = result.data[0]

    message = (
        f"⚰️ *GRAVEYARD*\n\n"
        f"You missed this one before.\n\n"
        f"*Problem:* {problem['original_problem']}\n\n"
        f"Don't solve it. Just recall the trap mentally.\n\n"
        f"Reply *got it* if you remember, *nope* if it's still foggy."
    )

    await bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")

    # Update settings so handle_reply knows what's pending
    supabase.table("settings")\
        .update({"value": problem["id"]})\
        .eq("key", "todays_problem_id")\
        .execute()

asyncio.run(graveyard_nudge())
