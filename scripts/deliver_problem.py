import os
import asyncio
from supabase import create_client
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
bot = Bot(token=os.environ["TELEGRAM_TOKEN"])
chat_id = os.environ["TELEGRAM_CHAT_ID"]

async def deliver():
    # Fetch one unseen problem
    result = supabase.table("qa_flaw_deck")\
        .select("*")\
        .eq("status", "unseen")\
        .limit(1)\
        .execute()

    if not result.data:
        await bot.send_message(
            chat_id=chat_id,
            text="⚠️ Problem bank is empty. Transcribe a new class and run process_transcript.py."
        )
        return

    problem = result.data[0]
    steps = problem["solution_steps"]

    # Send the problem statement first
    await bot.send_message(
        chat_id=chat_id,
        text=f"🔍 *SPOT THE FLAW — 2 PM*\n\n*Problem:*\n{problem['original_problem']}",
        parse_mode="Markdown"
    )

    # Send quiz poll with steps as options
    await bot.send_poll(
        chat_id=chat_id,
        question="Which step contains the logical flaw?",
        options=steps,
        type="quiz",
        correct_option_id=problem["flawed_step_number"] - 1,
        explanation=f"Trap: {problem['error_category']}\n\n{problem['explanation']}",
        is_anonymous=False
    )

    # Update settings so 10 PM script knows what to send
    supabase.table("settings")\
        .update({"value": problem["trap_axiom"]})\
        .eq("key", "todays_axiom")\
        .execute()

    supabase.table("settings")\
        .update({"value": problem["id"]})\
        .eq("key", "todays_problem_id")\
        .execute()

    # Mark as delivered
    supabase.table("qa_flaw_deck")\
        .update({"delivered_at": "now()", "status": "delivered"})\
        .eq("id", problem["id"])\
        .execute()

    # Log delivery
    supabase.table("daily_log").insert({
        "problem_id": problem["id"]
    }).execute()

asyncio.run(deliver())
