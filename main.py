import asyncio, logging, os, tempfile
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv
from vision import analyze_screenshot
from memory import init_db, save_analysis, get_similar_count

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID", "").strip()
CONTACT = os.getenv("CONTACT", "@Masktrader6T9")
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.82"))
MIN_SIMILAR = int(os.getenv("MIN_SIMILAR", "3"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("quotex-bot")

def allowed(update: Update) -> bool:
    return not ADMIN_USER_ID or str(update.effective_user.id) == ADMIN_USER_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    await update.message.reply_text(
        "QUOTEX AI ANALYSIS BOT চালু আছে।\n"
        "একটি পরিষ্কার Quotex chart screenshot পাঠাও।\n"
        "/id — তোমার Telegram user ID\n"
        "/help — নির্দেশনা"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    await update.message.reply_text(
        "ব্যবহার:\n"
        "১) 1-minute chart-এর এমন screenshot পাঠাও যাতে অনেকগুলো candle দেখা যায়।\n"
        "২) Pair ও timeframe দৃশ্যমান রাখো।\n"
        "৩) সম্ভব হলে candle countdown-ও দৃশ্যমান রাখো।\n\n"
        "Bot CALL/PUT নিশ্চিত করে না; অস্পষ্ট বা দুর্বল setup হলে কোনো signal দেবে না।"
    )

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your Telegram user ID: {update.effective_user.id}")

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    msg = update.message
    status = await msg.reply_text("Screenshot পেয়েছি। Chart ও candle behaviour বিশ্লেষণ করছি…")
    photo = msg.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "chart.jpg"
        await file.download_to_drive(custom_path=path)
        try:
            result = await asyncio.to_thread(analyze_screenshot, path)
        except Exception as e:
            log.exception("Analysis failed")
            await status.edit_text(f"Analysis করা যায়নি: {type(e).__name__}: {e}")
            return

    pair = result.get("pair", "Unknown")
    timeframe = result.get("timeframe", "Unknown")
    pattern = result.get("pattern", "Unclear")
    behaviour = result.get("market_behaviour", "Unclear")
    direction = result.get("direction", "NO SIGNAL").upper()
    confidence = float(result.get("confidence", 0))
    evidence = result.get("evidence", [])
    similar = get_similar_count(pattern, behaviour)

    save_analysis(pair, timeframe, pattern, behaviour, direction, confidence, result)

    # Strict gate: model must explicitly say setup is actionable and evidence is clear.
    approved = (
        direction in ("CALL", "PUT")
        and result.get("actionable") is True
        and confidence >= MIN_CONFIDENCE
        and len(evidence) >= 2
        and similar >= MIN_SIMILAR
        and result.get("screenshot_quality") == "good"
    )

    if not approved:
        await status.edit_text(
            "NO SIGNAL\n\n"
            f"Pair: {pair}\nTimeframe: {timeframe}\n"
            f"Pattern: {pattern}\nMarket Behaviour: {behaviour}\n"
            "কারণ: যথেষ্ট পরিষ্কার confirmation / repeated history পাওয়া যায়নি।\n"
            "এটি ইচ্ছাকৃত safety filter।"
        )
        return

    arrow = "↑" if direction == "CALL" else "↓"
    text = (
        "QUOTEX AI ANALYSIS\n\n"
        f"{direction} {arrow}\n"
        f"Pair: {pair}\n"
        f"Timeframe: {timeframe}\n"
        f"Pattern: {pattern}\n"
        f"Market Behaviour: {behaviour}\n"
        f"Previous Similar Setups: {similar}\n\n"
        f"Contact: {CONTACT}"
    )
    await status.edit_text(text)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if allowed(update):
        await update.message.reply_text("Chart screenshot পাঠাও। /help লিখে নির্দেশনা দেখো।")


# Render Free Web Service uses an HTTP server. Use Telegram webhook instead of run_polling().
# Required Render environment variables:
# TELEGRAM_BOT_TOKEN, RENDER_EXTERNAL_URL, WEBHOOK_SECRET
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Request
import uvicorn

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN Render Environment-এ সেট করা নেই")
if not RENDER_EXTERNAL_URL:
    raise RuntimeError("RENDER_EXTERNAL_URL Render Environment-এ পাওয়া যায়নি")
if not WEBHOOK_SECRET:
    raise RuntimeError("WEBHOOK_SECRET Render Environment-এ সেট করা নেই")

init_db()
telegram_app = Application.builder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", help_cmd))
telegram_app.add_handler(CommandHandler("id", id_cmd))
telegram_app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

@asynccontextmanager
async def lifespan(web_app: FastAPI):
    await telegram_app.initialize()
    await telegram_app.start()
    webhook_url = f"{RENDER_EXTERNAL_URL}/telegram/{WEBHOOK_SECRET}"
    await telegram_app.bot.set_webhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET,
        allowed_updates=Update.ALL_TYPES,
    )
    log.info("Telegram webhook configured")
    try:
        yield
    finally:
        await telegram_app.bot.delete_webhook()
        await telegram_app.stop()
        await telegram_app.shutdown()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def health():
    return {"ok": True, "service": "quotex-ai-telegram-bot"}

@app.post("/telegram/{secret}")
async def telegram_webhook(
    secret: str,
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if secret != WEBHOOK_SECRET or x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        payload = await request.json()
        update = Update.de_json(payload, telegram_app.bot)
        await telegram_app.process_update(update)
    except Exception:
        log.exception("Webhook update processing failed")
        raise HTTPException(status_code=500, detail="Update processing failed")
    return {"ok": True}

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
web
