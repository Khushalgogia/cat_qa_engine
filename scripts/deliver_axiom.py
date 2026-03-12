import os
import json
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from supabase import create_client
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

IST = ZoneInfo("Asia/Kolkata")
FLAW_DAY_STATE_KEY = "flaw_day_state_v1"

supabase = create_client(os.environ["SUPABASE_URL"].strip(), os.environ["SUPABASE_KEY"].strip())
bot = Bot(token=os.environ["TELEGRAM_TOKEN"].strip())
chat_id = os.environ["TELEGRAM_CHAT_ID"].strip()


def _today_key():
    return datetime.now(IST).date().isoformat()


def _get_day_state():
    result = supabase.table("settings")\
        .select("value")\
        .eq("key", FLAW_DAY_STATE_KEY)\
        .execute()

    if not result.data or not result.data[0].get("value"):
        return {}

    try:
        return json.loads(result.data[0]["value"])
    except json.JSONDecodeError:
        return {}

def _format_axiom(axiom_raw, framing):
    """Format the axiom as a Cognitive Anchor message.
    Handles both new JSON format and legacy plain-text strings."""

    # Try parsing as JSON (new 3-part format)
    axiom_obj = None
    if isinstance(axiom_raw, dict):
        axiom_obj = axiom_raw
    elif isinstance(axiom_raw, str):
        try:
            parsed = json.loads(axiom_raw)
            if isinstance(parsed, dict) and "core_rule" in parsed:
                axiom_obj = parsed
        except (json.JSONDecodeError, TypeError):
            pass

    if axiom_obj:
        # New Cognitive Anchor format
        core_rule = axiom_obj.get("core_rule", "")
        mental_model = axiom_obj.get("mental_model", "")
        anchor_question = axiom_obj.get("anchor_question", "")

        msg = f"🌙 *Tonight's Cognitive Anchor*\n\n{framing}"
        msg += f"📌 *The Rule:* {core_rule}\n\n"
        msg += f"💡 *Mental Model:* {mental_model}\n\n"
        msg += f"_{anchor_question}_\n\n"
        msg += "Sleep on it. 🧠"
        return msg
    else:
        # Legacy fallback — plain string axiom
        msg = f"🌙 *Tonight's Axiom*\n\n{framing}"
        msg += f"_{axiom_raw}_\n\n"
        msg += "Sleep on it."
        return msg

async def deliver_axiom():
    state = _get_day_state().get(_today_key(), {})
    problem_id = state.get("most_recent_missed_problem_id") or state.get("most_recent_answered_problem_id")
    axiom = state.get("most_recent_missed_axiom") or state.get("most_recent_answered_axiom")
    if not axiom or not problem_id:
        return

    framing = ""

    if state.get("most_recent_missed_problem_id"):
        framing = "This one caught you today. Make sure it never does again.\n\n"
    elif state.get("most_recent_answered_problem_id"):
        framing = "You spotted this trap today. Lock it in.\n\n"

    text = _format_axiom(axiom, framing)

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"  ⚠️ Markdown send failed ({e}), retrying as plain text...")
        plain_text = text.replace("*", "").replace("_", "")
        await bot.send_message(chat_id=chat_id, text=plain_text)

    print(f"Axiom delivered. Framing: {'caught' if 'spotted' in framing else 'missed' if 'caught you' in framing else 'neutral'}")

asyncio.run(deliver_axiom())
