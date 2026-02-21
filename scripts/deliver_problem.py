import os
import json
import asyncio
from supabase import create_client
from telegram import Bot
from google import genai
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"].strip(), os.environ["SUPABASE_KEY"].strip())
bot = Bot(token=os.environ["TELEGRAM_TOKEN"].strip())
chat_id = os.environ["TELEGRAM_CHAT_ID"].strip()

# Optional: only needed if >10-step problems exist
_genai_client = None
def _get_genai():
    global _genai_client
    if _genai_client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return None
        _genai_client = genai.Client(api_key=api_key)
    return _genai_client

def _try_condense(steps, flaw_step_number):
    """Attempt to condense >10 steps to ≤10. Returns dict or None on failure."""
    client = _get_genai()
    if not client:
        print("  GEMINI_API_KEY not set. Cannot auto-condense.")
        return None

    import time
    prompt = f"""You have a math solution with {len(steps)} numbered steps.
The flaw is in step {flaw_step_number}.
Condense this into EXACTLY 10 steps or fewer by merging trivially related consecutive steps.
CRITICAL: The flawed step must remain identifiable — do NOT merge it with a correct step.

Current steps:
{json.dumps(steps, indent=2)}

Return ONLY a JSON object with:
- "condensed_steps": array of max 10 steps
- "new_flaw_step_number": the 1-based index of the flawed step in the condensed version

Return only valid JSON."""

    for attempt in range(3):
        try:
            response = client.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]
            result = json.loads(text)
            if len(result.get("condensed_steps", [])) <= 10:
                return result
            return None  # LLM still returned >10
        except Exception as e:
            if "429" in str(e) or "503" in str(e):
                wait = 2 ** attempt * 10
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  Condense error: {e}")
                return None
    return None

async def deliver():
    # Fetch one unseen problem
    result = supabase.table("qa_flaw_deck")\
        .select("*")\
        .eq("status", "unseen")\
        .order("source_file")\
        .limit(1)\
        .execute()

    # Fallback: if bank is exhausted, re-deliver oldest caught problem as revision
    is_revision = False
    if not result.data:
        result = supabase.table("qa_flaw_deck")\
            .select("*")\
            .eq("status", "caught")\
            .order("delivered_at")\
            .limit(1)\
            .execute()
        is_revision = True

    if not result.data:
        await bot.send_message(
            chat_id=chat_id,
            text="⚠️ Problem bank is empty. Transcribe a new class and run process_transcript.py."
        )
        return

    problem = result.data[0]
    steps = problem["solution_steps"]

    # Safety: Telegram polls max 10 options — auto-condense if needed
    if len(steps) > 10:
        print(f"Problem {problem['id'][:8]}... has {len(steps)} steps (max 10). Attempting auto-condense...")
        condensed = _try_condense(steps, problem["flawed_step_number"])
        if condensed:
            steps = condensed["condensed_steps"]
            problem["flawed_step_number"] = condensed["new_flaw_step_number"]
            # Persist the condensed version so we don't re-condense next time
            supabase.table("qa_flaw_deck").update({
                "solution_steps": steps,
                "flawed_step_number": problem["flawed_step_number"]
            }).eq("id", problem["id"]).execute()
            print(f"  Auto-condensed to {len(steps)} steps.")
        else:
            # Condensing failed — skip this problem
            print(f"  Auto-condense failed. Skipping.")
            supabase.table("qa_flaw_deck")\
                .update({"status": "skip_overlimit"})\
                .eq("id", problem["id"])\
                .execute()
            # Retry with next problem
            result = supabase.table("qa_flaw_deck")\
                .select("*")\
                .eq("status", "unseen")\
                .order("source_file")\
                .limit(1)\
                .execute()
            if not result.data:
                await bot.send_message(chat_id=chat_id, text="⚠️ No deliverable problems. Run process_transcript.py.")
                return
            problem = result.data[0]
            steps = problem["solution_steps"]

    # Header: revision round or normal
    if is_revision:
        header = "📚 *REVISION ROUND*\n\nYou caught this before. Still remember why the flaw was where it was?\n\n"
    else:
        header = "🔍 *SPOT THE FLAW — 12 PM*\n\n"

    # ── Telegram API Limits (from telegram.constants) ──
    # Message text: ≤ 4096 chars
    # Poll question: ≤ 300 chars
    # Poll option:   ≤ 100 chars each
    # Poll options:  ≤ 10 total
    # Explanation:   ≤ 200 chars, max 2 newlines
    # ──────────────────────────────────────────────────

    # Build the message with full steps + full explanation (no detail lost)
    formatted_steps = "\n".join([f"Step {i+1}: {s}" for i, s in enumerate(steps)])
    full_explanation = f"Trap: {problem['error_category']}\n{problem['explanation']}"
    full_message = (
        f"{header}*Problem:*\n{problem['original_problem']}\n\n"
        f"*Steps:*\n{formatted_steps}\n\n"
        f"*Explanation:*\n{full_explanation}"
    )

    # Send message (split if > 4096 chars)
    if len(full_message) <= 4096:
        await bot.send_message(chat_id=chat_id, text=full_message, parse_mode="Markdown")
    else:
        # First chunk: header + problem
        msg1 = f"{header}*Problem:*\n{problem['original_problem']}"
        await bot.send_message(chat_id=chat_id, text=msg1[:4096], parse_mode="Markdown")
        # Second chunk: steps + explanation
        msg2 = f"*Steps:*\n{formatted_steps}\n\n*Explanation:*\n{full_explanation}"
        while msg2:
            await bot.send_message(chat_id=chat_id, text=msg2[:4096], parse_mode="Markdown")
            msg2 = msg2[4096:]

    # Build poll options: "Step X: [preview...]" — each guaranteed ≤ 100 chars
    poll_options = []
    for i, s in enumerate(steps):
        prefix = f"Step {i+1}: "
        max_preview = 100 - len(prefix) - 3  # -3 for "..."
        if len(prefix) + len(s) > 100:
            poll_options.append(f"{prefix}{s[:max_preview]}...")
        else:
            poll_options.append(f"{prefix}{s}")

    # Build explanation: must be ≤ 200 chars with max 2 newlines
    poll_explanation = f"Trap: {problem['error_category']}"
    if len(poll_explanation) < 197:
        remaining = 200 - len(poll_explanation) - 3  # -3 for "\n\n" prefix + safety
        expl_text = problem['explanation'][:remaining]
        poll_explanation = f"{poll_explanation}\n\n{expl_text}"
    # Final safety cap
    poll_explanation = poll_explanation[:200]

    await bot.send_poll(
        chat_id=chat_id,
        question="Which step contains the logical flaw?"[:300],
        options=poll_options,
        type="quiz",
        correct_option_id=problem["flawed_step_number"] - 1,
        explanation=poll_explanation,
        is_anonymous=False
    )

    # Update settings
    supabase.table("settings")\
        .update({"value": problem["trap_axiom"]})\
        .eq("key", "todays_axiom")\
        .execute()

    supabase.table("settings")\
        .update({"value": problem["id"]})\
        .eq("key", "todays_problem_id")\
        .execute()

    # Mark as delivered (revision stays 'caught' but gets re-delivered)
    if not is_revision:
        supabase.table("qa_flaw_deck")\
            .update({"delivered_at": "now()", "status": "delivered"})\
            .eq("id", problem["id"])\
            .execute()

    supabase.table("daily_log").insert({
        "problem_id": problem["id"],
        "is_revision": is_revision
    }).execute()

    print(f"{'Revision' if is_revision else 'New'} problem delivered: {problem['id'][:8]}...")

asyncio.run(deliver())
