# Quotex AI Screenshot Telegram Bot (Starter)

## গুরুত্বপূর্ণ সীমাবদ্ধতা
এই সংস্করণটি একটি পরীক্ষামূলক starter bot। এটি Screenshot থেকে দৃশ্যমান candle/pattern বর্ণনা করে।
এটি ভবিষ্যৎ candle দেখতে পারে না, OTC market-এর নির্ভরযোগ্য historical data পায় না এবং লাভ নিশ্চিত করে না।
Database-এ আগের analysis জমা হয়; একই pattern count হওয়া মানেই সেটি profitable প্রমাণ নয়।
বর্তমান gate খুব conservative: অন্তত ৩টি আগের একই pattern/behaviour observation না থাকলে signal পাঠাবে না।
তাই একদম নতুন database-এ সাধারণত NO SIGNAL হবে—এটাই প্রত্যাশিত।

## Android-এ চালানো (Termux)
1. Termux install করে খুলুন।
2. চালান:
   ```
   pkg update -y && pkg upgrade -y
   pkg install python git -y
   ```
3. ZIP extract করে folder-এ যান।
4. চালান:
   ```
   pip install -r requirements.txt
   cp .env.example .env
   ```
5. `.env` ফাইল edit করে Telegram token এবং Gemini API key বসান।
6. প্রথমে bot-এ `/id` পাঠিয়ে নিজের Telegram user ID জেনে `.env`-এর `ADMIN_USER_ID`-তে বসান।
7. চালান:
   ```
   python main.py
   ```

## API Key
Gemini API key Google AI Studio থেকে তৈরি করুন: https://aistudio.google.com/app/apikey
Telegram token BotFather থেকে পাওয়া token। কাউকে পাঠাবেন না, GitHub-এ `.env` upload করবেন না।

## Signal rule
- Screenshot-এ Pair/Timeframe/candles পরিষ্কার না হলে NO SIGNAL।
- Gemini-এর visual confidence 0.82-এর কম হলে NO SIGNAL।
- একই pattern + behaviour আগের অন্তত ৩ বার database-এ না থাকলে NO SIGNAL।
- এটি live market execution clock নয়। Screenshot পাঠানো ও AI response-এর latency-র কারণে পরের candle miss হতে পারে।
- 1-minute expiry-তে real-money use করার আগে দীর্ঘ সময় demo test করুন।

## Model
`.env`-এর `GEMINI_MODEL` দিয়ে model পরিবর্তন করা যায়। Google AI Studio-তে আপনার project-এর available model ও free quota দেখে নিন।
