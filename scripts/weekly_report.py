import os
import asyncio
from supabase import create_client
from telegram import Bot
from collections import Counter
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
bot = Bot(token=os.environ["TELEGRAM_TOKEN"])
chat_id = os.environ["TELEGRAM_CHAT_ID"]

async def report():
    logs = supabase.table("daily_log")\
        .select("*, qa_flaw_deck(error_category)")\
        .not_.is_("caught", "null")\
        .neq("is_revision", True)\
        .execute()

    if not logs.data:
        await bot.send_message(chat_id=chat_id, text="No data yet for weekly report.")
        return

    total = len(logs.data)
    caught_logs = [l for l in logs.data if l["caught"]]
    missed_logs = [l for l in logs.data if not l["caught"]]

    missed_cats = Counter(l["qa_flaw_deck"]["error_category"] for l in missed_logs)
    caught_cats = Counter(l["qa_flaw_deck"]["error_category"] for l in caught_logs)

    msg = f"📊 *WEEKLY ERROR FINGERPRINT*\n\n"
    msg += f"Attempted: {total} | Caught: {len(caught_logs)} ✅ | Missed: {len(missed_logs)} ❌\n\n"

    if missed_cats:
        msg += "*Your Blind Spots:*\n"
        for cat, count in missed_cats.most_common():
            msg += f"  • {cat}: missed {count}x\n"

    if caught_cats:
        msg += "\n*Your Strengths:*\n"
        for cat, count in caught_cats.most_common(3):
            msg += f"  • {cat}: caught {count}x\n"

    if missed_cats:
        worst = missed_cats.most_common(1)[0][0]
        msg += f"\n🎯 *Fix this week:* {worst}"

    # ── Sprint stats ──────────────────────────────────────
    try:
        sprint_logs = supabase.table("sprint_logs")\
            .select("*")\
            .execute()

        if sprint_logs.data:
            sprint_total = len(sprint_logs.data)
            sprint_correct = sum(1 for l in sprint_logs.data if l["is_correct"])
            sprint_debt = sum(1 for l in sprint_logs.data if l["is_debt_attempt"])

            wrong_cats = Counter(
                l["category"] for l in sprint_logs.data if not l["is_correct"]
            )

            msg += f"\n\n⚡ *SPRINT STATS (this week)*\n"
            msg += f"Answers: {sprint_total} | Correct: {sprint_correct} | "
            msg += f"Debt repaid: {sprint_debt}\n"

            if wrong_cats:
                msg += f"Slowest category: *{wrong_cats.most_common(1)[0][0]}*"
    except Exception:
        pass  # Sprint tables may not exist yet

    await bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

asyncio.run(report())
