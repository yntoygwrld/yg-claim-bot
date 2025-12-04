"""YG Video Claim Bot - Telegram bot for $YNTOYG viral content distribution"""
import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import config
import database as db

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ============ COMMAND HANDLERS ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command with optional magic link token"""
    user = update.effective_user
    args = context.args

    # Check if user already exists
    existing_user = await db.get_user_by_telegram_id(user.id)

    if existing_user:
        await update.message.reply_text(
            f"Welcome back, Gentleman! 🎩\n\n"
            f"Your current stats:\n"
            f"• Gentleman Score: {existing_user.get('gentleman_score', 0)}\n"
            f"• Streak: {existing_user.get('streak_count', 0)} days\n"
            f"• Total Claims: {existing_user.get('total_claims', 0)}\n\n"
            f"Use /claim to get today's video!"
        )
        return

    # New user - check for magic link token
    if args and len(args) > 0:
        token = args[0]
        email = await db.verify_magic_token(token)

        if email:
            # Create user with linked email
            await db.create_user(email, user.id)
            await update.message.reply_text(
                f"🎩 Welcome to $YNTOYG, Gentleman!\n\n"
                f"Your email ({email}) is now linked.\n\n"
                f"Next steps:\n"
                f"1. /wallet <address> - Connect your Solana wallet\n"
                f"2. /connect - Link your social accounts\n"
                f"3. /claim - Get your daily video\n\n"
                f"Let's transform from YN to YG together!"
            )
        else:
            await update.message.reply_text(
                "❌ Invalid or expired magic link.\n\n"
                "Please get a new link from https://yntoyg.com"
            )
    else:
        await update.message.reply_text(
            "🎩 Welcome to $YNTOYG!\n\n"
            "To get started, please sign up at:\n"
            "https://yntoyg.com\n\n"
            "You'll receive a magic link to connect your account."
        )


async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /wallet command to connect Solana wallet"""
    user = update.effective_user
    args = context.args

    # Check if user exists
    db_user = await db.get_user_by_telegram_id(user.id)
    if not db_user:
        await update.message.reply_text(
            "Please complete /start first to link your account."
        )
        return

    if not args or len(args) == 0:
        await update.message.reply_text(
            "Usage: /wallet <solana_address>\n\n"
            "Example: /wallet 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
        )
        return

    wallet_address = args[0]

    # Basic Solana address validation (32-44 characters, base58)
    if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', wallet_address):
        await update.message.reply_text(
            "❌ Invalid Solana wallet address.\n"
            "Please provide a valid address."
        )
        return

    await db.update_user_wallet(user.id, wallet_address)
    await update.message.reply_text(
        f"✅ Wallet connected!\n\n"
        f"Address: {wallet_address[:8]}...{wallet_address[-4:]}\n\n"
        f"Next: Use /connect to link your socials, then /claim to get your daily video!"
    )


async def connect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /connect command to link social accounts"""
    user = update.effective_user

    # Check if user exists
    db_user = await db.get_user_by_telegram_id(user.id)
    if not db_user:
        await update.message.reply_text(
            "Please complete /start first to link your account."
        )
        return

    keyboard = [
        [InlineKeyboardButton("📱 TikTok", callback_data="connect_tiktok")],
        [InlineKeyboardButton("📸 Instagram", callback_data="connect_instagram")],
        [InlineKeyboardButton("🐦 Twitter/X", callback_data="connect_twitter")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Show current connections
    tiktok = db_user.get("tiktok_username", "Not connected")
    instagram = db_user.get("instagram_username", "Not connected")
    twitter = db_user.get("twitter_username", "Not connected")

    await update.message.reply_text(
        f"🔗 Connect your social accounts\n\n"
        f"Current connections:\n"
        f"• TikTok: {tiktok}\n"
        f"• Instagram: {instagram}\n"
        f"• Twitter: {twitter}\n\n"
        f"Select a platform to connect:",
        reply_markup=reply_markup
    )


async def claim(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /claim command to get daily video"""
    user = update.effective_user

    # Check if user exists
    db_user = await db.get_user_by_telegram_id(user.id)
    if not db_user:
        await update.message.reply_text(
            "Please complete /start first to link your account."
        )
        return

    # Check if already claimed today
    if await db.has_claimed_today(db_user["id"]):
        await update.message.reply_text(
            "⏰ You've already claimed today's video!\n\n"
            "Come back tomorrow for a fresh one.\n"
            "In the meantime, post your video and use /submit <link> to earn points!"
        )
        return

    # Get random video
    video = await db.get_random_active_video()
    if not video:
        await update.message.reply_text(
            "😅 No videos available right now.\n"
            "Please check back later!"
        )
        return

    # Create claim record
    await db.create_claim(db_user["id"], video["id"])

    # Send video
    await update.message.reply_text(
        f"🎬 Here's your daily video, Gentleman!\n\n"
        f"📹 {video.get('title', 'YG Content')}\n\n"
        f"Instructions:\n"
        f"1. Download and repost on TikTok, Instagram, or Twitter\n"
        f"2. Use /submit <link> to submit your repost\n"
        f"3. Earn points based on views!\n\n"
        f"The more views you get, the higher you climb on the leaderboard! 🏆"
    )

    # Send the actual video file
    await update.message.reply_document(
        document=video["video_url"],
        caption="Post this and submit your link with /submit"
    )


async def submit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /submit command to submit repost proof"""
    user = update.effective_user
    args = context.args

    # Check if user exists
    db_user = await db.get_user_by_telegram_id(user.id)
    if not db_user:
        await update.message.reply_text(
            "Please complete /start first to link your account."
        )
        return

    if not args or len(args) == 0:
        await update.message.reply_text(
            "Usage: /submit <post_url>\n\n"
            "Example:\n"
            "/submit https://tiktok.com/@youruser/video/1234567890\n"
            "/submit https://instagram.com/reel/ABC123/\n"
            "/submit https://twitter.com/youruser/status/1234567890"
        )
        return

    post_url = args[0]

    # Detect platform and validate URL
    platform = None
    for plat, pattern in config.URL_PATTERNS.items():
        if re.search(pattern, post_url):
            platform = plat
            break

    if not platform:
        await update.message.reply_text(
            "❌ Invalid URL.\n\n"
            "Please submit a valid TikTok, Instagram, or Twitter post URL."
        )
        return

    # TODO: Get the most recent video claimed by user
    # For now, we'll use a placeholder
    video_id = None  # Will be implemented with proper claim tracking

    # Create repost record
    await db.create_repost(db_user["id"], video_id, platform, post_url)

    await update.message.reply_text(
        f"✅ Repost submitted!\n\n"
        f"Platform: {platform.title()}\n"
        f"URL: {post_url}\n\n"
        f"We'll track your views and update your score.\n"
        f"Check /mystats to see your progress!"
    )


async def mystats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /mystats command to show user stats"""
    user = update.effective_user

    db_user = await db.get_user_by_telegram_id(user.id)
    if not db_user:
        await update.message.reply_text(
            "Please complete /start first to link your account."
        )
        return

    await update.message.reply_text(
        f"📊 Your Stats, Gentleman\n\n"
        f"🎩 Gentleman Score: {db_user.get('gentleman_score', 0)}\n"
        f"🔥 Streak: {db_user.get('streak_count', 0)} days\n"
        f"📹 Total Claims: {db_user.get('total_claims', 0)}\n"
        f"📤 Total Reposts: {db_user.get('total_reposts', 0)}\n"
        f"👀 Total Views Generated: {db_user.get('total_views_generated', 0):,}\n\n"
        f"Keep posting to climb the leaderboard! 🏆"
    )


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /leaderboard command to show top performers"""
    leaders = await db.get_weekly_leaderboard(10)

    if not leaders:
        await update.message.reply_text(
            "🏆 Leaderboard\n\n"
            "No rankings yet this week.\n"
            "Be the first to claim and post!"
        )
        return

    leaderboard_text = "🏆 This Week's Top Gentlemen\n\n"

    medals = ["🥇", "🥈", "🥉"]
    for i, leader in enumerate(leaders):
        medal = medals[i] if i < 3 else f"{i+1}."
        views = leader.get("total_views", 0)
        posts = leader.get("posts_count", 0)
        leaderboard_text += f"{medal} {views:,} views ({posts} posts)\n"

    leaderboard_text += "\n/claim to get your daily video and compete!"

    await update.message.reply_text(leaderboard_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command"""
    await update.message.reply_text(
        "🎩 $YNTOYG - How It Works\n\n"
        "1️⃣ /start - Begin your journey\n"
        "2️⃣ /wallet <addr> - Connect Solana wallet\n"
        "3️⃣ /connect - Link social accounts\n"
        "4️⃣ /claim - Get daily video content\n"
        "5️⃣ Post the video on TikTok/IG/Twitter\n"
        "6️⃣ /submit <url> - Submit your post link\n"
        "7️⃣ Earn points based on views!\n\n"
        "📊 /mystats - View your progress\n"
        "🏆 /leaderboard - See top performers\n\n"
        "The more views you generate, the higher your Gentleman Score!\n\n"
        "Learn more: https://yntoyg.com\n"
        "Community: https://t.me/yntoyg"
    )


# ============ CALLBACK HANDLERS ============

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button callbacks"""
    query = update.callback_query
    await query.answer()

    if query.data.startswith("connect_"):
        platform = query.data.replace("connect_", "")
        context.user_data["connecting_platform"] = platform
        await query.edit_message_text(
            f"Please send your {platform.title()} username:\n\n"
            f"Example: @yourUsername or just yourUsername"
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages (for social account connection flow)"""
    user = update.effective_user

    # Check if we're in a connection flow
    if "connecting_platform" in context.user_data:
        platform = context.user_data.pop("connecting_platform")
        username = update.message.text.strip().lstrip("@")

        await db.update_user_socials(user.id, platform, username)
        await update.message.reply_text(
            f"✅ {platform.title()} connected: @{username}\n\n"
            f"Use /connect to link more accounts or /claim to get your video!"
        )


# ============ MAIN ============

def main() -> None:
    """Start the bot"""
    # Create application
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("wallet", wallet))
    application.add_handler(CommandHandler("connect", connect))
    application.add_handler(CommandHandler("claim", claim))
    application.add_handler(CommandHandler("submit", submit))
    application.add_handler(CommandHandler("mystats", mystats))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("help", help_command))

    # Add callback handler for inline keyboards
    application.add_handler(CallbackQueryHandler(button_callback))

    # Add message handler for connection flow
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start polling
    logger.info("Starting YG Video Claim Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
