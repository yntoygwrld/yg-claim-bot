# YG Claim Bot - Claude Code Instructions

## Project Overview
Telegram bot for $YNTOYG viral content distribution. Users claim daily videos, repost on socials, and earn points.

## 🧪 TESTING PROTOCOL

### Test Account
- **Email:** hugepileofjunk@gmail.com
- **Telegram ID:** 5836555576

### Before EVERY Test
1. **Wipe test data** - Tell Claude: `Delete all records for hugepileofjunk@gmail.com`
2. **Leave Covenant group** (if testing "join group" flow) - User must manually leave $YNTOYG Covenant group in Telegram
3. Wait for Claude to confirm "DELETED"

### Two Onboarding Paths
The bot has TWO different flows based on group membership:

| Scenario | Flow |
|----------|------|
| Valid token + ALREADY in group | Instant activation (skips join step) |
| Valid token + NOT in group | Pending state → "Join group first" → Button to complete |

### To Test "Join Group" Flow
User MUST leave the Covenant group before testing, otherwise they'll hit the "instant activation" path.

### Test Guide Location
Full step-by-step test guide: `/mnt/x/YNTOYG/POST_LAUNCH/TEST_GUIDE.md`

## 🚨 STRICT ACCOUNT RULES - MANDATORY

### GitHub Account
- **Username:** `yntoygwrld` (NOT relaxshadow!)
- **Repository:** `yntoygwrld/yg-claim-bot`
- **Branch:** `main`

### Before Any Git Operations:
1. Verify `git remote -v` shows `yntoygwrld/yg-claim-bot`
2. If wrong, fix with: `git remote set-url origin https://github.com/yntoygwrld/yg-claim-bot.git`

## Deployment

### Platform: Koyeb
- **Service URL**: Deployed on Koyeb (serverless)
- **Service Name**: `yg-claim-bot` (sticky-lavinia)
- **GitHub Repo**: `yntoygwrld/yg-claim-bot`
- **Procfile**: `worker: python bot.py`

### ⚠️ IMPORTANT: Manual Redeploy Required
Koyeb is configured with "Public repository" mode, which does NOT auto-deploy.
After pushing code, you MUST manually trigger a redeploy on Koyeb.

### Environment Variables (Set in Koyeb Dashboard)
```
TELEGRAM_BOT_TOKEN=<from BotFather>
SUPABASE_URL=https://jdaderasjnuuahzebonq.supabase.co
SUPABASE_KEY=<service role key>
ADMIN_USER_IDS=8227072324
```

### Deployment Flow
1. Push code to `main` branch on GitHub
2. Go to Koyeb dashboard → Services → yg-claim-bot
3. Click "Redeploy" button → "Trigger build"
4. Wait for deployment to become "Healthy"
5. If token needs update, go to Koyeb dashboard → Service → Settings → Environment Variables

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
| `/addvideo` | Add single video to pool |
| `/bulkupload` | Start bulk upload mode (send multiple videos) |
| `/done` | End bulk upload mode |
| `/listvideosadmin` | List all videos |
| `/video_enable <id>` | Enable video |
| `/video_disable <id>` | Disable video |
| `/video_delete <id>` | Delete video |
| `/admin_pause` | Pause claims |
| `/admin_resume` | Resume claims |
| `/dev` | Test video download (no claim increment) |

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
- Local changes DO NOTHING until pushed AND redeployed
- The bot runs on Koyeb, NOT locally
- User expects to see changes live immediately
- Koyeb uses "Public repository" mode - NO auto-deploy!

### After Every Code Change:
```bash
git add -A
git commit -m "descriptive message"
git push origin main
```

### 🤖 AUTOMATED KOYEB REDEPLOY (Use Playwright!)
After pushing code, use Playwright MCP to trigger redeploy:

1. **Navigate to Koyeb** (if not already open):
   - Use `browser_tabs` to select Koyeb tab, or
   - Use `browser_navigate` to `https://app.koyeb.com/services`

2. **Click on yg-claim-bot service** (sticky-lavinia)

3. **Click "Redeploy" button**

4. **In dialog, click "Trigger build"** (NOT "Skip build")

5. **Wait ~60 seconds** for deployment

6. **Verify status shows "Healthy"**

This is MANDATORY after every push - do NOT ask user to do it manually!

### DO NOT:
- ❌ Leave changes uncommitted
- ❌ Wait for user to ask you to push
- ❌ Assume local changes affect the live bot
- ❌ Forget to push after editing files

### DO:
- ✅ Commit immediately after making changes
- ✅ Push to GitHub (`yntoygwrld/yg-claim-bot`)
- ✅ Write clear commit messages
- ✅ Go to Koyeb and click "Redeploy" → "Trigger build"
- ✅ Verify deployment becomes healthy

### Verification After Push + Redeploy:
1. Check git status shows clean working tree
2. Go to Koyeb dashboard → Services → yg-claim-bot
3. Click "Redeploy" → "Trigger build"
4. Wait for build to complete (~30-60 seconds)
5. Verify deployment shows "Healthy"

### Commit Message Format:
```
feat: Add new feature
fix: Fix bug in X
update: Update configuration
refactor: Refactor code structure
docs: Update documentation
```

**REMEMBER: Changes only go live after `git push origin main`!**
