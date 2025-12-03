# YG Claim Bot

Telegram bot for the $YNTOYG viral content distribution system.

## Features

- `/start [token]` - Onboarding with magic link token from website
- `/wallet <address>` - Connect Solana wallet
- `/connect` - Link social accounts (TikTok, IG, Twitter)
- `/claim` - Get daily unique video content
- `/submit <url>` - Submit repost proof link
- `/mystats` - View personal stats and ranking
- `/leaderboard` - Top 10 gentlemen this week
- `/help` - How the system works

## Setup

1. Create bot with @BotFather on Telegram
2. Copy `.env.example` to `.env` and fill in credentials
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `python bot.py`

## Environment Variables

```
TELEGRAM_BOT_TOKEN=<from BotFather>
SUPABASE_URL=<project URL>
SUPABASE_KEY=<service role key>
```

## Architecture

```
yg-claim-bot/
├── bot.py              # Main Telegram bot
├── database.py         # Supabase CRUD operations
├── scraper.py          # Social media view scraper
├── leaderboard.py      # Rankings calculation
├── video_manager.py    # Video assignment logic
├── config.py           # Settings
├── requirements.txt
└── .env.example
```

## Deployment

Deploy to Koyeb or Railway:

```bash
# Procfile
worker: python bot.py
```

## Related

- Website: https://github.com/relaxshadow/yntoyg-website
- Deployed: https://yntoyg-website.vercel.app
