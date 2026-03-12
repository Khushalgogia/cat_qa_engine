import argparse
import asyncio
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from supabase import create_client
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

load_dotenv()

IST = ZoneInfo("Asia/Kolkata")

supabase = create_client(os.environ["SUPABASE_URL"].strip(), os.environ["SUPABASE_KEY"].strip())
bot = Bot(token=os.environ["TELEGRAM_TOKEN"].strip())
chat_id = os.environ["TELEGRAM_CHAT_ID"].strip()

FLAW_BUTTON_KEY = "flaw_persistent_button_v1"
FLAW_SESSION_KEY = "flaw_session_v1"


def iso_now() -> str:
    return datetime.now(IST).isoformat()


def get_setting(key: str) -> str | None:
    result = supabase.table("settings").select("value").eq("key", key).execute()
    if not result.data:
        return None
    return result.data[0].get("value")


def get_json_setting(key: str, default):
    raw = get_setting(key)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def upsert_setting(key: str, value: str) -> None:
    supabase.table("settings").upsert({"key": key, "value": value}).execute()


def upsert_json_setting(key: str, value) -> None:
    upsert_setting(key, json.dumps(value, separators=(",", ":")))


def clear_active_session() -> None:
    upsert_json_setting(FLAW_SESSION_KEY, None)


def start_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("▶️ Start Spot the Flaw", callback_data="flw|open"),
    ]])


async def post_button() -> None:
    existing = get_json_setting(FLAW_BUTTON_KEY, None)
    if existing and existing.get("message_id"):
        try:
            await bot.delete_message(chat_id=existing.get("chat_id", chat_id), message_id=existing["message_id"])
        except Exception as exc:
            print(f"[WARN] Could not delete old Spot the Flaw button: {exc}")

    clear_active_session()

    text = (
        "🔍 *SPOT THE FLAW*\n\n"
        "Tap below to choose how many questions you want today."
    )
    message = await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=start_keyboard(),
    )
    upsert_json_setting(FLAW_BUTTON_KEY, {
        "message_id": message.message_id,
        "chat_id": str(message.chat.id),
        "posted_at": iso_now(),
    })
    print(f"Spot the Flaw button posted: {message.message_id}")


async def cleanup_button() -> None:
    existing = get_json_setting(FLAW_BUTTON_KEY, None)
    if existing and existing.get("message_id"):
        try:
            await bot.delete_message(chat_id=existing.get("chat_id", chat_id), message_id=existing["message_id"])
        except Exception as exc:
            print(f"[WARN] Could not delete Spot the Flaw button: {exc}")
    upsert_json_setting(FLAW_BUTTON_KEY, None)
    clear_active_session()
    print("Spot the Flaw button cleaned up.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Spot the Flaw persistent button manager.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("post")
    sub.add_parser("cleanup")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    if args.command == "post":
        await post_button()
    elif args.command == "cleanup":
        await cleanup_button()
    else:
        raise RuntimeError(f"Unsupported command: {args.command}")


asyncio.run(main())
