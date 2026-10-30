import json, os
from pathlib import Path
from google import genai
from google.genai import types
from PIL import Image

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
API_KEY = os.getenv("GEMINI_API_KEY", "")

PROMPT = """
You are a cautious visual chart-observation assistant, NOT a profit predictor.
Analyze only what is visibly present in this screenshot. Never invent candles,
prices, pair names, timeframe, history, or future outcomes.

The chart is intended to be a Quotex 1-minute candlestick chart. Identify:
- visible pair and timeframe, otherwise Unknown
- screenshot quality: good or poor
- visible candle structures and possible patterns among:
Hammer, Bullish Engulfing, Morning Star, Piercing Line, Three White Soldiers,
Inverted Hammer, Shooting Star, Bearish Engulfing, Evening Star, Dark Cloud Cover,
Three Black Crows, Hanging Man, Dragonfly Doji, Gravestone Doji, Doji,
Spinning Top, Bullish Harami, Bearish Harami, Bullish Marubozu, Bearish Marubozu,
or Unclear/Custom Behaviour.
- trend and market structure, visible support/resistance, rejection/continuation
- what happened AFTER similar visible patterns only if the screenshot itself shows it.
Do not claim that a pattern repeats 2-3 times unless you can point to distinct visible
examples in this screenshot. Do not claim historical win rates.

A signal is actionable only when the final fully closed candle, context, and repeated
behaviour provide clear evidence. If uncertain, use NO SIGNAL. The next candle's future
direction cannot be known from a screenshot. Never promise a win or say loss-free.

Return ONLY valid JSON with this schema:
{
 "pair":"string",
 "timeframe":"string",
 "screenshot_quality":"good|poor",
 "direction":"CALL|PUT|NO SIGNAL",
 "pattern":"string",
 "market_behaviour":"string",
 "confidence":0.0,
 "actionable":false,
 "evidence":["visible evidence 1","visible evidence 2"],
 "similar_examples_visible":0,
 "warnings":["string"]
}
Confidence is visual assessment confidence, NOT probability of winning.
"""

def analyze_screenshot(image_path: Path) -> dict:
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY .env ফাইলে সেট করা নেই")
    client = genai.Client(api_key=API_KEY)
    img = Image.open(image_path).convert("RGB")
    response = client.models.generate_content(
        model=MODEL,
        contents=[PROMPT, img],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )
    raw = response.text or "{}"
    data = json.loads(raw)
    required = ["pair", "timeframe", "screenshot_quality", "direction",
                "pattern", "market_behaviour", "confidence", "actionable", "evidence"]
    for key in required:
        if key not in data:
            raise ValueError(f"Gemini response missing field: {key}")
    return data
