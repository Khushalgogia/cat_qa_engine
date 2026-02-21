import os
import sys
import asyncio
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

# ─── IMPORTANT: Set your Edge Function URL here ───
# Replace 'your-project-ref' with the part of your Supabase URL
# between https:// and .supabase.co
# Example: if your URL is https://abcdefgh.supabase.co
#          then your ref is 'abcdefgh'

EDGE_FUNCTION_URL = os.environ.get(
    "SPRINT_WEBHOOK_URL",
    "https://ucbudwmxzdyzqxjwpyti.supabase.co/functions/v1/sprint-webhook"
)

async def register():
    bot = Bot(token=os.environ["TELEGRAM_TOKEN"].strip())
    
    if "your-project-ref" in EDGE_FUNCTION_URL:
        print("❌ ERROR: You need to set your Edge Function URL first!")
        print("   Edit EDGE_FUNCTION_URL in this file, or set SPRINT_WEBHOOK_URL env var.")
        print("   Format: https://YOUR-PROJECT-REF.supabase.co/functions/v1/sprint-webhook")
        sys.exit(1)
    
    print(f"Registering webhook: {EDGE_FUNCTION_URL}")
    print("Setting allowed_updates to ['callback_query', 'poll_answer']...")
    print("(All interactive events now go to the Edge Function.)\n")
    
    result = await bot.set_webhook(
        url=EDGE_FUNCTION_URL,
        allowed_updates=["callback_query", "poll_answer"]
    )
    
    if result:
        print("✅ Webhook registered successfully!")
        print(f"   URL: {EDGE_FUNCTION_URL}")
        print("   Telegram will send callback_query + poll_answer events to this webhook.")
        print("   Sprint buttons, graveyard buttons, and quiz answers all handled in real-time.")
    else:
        print("❌ Webhook registration failed. Check your Edge Function URL.")
    
    info = await bot.get_webhook_info()
    print(f"\nWebhook info:")
    print(f"  URL: {info.url}")
    print(f"  Pending updates: {info.pending_update_count}")
    print(f"  Allowed updates: {info.allowed_updates}")
    if info.last_error_message:
        print(f"  Last error: {info.last_error_message}")

asyncio.run(register())
