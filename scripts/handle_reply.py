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
    # Get today's problem id
    result = supabase.table("settings")\
        .select("value")\
        .eq("key", "todays_problem_id")\
        .execute()

    problem_id = result.data[0]["value"] if result.data else None
    if not problem_id:
        print("No problem ID in settings. Nothing to do.")
        return

    # Get the problem to know the correct answer
    problem = supabase.table("qa_flaw_deck")\
        .select("flawed_step_number, status")\
        .eq("id", problem_id)\
        .execute()

    if not problem.data:
        print(f"Problem {problem_id} not found in qa_flaw_deck.")
        return

    current_status = problem.data[0]["status"]
    correct_option = problem.data[0]["flawed_step_number"] - 1  # 0-indexed for poll

    if current_status in ["caught", "missed"]:
        print(f"Problem already resolved as '{current_status}'. Skipping.")
        return

    # Get recent updates from bot
    updates = await bot.get_updates(limit=20)

    caught = None

    # Strategy 1: Check for poll answers (user tapped quiz option)
    for update in reversed(updates):
        if update.poll_answer:
            chosen = update.poll_answer.option_ids
            if len(chosen) > 0:
                caught = (chosen[0] == correct_option)
                source = f"poll answer (chose option {chosen[0]}, correct={correct_option})"
                print(f"Found {source} → {'caught' if caught else 'missed'}")
                break

    # Strategy 2: Check for text replies (overrides poll if present)
    for update in reversed(updates):
        if update.message and update.message.text:
            text = update.message.text.lower().strip()
            if text in ["caught", "got it"]:
                caught = True
                print(f"Found text reply: '{text}' → caught (overrides poll)")
                break
            elif text in ["missed", "nope"]:
                caught = False
                print(f"Found text reply: '{text}' → missed (overrides poll)")
                break

    if caught is None:
        print("No poll answer or text reply found. Nothing to update.")
        return

    new_status = "caught" if caught else "missed"

    # Update qa_flaw_deck
    supabase.table("qa_flaw_deck")\
        .update({"status": new_status})\
        .eq("id", problem_id)\
        .execute()
    print(f"Updated qa_flaw_deck: problem {problem_id[:8]}... → status='{new_status}'")

    # Update daily_log
    supabase.table("daily_log")\
        .update({"caught": caught})\
        .eq("problem_id", problem_id)\
        .execute()
    print(f"Updated daily_log: problem {problem_id[:8]}... → caught={caught}")

    # Send confirmation to user
    emoji = "✅" if caught else "❌"
    await bot.send_message(
        chat_id=chat_id,
        text=f"{emoji} Recorded as *{'CAUGHT' if caught else 'MISSED'}*.",
        parse_mode="Markdown"
    )
    print(f"Sent confirmation to Telegram.")

asyncio.run(handle())
