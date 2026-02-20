import os
import json
import asyncio
import random
from collections import Counter
from supabase import create_client
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
bot = Bot(token=os.environ["TELEGRAM_TOKEN"])
chat_id = os.environ["TELEGRAM_CHAT_ID"]

def get_weak_categories():
    """Read Spot the Flaw errors and find weakest category."""
    logs = supabase.table("daily_log")\
        .select("*, qa_flaw_deck(error_category)")\
        .eq("caught", False)\
        .execute()
    
    if not logs.data:
        return []
    
    category_to_sprint = {
        "Algebraic Sign Error": "square",
        "Ignoring Negative Root": "square",
        "Integer Constraint Missed": "prime",
        "Ratio Misapplied": "reciprocal",
        "Calculation Shortcut Trap": "table",
        "Proportionality Assumed Equal": "reciprocal",
        "Misread Constraint": "prime"
    }
    
    sprint_cats = []
    for log in logs.data:
        if log.get("qa_flaw_deck"):
            error_cat = log["qa_flaw_deck"].get("error_category", "")
            sprint_cat = category_to_sprint.get(error_cat)
            if sprint_cat:
                sprint_cats.append(sprint_cat)
    
    if not sprint_cats:
        return []
    
    return [cat for cat, _ in Counter(sprint_cats).most_common(2)]

def select_questions(weak_categories):
    """Select 5 interleaved questions: 2 from weak spots + 3 random new."""
    questions = []
    
    # 2 from weak categories (if available)
    if weak_categories:
        for cat in weak_categories[:2]:
            result = supabase.table("math_sprints")\
                .select("*")\
                .eq("category", cat)\
                .order("times_attempted")\
                .limit(10)\
                .execute()
            if result.data:
                questions.append(random.choice(result.data))
    
    # Fill up to 5 with random questions from any category
    needed = 5 - len(questions)
    existing_ids = [q["id"] for q in questions]
    
    # Query all available, excluding already picked
    all_available = supabase.table("math_sprints")\
        .select("*")\
        .order("times_attempted")\
        .limit(50)\
        .execute()
    
    if all_available.data:
        pool = [q for q in all_available.data if q["id"] not in existing_ids]
        random.shuffle(pool)
        questions.extend(pool[:needed])
    
    # Shuffle the final 5 so weak-category questions aren't always first
    random.shuffle(questions)
    return questions[:5]

async def deliver():
    weak_cats = get_weak_categories()
    questions = select_questions(weak_cats)
    
    if not questions:
        await bot.send_message(
            chat_id=chat_id,
            text="⚠️ Math sprint: question bank is empty. Run generate_questions.py."
        )
        print("No questions available.")
        return
    
    first_q = questions[0]
    options = first_q["options"]
    
    # Create session with question queue
    session_result = supabase.table("sprint_sessions").insert({
        "chat_id": chat_id,
        "message_id": 0,  # placeholder, updated after send
        "question_queue": [q["id"] for q in questions],
        "current_index": 0,
        "original_count": len(questions),
        "debt_count": 0,
        "completed": False
    }).execute()
    
    session_id = session_result.data[0]["id"]
    
    # Build inline keyboard (2x2 grid)
    buttons = [
        InlineKeyboardButton(opt, callback_data=f"sp|{session_id}|{i}")
        for i, opt in enumerate(options)
    ]
    keyboard = InlineKeyboardMarkup([buttons[:2], buttons[2:]])
    
    # Weak category note
    weak_note = ""
    if weak_cats:
        weak_note = f"_Targeting your weak spots: {', '.join(weak_cats)}_\n\n"
    
    text = f"⚡ *MATH SPRINT* [1/{len(questions)}]\n\n{weak_note}{first_q['question_text']}"
    
    message = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    
    # Update session with real message_id so edge function can edit it
    supabase.table("sprint_sessions")\
        .update({"message_id": message.message_id})\
        .eq("id", session_id)\
        .execute()
    
    print(f"Sprint delivered. Session: {session_id}")
    print(f"Questions: {len(questions)} ({', '.join(q['category'] for q in questions)})")
    if weak_cats:
        print(f"Weak categories targeted: {', '.join(weak_cats)}")

asyncio.run(deliver())
