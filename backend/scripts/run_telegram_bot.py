"""Telegram Bot Runner for CortexCX.

Supports:
1. Long-polling mode for local development and immediate testing.
2. Webhook setup helper for production deployments.

Usage:
    # Run long-polling locally:
    python scripts/run_telegram_bot.py

    # Set webhook for production:
    python scripts/run_telegram_bot.py --set-webhook https://api.yourdomain.com/channels/telegram/webhook?workspace_id=<UUID>

    # Delete webhook:
    python scripts/run_telegram_bot.py --delete-webhook
"""

import argparse
import sys
import time
from uuid import UUID
import httpx

# Ensure console supports utf-8 and unbuffered output
import os
os.environ["PYTHONUNBUFFERED"] = "1"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

# Ensure app is on pythonpath
sys.path.insert(0, ".")

import app.database.models
from app.core.config import settings
from app.database.database import SessionLocal
from app.workspace.model import Workspace
from app.channels.telegram_adapter import TelegramAdapter


def get_default_workspace_id() -> UUID:
    """Workspace the bot serves: TELEGRAM_WORKSPACE_ID from .env (if present in DB), else the first active workspace."""
    db = SessionLocal()
    try:
        if settings.TELEGRAM_WORKSPACE_ID:
            try:
                target_id = UUID(settings.TELEGRAM_WORKSPACE_ID)
                ws = db.query(Workspace).filter(Workspace.id == target_id).first()
                if ws:
                    return ws.id
                print(f"WARNING: TELEGRAM_WORKSPACE_ID={settings.TELEGRAM_WORKSPACE_ID} not found in DB; falling back to active workspace.")
            except ValueError:
                print(f"WARNING: Invalid TELEGRAM_WORKSPACE_ID={settings.TELEGRAM_WORKSPACE_ID}; falling back to active workspace.")

        workspaces = db.query(Workspace).filter(Workspace.is_active.is_(True)).order_by(Workspace.created_at).all()
        if not workspaces:
            raise RuntimeError("No active Workspace found in database. Please run migrations or create a workspace first.")
        return workspaces[0].id
    finally:
        db.close()


def set_webhook(url: str, secret_token: str | None = None) -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN is not configured in .env")
        sys.exit(1)

    api_url = f"https://api.telegram.org/bot{token}/setWebhook"
    payload = {"url": url}
    if secret_token or settings.TELEGRAM_WEBHOOK_SECRET:
        payload["secret_token"] = secret_token or settings.TELEGRAM_WEBHOOK_SECRET

    resp = httpx.post(api_url, json=payload, timeout=10.0)
    data = resp.json()
    if data.get("ok"):
        print(f"SUCCESS: Webhook set to: {url}")
    else:
        print(f"FAILED to set webhook: {data}")


def delete_webhook() -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN is not configured in .env")
        sys.exit(1)

    api_url = f"https://api.telegram.org/bot{token}/deleteWebhook"
    resp = httpx.post(api_url, timeout=10.0)
    data = resp.json()
    if data.get("ok"):
        print("SUCCESS: Webhook removed. Bot is now ready for long-polling.")
    else:
        print(f"FAILED to delete webhook: {data}")


def run_polling(workspace_id: UUID) -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN is not configured in .env")
        sys.exit(1)

    # 1. Ensure webhook is cleared before starting long polling
    httpx.post(f"https://api.telegram.org/bot{token}/deleteWebhook", timeout=10.0)

    # 2. Verify bot identity
    me_resp = httpx.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10.0)
    me_data = me_resp.json().get("result", {})
    bot_name = me_data.get("first_name", "CortexCX")
    bot_username = me_data.get("username", "CortexCX_bot")

    print("=" * 60)
    print(f"🤖 CortexCX Telegram Bot is ONLINE: @{bot_username} ({bot_name})")
    print(f"🏢 Bound Workspace ID: {workspace_id}")
    print(f"💬 You can open Telegram and message: https://t.me/{bot_username}")
    print("Listening for incoming updates... (Press Ctrl+C to stop)")
    print("=" * 60)

    offset = 0
    adapter = TelegramAdapter()

    while True:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}&timeout=20"
            resp = httpx.get(url, timeout=30.0)
            if resp.status_code == 401:
                print("Telegram rejected the bot token (401 Unauthorized). It was revoked or changed in BotFather.")
                print("Copy the current token from @BotFather (/mybots -> your bot -> API Token), put it in")
                print("backend/.env as TELEGRAM_BOT_TOKEN, then start this script again.")
                sys.exit(1)
            if resp.status_code != 200:
                print(f"Telegram API warning (HTTP {resp.status_code}): {resp.text}")
                time.sleep(2)
                continue

            data = resp.json()
            updates = data.get("result", [])

            for update in updates:
                update_id = update.get("update_id", 0)
                offset = max(offset, update_id + 1)

                incoming = adapter.parse_webhook_payload(update)
                if not incoming:
                    continue

                print(f"\n📩 [{incoming.customer_name}]: {incoming.content}")

                db = SessionLocal()
                try:
                    response = adapter.handle_incoming_message(
                        db=db,
                        workspace_id=workspace_id,
                        incoming=incoming,
                    )
                    print(f"🤖 [CortexCX]: {response.content} (state={response.ai_state}, conf={response.confidence_score:.2f})")
                except Exception as e:
                    print(f"❌ Error processing message: {str(e)}")
                finally:
                    db.close()

        except httpx.TimeoutException:
            continue
        except KeyboardInterrupt:
            print("\nShutting down Telegram bot listener...")
            break
        except Exception as e:
            print(f"Polling exception: {str(e)}")
            time.sleep(3)


def main():
    parser = argparse.ArgumentParser(description="CortexCX Telegram Bot Utility")
    parser.add_argument("--workspace-id", type=str, default=None, help="Workspace UUID to bind bot conversations to")
    parser.add_argument("--set-webhook", type=str, default=None, help="Set Telegram webhook URL for production")
    parser.add_argument("--delete-webhook", action="store_true", help="Delete Telegram webhook for local polling")

    args = parser.parse_args()

    if args.set_webhook:
        set_webhook(args.set_webhook)
        return

    if args.delete_webhook:
        delete_webhook()
        return

    workspace_id = UUID(args.workspace_id) if args.workspace_id else get_default_workspace_id()
    run_polling(workspace_id)


if __name__ == "__main__":
    main()
