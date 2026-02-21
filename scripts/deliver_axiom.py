import os
import json
import asyncio
from supabase import create_client
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"].strip(), os.environ["SUPABASE_KEY"].strip())
bot = Bot(token=os.environ["TELEGRAM_TOKEN"].strip())
chat_id = os.environ["TELEGRAM_CHAT_ID"].strip()

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
                framing = "You spotted this trap today. Lock it in.\n\n"
            else:
                framing = "This one caught you today. Make sure it never does again.\n\n"

    text = _format_axiom(axiom, framing)

    await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown"
    )
    print(f"Axiom delivered. Framing: {'caught' if 'spotted' in framing else 'missed' if 'caught you' in framing else 'neutral'}")

asyncio.run(deliver_axiom())
