import os
import asyncio
from supabase import create_client
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"].strip(), os.environ["SUPABASE_KEY"].strip())
bot = Bot(token=os.environ["TELEGRAM_TOKEN"].strip())
chat_id = os.environ["TELEGRAM_CHAT_ID"].strip()

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
        f"Don't solve it. Just recall the trap mentally."
    )

    # Inline buttons — tapping triggers the Edge Function instantly
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Got It", callback_data=f"gy|{problem['id']}|got_it"),
        InlineKeyboardButton("❌ Still Foggy", callback_data=f"gy|{problem['id']}|foggy")
    ]])

    await bot.send_message(
        chat_id=chat_id,
        text=message,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

    print(f"Graveyard nudge sent: {problem['id'][:8]}... ({problem['error_category']})")

asyncio.run(graveyard_nudge())
