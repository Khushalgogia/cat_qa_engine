import os
import json
import asyncio
import random
from datetime import datetime, timedelta
from collections import Counter
from supabase import create_client
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"].strip(), os.environ["SUPABASE_KEY"].strip())
bot = Bot(token=os.environ["TELEGRAM_TOKEN"].strip())
chat_id = os.environ["TELEGRAM_CHAT_ID"].strip()

# Error category → sprint category mapping
CATEGORY_MAP = {
    "Algebraic Sign Error": "square",
    "Ignoring Negative Root": "square",
    "Integer Constraint Missed": "prime",
    "Ratio Misapplied": "reciprocal",
    "Calculation Shortcut Trap": "table",
    "Proportionality Assumed Equal": "reciprocal",
    "Misread Constraint": "prime",
    "At-Least vs Exactly Confusion": "prime",
    "Division by Variable Without Checking Zero": "reciprocal",
    # New categories map to themselves
    "pct_to_fraction": "pct_to_fraction",
    "approx_root": "approx_root",
    "fraction_compare": "fraction_compare",
    "successive_pct": "successive_pct"
}

def escape_md(text):
    """Escape Markdown special characters for Telegram MarkdownV2."""
    for ch in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        text = text.replace(ch, f'\\{ch}')
    return text

def get_yesterday_miss():
    """Check if yesterday's 2 PM flaw problem was missed.
    If so, return the mapped sprint category for guaranteed inclusion."""
    problem_result = supabase.table("settings")\
        .select("value")\
        .eq("key", "todays_problem_id")\
        .execute()

    problem_id = problem_result.data[0]["value"] if problem_result.data and problem_result.data[0]["value"] else None
    if not problem_id:
        return None

    log = supabase.table("daily_log")\
        .select("caught, problem_id, qa_flaw_deck(error_category)")\
        .eq("problem_id", problem_id)\
        .execute()

    if not log.data or log.data[0]["caught"] is not False:
        return None  # Not missed, or not yet resolved

    error_cat = log.data[0].get("qa_flaw_deck", {}).get("error_category", "")
    sprint_cat = CATEGORY_MAP.get(error_cat)
    if sprint_cat:
        print(f"Yesterday's miss: {error_cat} → sprint category: {sprint_cat}")
    return sprint_cat

def get_weak_categories():
    """Read all missed Spot the Flaw errors and find weakest categories."""
    logs = supabase.table("daily_log")\
        .select("*, qa_flaw_deck(error_category)")\
        .eq("caught", False)\
        .execute()

    if not logs.data:
        return []

    sprint_cats = []
    for log in logs.data:
        if log.get("qa_flaw_deck"):
            error_cat = log["qa_flaw_deck"].get("error_category", "")
            sprint_cat = CATEGORY_MAP.get(error_cat)
            if sprint_cat:
                sprint_cats.append(sprint_cat)

    if not sprint_cats:
        return []

    return [cat for cat, _ in Counter(sprint_cats).most_common(2)]

def select_questions(weak_categories, yesterday_miss_cat):
    """Select 7 questions with yesterday-miss guarantee + weak spot weighting."""
    questions = []
    existing_ids = []

    # Priority 1: If yesterday was missed, guarantee 2 from that category
    if yesterday_miss_cat:
        result = supabase.table("math_sprints")\
            .select("*")\
            .eq("category", yesterday_miss_cat)\
            .order("times_attempted")\
            .limit(10)\
            .execute()
        if result.data:
            pool = random.sample(result.data, min(2, len(result.data)))
            questions.extend(pool)
            existing_ids = [q["id"] for q in questions]

    # Priority 2: Fill from weak categories (if any slots left)
    if len(questions) < 3 and weak_categories:
        for cat in weak_categories[:2]:
            if len(questions) >= 3:
                break
            result = supabase.table("math_sprints")\
                .select("*")\
                .eq("category", cat)\
                .order("times_attempted")\
                .limit(10)\
                .execute()
            if result.data:
                pool = [q for q in result.data if q["id"] not in existing_ids]
                if pool:
                    questions.append(random.choice(pool))
                    existing_ids.append(questions[-1]["id"])

    # Priority 3: Fill to 7 with random least-attempted questions
    needed = 7 - len(questions)
    all_available = supabase.table("math_sprints")\
        .select("*")\
        .order("times_attempted")\
        .limit(50)\
        .execute()

    if all_available.data:
        pool = [q for q in all_available.data if q["id"] not in existing_ids]
        random.shuffle(pool)
        questions.extend(pool[:needed])

    random.shuffle(questions)
    return questions[:7]

async def deliver():
    yesterday_miss = get_yesterday_miss()
    weak_cats = get_weak_categories()
    questions = select_questions(weak_cats, yesterday_miss)

    if not questions:
        await bot.send_message(
            chat_id=chat_id,
            text="⚠️ Math sprint: question bank is empty. Run generate_questions.py."
        )
        print("No questions available.")
        return

    first_q = questions[0]
    options = first_q["options"]

    # Create session
    session_result = supabase.table("sprint_sessions").insert({
        "chat_id": chat_id,
        "message_id": 0,
        "question_queue": [q["id"] for q in questions],
        "current_index": 0,
        "original_count": len(questions),
        "debt_count": 0,
        "completed": False
    }).execute()

    session_id = session_result.data[0]["id"]

    buttons = [
        InlineKeyboardButton(opt, callback_data=f"sp|{session_id}|{i}")
        for i, opt in enumerate(options)
    ]
    keyboard = InlineKeyboardMarkup([buttons[:2], buttons[2:]])

    # Build message
    weak_note = ""
    if yesterday_miss:
        weak_note = f"_Yesterday's miss \\→ drilling {escape_md(yesterday_miss)} today_\n\n"
    elif weak_cats:
        cats_text = escape_md(', '.join(weak_cats))
        weak_note = f"_Targeting weak spots: {cats_text}_\n\n"

    q_text = escape_md(first_q['question_text'])
    text = f"⚡ *MATH SPRINT* \\[1/{len(questions)}\\]\n\n{weak_note}{q_text}"

    try:
        message = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )
    except Exception:
        text_plain = f"⚡ MATH SPRINT [1/{len(questions)}]\n\n{first_q['question_text']}"
        message = await bot.send_message(
            chat_id=chat_id,
            text=text_plain,
            reply_markup=keyboard
        )

    supabase.table("sprint_sessions")\
        .update({"message_id": message.message_id})\
        .eq("id", session_id)\
        .execute()

    # ── Session cleanup: delete sessions older than 7 days ──
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()

    # First find old session IDs
    old_sessions = supabase.table("sprint_sessions")\
        .select("id")\
        .lt("created_at", cutoff)\
        .execute()

    if old_sessions.data:
        old_ids = [s["id"] for s in old_sessions.data]
        # Delete child sprint_logs first (FK constraint)
        for sid in old_ids:
            supabase.table("sprint_logs")\
                .delete()\
                .eq("session_id", sid)\
                .execute()
        # Then delete the sessions
        supabase.table("sprint_sessions")\
            .delete()\
            .lt("created_at", cutoff)\
            .execute()

    print(f"Sprint delivered. Session: {session_id}")
    print(f"Questions: {len(questions)} ({', '.join(q['category'] for q in questions)})")
    if yesterday_miss:
        print(f"Yesterday's miss guaranteed: {yesterday_miss}")
    elif weak_cats:
        print(f"Weak categories targeted: {', '.join(weak_cats)}")

asyncio.run(deliver())
