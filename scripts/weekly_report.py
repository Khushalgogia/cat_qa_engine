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

    await bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

asyncio.run(report())
