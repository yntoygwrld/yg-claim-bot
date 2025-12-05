# YG Claim Bot - Claude Code Instructions

## Project Overview
Telegram bot for $YNTOYG viral content distribution. Users claim daily videos, repost on socials, and earn points.

## Deployment

### Platform: Koyeb
- **Service URL**: Deployed on Koyeb (serverless)
- **GitHub Repo**: `yntoygwrld/yg-claim-bot`
- **Procfile**: `worker: python bot.py`

### Environment Variables (Set in Koyeb Dashboard)
```
TELEGRAM_BOT_TOKEN=<from BotFather>
SUPABASE_URL=https://jdaderasjnuuahzebonq.supabase.co
SUPABASE_KEY=<service role key>
```

### Deployment Flow
1. Push code to `main` branch on GitHub
2. Koyeb auto-deploys from GitHub
3. If token needs update, go to Koyeb dashboard → Service → Environment Variables

### To Get New Bot Token
1. Open Telegram → @BotFather
2. Send `/mybots`
3. Select `@yntoyg_claim_bot`
4. Click "API Token" → "Revoke current token"
5. Copy new token to Koyeb environment variables

## Bot Architecture

### Admin Commands
| Command | Description |
|---------|-------------|
| `/admin` | Dashboard with all settings |
| `/addvideo` | Add video to pool (send as document) |
| `/listvideosadmin` | List all videos |
| `/video_enable <id>` | Enable video |
| `/video_disable <id>` | Disable video |
| `/admin_pause` | Pause claims |
| `/admin_resume` | Resume claims |

### User Commands
| Command | Description |
|---------|-------------|
| `/start` | Begin onboarding |
| `/claim` | Get daily video |
| `/submit <url>` | Submit repost proof |
| `/mystats` | View stats |
| `/leaderboard` | Top performers |

### Video Uniquification
- Each video served has unique XMP metadata injected
- Prevents duplicate content detection on social platforms
- Uses `video_uniquifier_integration.py` → imports from `../metadata thing/`

### Database (Supabase)
- **Project**: jdaderasjnuuahzebonq
- **Tables**: users, videos, daily_claims, reposts, bot_settings
- **Video Storage**: Uses `telegram_file_id` (Telegram's internal storage)

## Admin User
- **Telegram ID**: 8227072324 (@OriginalYG)
- Hardcoded in `config.py` → `ADMIN_USER_IDS`

## File Structure
```
bot.py                          # Main bot handlers
database.py                     # Supabase operations
config.py                       # Configuration & admin IDs
video_uniquifier_integration.py # Metadata uniquification
requirements.txt                # Python dependencies
Procfile                        # Koyeb worker config
```

## Dependencies
- python-telegram-bot==21.0
- supabase==2.10.0
- aiohttp==3.9.3
- python-dotenv==1.0.0

---

## 🚨 MANDATORY: Git Commit & Push Protocol

**CRITICAL: After ANY code changes, you MUST commit and push immediately.**

### Why This Matters
- Koyeb auto-deploys from GitHub on push to `main`
- Local changes DO NOTHING until pushed
- The bot runs on Koyeb, NOT locally
- User expects to see changes live immediately

### After Every Code Change:
```bash
git add -A
git commit -m "descriptive message"
git push origin main
```

### DO NOT:
- ❌ Leave changes uncommitted
- ❌ Wait for user to ask you to push
- ❌ Assume local changes affect the live bot
- ❌ Forget to push after editing files

### DO:
- ✅ Commit immediately after making changes
- ✅ Push to trigger Koyeb auto-deploy
- ✅ Write clear commit messages
- ✅ Verify push succeeded before moving on

### Verification After Push:
1. Check git status shows clean working tree
2. Wait ~30 seconds for Koyeb to detect changes
3. Check Koyeb dashboard for new deployment
4. Verify deployment is healthy

### Commit Message Format:
```
feat: Add new feature
fix: Fix bug in X
update: Update configuration
refactor: Refactor code structure
docs: Update documentation
```

**REMEMBER: Changes only go live after `git push origin main`!**
