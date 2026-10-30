
import asyncio
import logging
import os
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv

from vision import analyze_screenshot
from memory import init_db, save_analysis, get_similar_count


# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID", "").strip()
CONTACT = os.getenv("CONTACT", "@Masktrader6T9")
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.82"))
MIN_SIMILAR = int(os.getenv("MIN_SIMILAR", "3"))

RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("quotex-bot")


# Check required settings
if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN Render Environment-এ সেট করো")

if not RENDER_EXTERNAL_URL:
    raise RuntimeError("RENDER_EXTERNAL_URL পাওয়া যায়নি")

if not WEBHOOK_SECRET:
    raise RuntimeError("WEBHOOK_SECRET Render Environment-এ সেট করো")


def allowed(update: Update) -> bool:
    user = update.effective_user

    if not user:
        return False

    return (
        not ADMIN_USER_ID
        or str(user.id) == ADMIN_USER_ID
    )


# Telegram commands
async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not allowed(update):
        return

    await update.message.reply_text(
        "QUOTEX AI ANALYSIS BOT চালু আছে।\n\n"
        "একটি পরিষ্কার Quotex chart screenshot পাঠাও।\n\n"
        "/id - তোমার Telegram user ID\n"
        "/help - নির্দেশনা"
    )


async def help_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not allowed(update):
        return

    await update.message.reply_text(
        "ব্যবহার:\n\n"
        "১) 1-minute chart screenshot পাঠাও।\n"
        "২) Pair ও timeframe দৃশ্যমান রাখো।\n"
        "৩) যত বেশি আগের candle দেখা যায় তত ভালো।\n\n"
        "দুর্বল বা অস্পষ্ট setup হলে Bot signal দেবে না।"
    )


async def id_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_user:
        await update.message.reply_text(
            f"Your Telegram user ID: "
            f"{update.effective_user.id}"
        )


# Screenshot analysis
async def photo_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not allowed(update):
        return

    msg = update.message

    if not msg or not msg.photo:
        return

    status = await msg.reply_text(
        "Screenshot পেয়েছি। Chart বিশ্লেষণ করছি..."
    )

    try:
        photo = msg.photo[-1]
        telegram_file = await context.bot.get_file(
            photo.file_id
        )

        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "chart.jpg"

            await telegram_file.download_to_drive(
                custom_path=image_path
            )

            # Run synchronous Gemini analysis without blocking
            result = await asyncio.to_thread(
                analyze_screenshot,
                image_path,
            )

    except Exception as error:
        log.exception("Screenshot analysis failed")

        await status.edit_text(
            "Analysis করা যায়নি:\n"
            f"{type(error).__name__}: {error}"
        )
        return

    try:
        pair = result.get("pair", "Unknown")
        timeframe = result.get("timeframe", "Unknown")
        pattern = result.get("pattern", "Unclear")
        behaviour = result.get(
            "market_behaviour",
            "Unclear",
        )

        direction = str(
            result.get("direction", "NO SIGNAL")
        ).upper()

        confidence = float(
            result.get("confidence", 0)
        )

        evidence = result.get("evidence", [])

        # Count previous similar setups before saving current one
        similar = get_similar_count(
            pattern,
            behaviour,
        )

        save_analysis(
            pair,
            timeframe,
            pattern,
            behaviour,
            direction,
            confidence,
            result,
        )

        approved = (
            direction in ("CALL", "PUT")
            and result.get("actionable") is True
            and confidence >= MIN_CONFIDENCE
            and isinstance(evidence, list)
            and len(evidence) >= 2
            and similar >= MIN_SIMILAR
            and result.get("screenshot_quality") == "good"
        )

        if not approved:
            await status.edit_text(
                "NO SIGNAL\n\n"
                f"Pair: {pair}\n"
                f"Timeframe: {timeframe}\n"
                f"Pattern: {pattern}\n"
                f"Market Behaviour: {behaviour}\n\n"
                "কারণ: যথেষ্ট confirmation বা "
                "repeated history পাওয়া যায়নি।"
            )
            return

        arrow = "↑" if direction == "CALL" else "↓"

        signal_text = (
            "QUOTEX AI ANALYSIS\n\n"
            f"{direction} {arrow}\n\n"
            f"Pair: {pair}\n"
            f"Timeframe: {timeframe}\n"
            f"Pattern: {pattern}\n"
            f"Market Behaviour: {behaviour}\n"
            f"Previous Similar Setups: {similar}\n\n"
            f"Contact: {CONTACT}"
        )

        await status.edit_text(signal_text)

    except Exception as error:
        log.exception("Result processing failed")

        await status.edit_text(
            "Result processing error:\n"
            f"{type(error).__name__}: {error}"
        )


async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if allowed(update) and update.message:
        await update.message.reply_text(
            "Chart screenshot পাঠাও।\n"
            "/help লিখে নির্দেশনা দেখো।"
        )


# Create Telegram application
init_db()

telegram_app = (
    Application.builder()
    .token(BOT_TOKEN)
    .build()
)

telegram_app.add_handler(
    CommandHandler("start", start)
)

telegram_app.add_handler(
    CommandHandler("help", help_cmd)
)

telegram_app.add_handler(
    CommandHandler("id", id_cmd)
)

telegram_app.add_handler(
    MessageHandler(filters.PHOTO, photo_handler)
)

telegram_app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        text_handler,
    )
)


# Render Webhook lifecycle
@asynccontextmanager
async def lifespan(web_app: FastAPI):

    await telegram_app.initialize()
    await telegram_app.start()

    webhook_url = (
        f"{RENDER_EXTERNAL_URL}/telegram/{WEBHOOK_SECRET}"
    )

    await telegram_app.bot.set_webhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET,
        allowed_updates=Update.ALL_TYPES,
    )

    log.info("Telegram webhook configured successfully")

    try:
        yield

    finally:
        await telegram_app.bot.delete_webhook()
        await telegram_app.stop()
        await telegram_app.shutdown()


app = FastAPI(lifespan=lifespan)


# Health check
@app.get("/")
async def health():
    return {
        "ok": True,
        "service": "Quotex AI Telegram Bot",
    }


# Receive Telegram updates
@app.post("/telegram/{secret}")
async def telegram_webhook(
    secret: str,
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(
        default=None
    ),
):

    if (
        secret != WEBHOOK_SECRET
        or x_telegram_bot_api_secret_token != WEBHOOK_SECRET
    ):
        raise HTTPException(
            status_code=403,
            detail="Forbidden",
        )

    try:
        payload = await request.json()

        update = Update.de_json(
            payload,
            telegram_app.bot,
        )

        await telegram_app.process_update(update)

    except Exception:
        log.exception("Webhook processing failed")

        raise HTTPException(
            status_code=500,
            detail="Update processing failed",
        )

    return {"ok": True}


# Start Render web server
if __name__ == "__main__":

    import uvicorn

    port = int(os.getenv("PORT", "10000"))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
    )
status
