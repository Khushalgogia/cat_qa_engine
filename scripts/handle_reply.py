import os
import time
import asyncio
from supabase import create_client
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
bot = Bot(token=os.environ["TELEGRAM_TOKEN"])
chat_id = os.environ["TELEGRAM_CHAT_ID"]

# Edge Function URL for webhook restore
WEBHOOK_URL = os.environ.get(
    "SPRINT_WEBHOOK_URL",
    "https://ucbudwmxzdyzqxjwpyti.supabase.co/functions/v1/sprint-webhook"
)

async def handle():
    # ── Step 1: Check for graveyard reply first ────────────
    graveyard_result = supabase.table("settings")\
        .select("value")\
        .eq("key", "graveyard_pending_id")\
        .execute()

    graveyard_id = graveyard_result.data[0]["value"] if graveyard_result.data and graveyard_result.data[0]["value"] else None

    # ── Step 2: Get today's flaw problem id ────────────────
    problem_result = supabase.table("settings")\
        .select("value")\
        .eq("key", "todays_problem_id")\
        .execute()

    problem_id = problem_result.data[0]["value"] if problem_result.data and problem_result.data[0]["value"] else None

    # ── Step 3: Temporarily remove webhook to use getUpdates ──
    await bot.delete_webhook()
    updates = await bot.get_updates(limit=20)

    # Detect text replies
    text_reply = None
    for update in reversed(updates):
        if update.message and update.message.text:
            text = update.message.text.lower().strip()
            if text in ["caught", "got it"]:
                text_reply = "caught"
                break
            elif text in ["missed", "nope"]:
                text_reply = "missed"
                break

    # ── Step 4: Handle graveyard reply ("got it"/"nope") ───
    if graveyard_id and text_reply:
        if text_reply in ["caught"]:  # "got it" maps to "caught" keyword
            supabase.table("qa_flaw_deck")\
                .update({"status": "reviewed"})\
                .eq("id", graveyard_id)\
                .execute()
            await bot.send_message(
                chat_id=chat_id,
                text="✅ Graveyard cleared. That trap won't catch you again.",
                parse_mode="Markdown"
            )
            print(f"Graveyard problem {graveyard_id[:8]}... → reviewed")
        else:  # "nope" — leave as missed, it'll come back
            await bot.send_message(
                chat_id=chat_id,
                text="📌 Still foggy — this one stays in the graveyard. It'll come back.",
                parse_mode="Markdown"
            )
            print(f"Graveyard problem {graveyard_id[:8]}... → stays missed")

        # Clear graveyard pending
        supabase.table("settings")\
            .update({"value": ""})\
            .eq("key", "graveyard_pending_id")\
            .execute()
        return  # Done — don't also process flaw reply in same run

    # ── Step 5: Handle flaw problem reply ──────────────────
    if not problem_id:
        print("No problem ID in settings. Nothing to do.")
        return

    problem = supabase.table("qa_flaw_deck")\
        .select("flawed_step_number, status")\
        .eq("id", problem_id)\
        .execute()

    if not problem.data:
        print(f"Problem {problem_id} not found.")
        return

    current_status = problem.data[0]["status"]
    correct_option = problem.data[0]["flawed_step_number"] - 1

    if current_status in ["caught", "missed"]:
        print(f"Problem already resolved as '{current_status}'. Skipping.")
        return

    caught = None
    eight_hours_ago = int(time.time()) - (8 * 3600)

    # Check poll answer (only from last 8 hours to prevent stale cross-day answers)
    for update in reversed(updates):
        if update.poll_answer:
            chosen = update.poll_answer.option_ids
            if len(chosen) > 0:
                caught = (chosen[0] == correct_option)
                print(f"Found poll answer (chose {chosen[0]}, correct={correct_option}) → {'caught' if caught else 'missed'}")
                break

    # Text reply overrides poll
    if text_reply == "caught":
        caught = True
        print("Found text reply: 'caught' → caught")
    elif text_reply == "missed":
        caught = False
        print("Found text reply: 'missed' → missed")

    # ── Step 6: If no reply found, send reminder ───────────
    if caught is None:
        await bot.send_message(
            chat_id=chat_id,
            text="⏰ *Reminder:* Did you spot the flaw in today's problem?\n\nReply *caught* or *missed*.",
            parse_mode="Markdown"
        )
        print("No reply found. Sent reminder.")
        return

    new_status = "caught" if caught else "missed"

    supabase.table("qa_flaw_deck")\
        .update({"status": new_status})\
        .eq("id", problem_id)\
        .execute()
    print(f"Updated qa_flaw_deck: {problem_id[:8]}... → '{new_status}'")

    supabase.table("daily_log")\
        .update({"caught": caught})\
        .eq("problem_id", problem_id)\
        .execute()
    print(f"Updated daily_log: {problem_id[:8]}... → caught={caught}")

    emoji = "✅" if caught else "❌"
    await bot.send_message(
        chat_id=chat_id,
        text=f"{emoji} Recorded as *{'CAUGHT' if caught else 'MISSED'}*.",
        parse_mode="Markdown"
    )
    print("Sent confirmation.")

async def main():
    try:
        await handle()
    finally:
        # Always restore the webhook, even if handle() returns early or errors
        await bot.set_webhook(url=WEBHOOK_URL, allowed_updates=["callback_query"])
        print("Webhook restored.")

asyncio.run(main())
