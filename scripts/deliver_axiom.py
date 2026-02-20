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
    # Get today's axiom
    axiom_result = supabase.table("settings")\
        .select("value")\
        .eq("key", "todays_axiom")\
        .execute()

    axiom = axiom_result.data[0]["value"] if axiom_result.data else None
    if not axiom:
        return

    # Get today's problem ID and check if user caught or missed
    problem_result = supabase.table("settings")\
        .select("value")\
        .eq("key", "todays_problem_id")\
        .execute()

    problem_id = problem_result.data[0]["value"] if problem_result.data else None
    framing = ""

    if problem_id:
        log = supabase.table("daily_log")\
            .select("caught")\
            .eq("problem_id", problem_id)\
            .execute()

        if log.data and log.data[0]["caught"] is not None:
            if log.data[0]["caught"]:
                framing = "You spotted this one today. Lock it in.\n\n"
            else:
                framing = "This one got you today. Make sure it never does again.\n\n"

    await bot.send_message(
        chat_id=chat_id,
        text=f"🌙 *Tonight's Axiom*\n\n{framing}_{axiom}_\n\nSleep on it.",
        parse_mode="Markdown"
    )
    print(f"Axiom delivered. Framing: {'caught' if 'spotted' in framing else 'missed' if 'got you' in framing else 'neutral'}")

asyncio.run(deliver_axiom())
