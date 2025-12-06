"""YG Video Claim Bot - Telegram bot for $YNTOYG viral content distribution"""
import logging
import random
import re
import tempfile
from pathlib import Path
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    ContextTypes,
    filters,
)
import config
import database as db
from video_uniquifier_integration import serve_unique_video, get_uniquifier

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def generate_random_filename() -> str:
    """Generate a random video filename for uniqueness"""
    prefixes = ["video", "vid", "clip", "content", "media", "VID", "MOV"]
    prefix = random.choice(prefixes)
    number = random.randint(10000000, 99999999)
    return f"{prefix}{number}.mp4"


def get_submit_buttons(submitted_platforms: list = None) -> InlineKeyboardMarkup:
    """Create inline keyboard with submit buttons for platforms not yet submitted."""
    if submitted_platforms is None:
        submitted_platforms = []

    buttons = []
    for platform in config.SUPPORTED_PLATFORMS:
        if platform not in submitted_platforms:
            name = config.PLATFORM_NAMES.get(platform, platform.title())
            buttons.append([
                InlineKeyboardButton(
                    f"Submit {name} Link  +{config.POINTS_SUBMIT} PTS",
                    callback_data=f"submit_{platform}"
                )
            ])

    return InlineKeyboardMarkup(buttons) if buttons else None


def get_remaining_platforms_text(submitted_platforms: list) -> str:
    """Get text describing remaining platforms to submit to."""
    remaining = [p for p in config.SUPPORTED_PLATFORMS if p not in submitted_platforms]
    if not remaining:
        return ""
    names = [config.PLATFORM_NAMES.get(p, p.title()) for p in remaining]
    return ", ".join(names)


# ============ GROUP MEMBERSHIP CHECK ============

async def check_covenant_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user is a member of the $YNTOYG Covenant private group."""
    try:
        member = await context.bot.get_chat_member(
            config.YNTOYG_COVENANT_GROUP_ID,
            user_id
        )
        # Check if member status indicates they're in the group
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.warning(f"Could not check membership for user {user_id}: {e}")
        return False


# ============ SOLANA WALLET VERIFICATION ============
# NOTE: Pre-launch mode - token verification NOT enforced yet.
# See /mnt/x/YNTOYG/POST_LAUNCH/02_TOKEN_VERIFICATION.md for activation.

# $YNTOYG token mint address - SET AFTER LAUNCH via activation prompt
YNTOYG_MINT_ADDRESS = None  # Will be set post-launch


def validate_solana_address(address: str) -> bool:
    """Validate Solana wallet address format.

    Solana addresses are base58 encoded, 32-44 characters.
    Base58 excludes: 0, O, I, l (zero, uppercase O, uppercase I, lowercase L)
    """
    if not address or not isinstance(address, str):
        return False
    # Base58 character set (no 0, O, I, l)
    base58_pattern = r'^[1-9A-HJ-NP-Za-km-z]{32,44}$'
    return bool(re.match(base58_pattern, address))


async def verify_token_holdings(wallet_address: str, mint_address: str = None):
    """Verify if wallet holds $YNTOYG tokens.

    PRE-LAUNCH MODE: Always returns (True, 0) to allow wallet registration
    without token ownership verification.

    POST-LAUNCH: Will verify actual token holdings via Solana RPC.
    See /mnt/x/YNTOYG/POST_LAUNCH/02_TOKEN_VERIFICATION.md

    Args:
        wallet_address: User's Solana wallet address
        mint_address: Token mint address (uses YNTOYG_MINT_ADDRESS if not provided)

    Returns:
        Tuple of (holds_token: bool, balance: int)
    """
    mint = mint_address or YNTOYG_MINT_ADDRESS

    if not mint:
        # Pre-launch mode: Accept all wallets
        logger.info(f"Pre-launch mode: Accepting wallet {wallet_address[:8]}... without token verification")
        return (True, 0)

    # POST-LAUNCH: This section will be activated when contract address is set
    # See /mnt/x/YNTOYG/POST_LAUNCH/02_TOKEN_VERIFICATION.md for full implementation
    logger.warning(f"Token verification called but mint address set - should implement RPC check")
    return (True, 0)


# ============ ADMIN DECORATOR ============

def admin_only(func):
    """Decorator to restrict commands to admin users"""
    # Hardcoded admin IDs - DO NOT REMOVE
    HARDCODED_ADMINS = [8227072324]  # @OriginalYG

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        # Check both hardcoded and config admin lists
        all_admins = set(HARDCODED_ADMINS + getattr(config, 'ADMIN_USER_IDS', []))
        if user_id not in all_admins:
            await update.message.reply_text("❌ This command is admin-only.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


# ============ COMMAND HANDLERS ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command with optional magic link token.

    Flow handles all cases:
    1. Existing user → Welcome back
    2. New user with token + in group → Complete onboarding
    3. New user with token + NOT in group → Store pending, ask to join
    4. New user without token + has pending + in group → Complete with pending data
    5. New user without token + has pending + NOT in group → Remind to join
    6. New user without token + no pending → Direct to website
    """
    user = update.effective_user
    args = context.args
    token = args[0] if args and len(args) > 0 else None

    # STEP 1: Check if user already exists (returning user)
    existing_user = await db.get_user_by_telegram_id(user.id)
    if existing_user:
        await update.message.reply_text(
            f"Welcome back.\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"YOUR STATS\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"▸ Gentleman Score: {existing_user.get('gentleman_score', 0)}\n"
            f"▸ Streak: {existing_user.get('streak_count', 0)} days\n"
            f"▸ Total Claims: {existing_user.get('total_claims', 0)}\n\n"
            f"Type /claim to get today's video."
        )
        return

    # STEP 2: Check group membership
    is_covenant_member = await check_covenant_membership(user.id, context)

    # STEP 3: Process token if provided
    if token:
        # Validate token WITHOUT consuming it yet
        email = await db.verify_magic_token_without_consuming(token)

        if not email:
            await update.message.reply_text(
                f"INVALID OR EXPIRED LINK\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"This magic link is no longer valid.\n\n"
                f"Get a new link at https://yntoyg.com"
            )
            return

        if is_covenant_member:
            # User has valid token AND is in group → Complete onboarding
            await db.create_user(email, user.id)
            await db.consume_magic_token(token)
            # Clean up any pending record
            await db.delete_pending_onboarding(user.id)

            # Generate dashboard auth token for instant website access
            dashboard_token = await db.generate_dashboard_token(email)
            dashboard_url = f"https://yntoyg.com/api/auth/verify?token={dashboard_token}"

            await update.message.reply_text(
                f"🎉 <b>Welcome to the Covenant</b>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>ACCOUNT ACTIVATED</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Your email <i>{email}</i> is now linked.\n\n"
                f"<b>📊 VIEW YOUR DASHBOARD</b>\n"
                f"▸ {dashboard_url}\n\n"
                f"<b>⚡ AVAILABLE COMMANDS</b>\n\n"
                f"▸ /claim — <i>Get your daily video (+{config.POINTS_CLAIM} pts)</i>\n\n"
                f"▸ Submit links — <i>+{config.POINTS_SUBMIT} pts each platform</i>\n\n"
                f"▸ /wallet — <i>Connect Solana wallet</i>\n\n"
                f"▸ /mystats — <i>View your stats</i>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>From YN to YG.</b>",
                parse_mode="HTML"
            )
        else:
            # User has valid token but NOT in group → Store pending
            await db.store_pending_onboarding(user.id, email, token)

            # Create button for easy completion after joining
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("I've Joined → Complete Setup", callback_data="complete_setup")]
            ])

            await update.message.reply_text(
                f"✅ <b>Email Verified</b>\n"
                f"<i>{email}</i>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>FINAL STEP: JOIN THE COVENANT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👉 <b>Tap here:</b> {config.YNTOYG_PORTAL_LINK}\n\n"
                f"Complete the verification to join.\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📲 <b>THEN COME BACK TO THIS CHAT</b>\n"
                f"<i>I'll message you here when you're in!</i>",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        return

    # STEP 4: No token - check for pending onboarding
    pending = await db.get_pending_onboarding(user.id)

    if pending:
        if is_covenant_member:
            # User completed group join → Finish onboarding with pending data
            email = pending["email"]
            original_token = pending["original_token"]

            await db.create_user(email, user.id)
            await db.consume_magic_token(original_token)
            await db.delete_pending_onboarding(user.id)

            # Generate dashboard auth token for instant website access
            dashboard_token = await db.generate_dashboard_token(email)
            dashboard_url = f"https://yntoyg.com/api/auth/verify?token={dashboard_token}"

            await update.message.reply_text(
                f"🎉 <b>Welcome to the Covenant</b>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>ACCOUNT ACTIVATED</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Your email <i>{email}</i> is now linked.\n\n"
                f"<b>📊 VIEW YOUR DASHBOARD</b>\n"
                f"▸ {dashboard_url}\n\n"
                f"<b>⚡ AVAILABLE COMMANDS</b>\n\n"
                f"▸ /claim — <i>Get your daily video (+{config.POINTS_CLAIM} pts)</i>\n\n"
                f"▸ Submit links — <i>+{config.POINTS_SUBMIT} pts each platform</i>\n\n"
                f"▸ /wallet — <i>Connect Solana wallet</i>\n\n"
                f"▸ /mystats — <i>View your stats</i>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>From YN to YG.</b>",
                parse_mode="HTML"
            )
        else:
            # User has pending but still not in group → Remind them
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("I've Joined → Complete Setup", callback_data="complete_setup")]
            ])

            await update.message.reply_text(
                f"⏳ <b>Almost There!</b>\n"
                f"<i>Email verified — just need to join the group!</i>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>JOIN THE COVENANT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👉 <b>Tap here:</b> {config.YNTOYG_PORTAL_LINK}\n\n"
                f"Complete the verification to join.\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📲 <b>THEN COME BACK TO THIS CHAT</b>\n"
                f"<i>I'll message you here when you're in!</i>",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        return

    # STEP 5: No token, no pending, not in group → Direct to covenant signup
    if not is_covenant_member:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join the Covenant →", url="https://yntoyg.com/covenant/join")]
        ])

        await update.message.reply_text(
            f"<b>$YNTOYG</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>JOIN THE COVENANT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>1.</b>  Tap the button below\n\n"
            f"<b>2.</b>  Enter your email\n\n"
            f"<b>3.</b>  Check inbox for magic link\n\n"
            f"<b>4.</b>  Click it to return here\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>From YN to YG.</b>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        # In group but no token/pending → Sign up on website
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Link Your Account →", url="https://yntoyg.com/covenant/join")]
        ])

        await update.message.reply_text(
            f"<b>$YNTOYG</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>LINK YOUR ACCOUNT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<i>You're in the Covenant but haven't linked your account yet.</i>\n\n"
            f"<b>1.</b>  Tap the button below\n\n"
            f"<b>2.</b>  Enter your email\n\n"
            f"<b>3.</b>  Click the magic link in your inbox\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>From YN to YG.</b>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )


async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /wallet command to connect Solana wallet.

    PRE-LAUNCH: Accepts wallets without token verification.
    POST-LAUNCH: Will verify $YNTOYG token holdings.
    See /mnt/x/YNTOYG/POST_LAUNCH/02_TOKEN_VERIFICATION.md
    """
    user = update.effective_user
    args = context.args

    # Check if user exists
    db_user = await db.get_user_by_telegram_id(user.id)
    if not db_user:
        await update.message.reply_text(
            "Please complete /start first to link your account."
        )
        return

    # Check if wallet already connected (wallets cannot be changed)
    if db_user.get('wallet_address'):
        short_addr = f"{db_user['wallet_address'][:8]}...{db_user['wallet_address'][-4:]}"
        await update.message.reply_text(
            f"Wallet Already Connected\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Your wallet: {short_addr}\n\n"
            f"Wallets cannot be changed once connected."
        )
        return

    # No address provided - show instructions
    if not args or len(args) == 0:
        await update.message.reply_text(
            "Connect Your Wallet\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "To participate in the Gentleman's System:\n\n"
            "I. You need a Solana wallet\n"
            "   (Phantom, Solflare, Backpack)\n\n"
            "II. One wallet = One account\n"
            "   No exceptions\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "TO CONNECT:\n"
            "/wallet YourSolanaAddressHere\n\n"
            "Example:\n"
            "/wallet 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU\n\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        return

    wallet_address = args[0].strip()

    # Validate Solana address format using helper
    if not validate_solana_address(wallet_address):
        await update.message.reply_text(
            "❌ Invalid Address\n\n"
            "That doesn't look like a valid Solana wallet address.\n\n"
            "Solana addresses are 32-44 characters using base58 encoding."
        )
        return

    # Check if wallet already used by another account
    existing_wallet = await db.get_wallet_by_address(wallet_address)
    if existing_wallet:
        await update.message.reply_text(
            "❌ Wallet Already Linked\n\n"
            "This wallet is connected to another account.\n\n"
            "Each wallet may only be linked once.\n"
            "The Covenant does not tolerate duplicity."
        )
        return

    # PRE-LAUNCH: Verify token holdings (currently returns True, 0)
    # POST-LAUNCH: This will actually check Solana RPC for $YNTOYG holdings
    holds_token, balance = await verify_token_holdings(wallet_address)

    # NOTE: Post-launch, this check will reject users without tokens
    # For now, holds_token is always True (pre-launch mode)
    if not holds_token:
        await update.message.reply_text(
            "❌ No $YNTOYG Detected\n\n"
            "This wallet does not hold any $YNTOYG tokens.\n\n"
            "To participate in the Gentleman's System:\n"
            "▸ Acquire $YNTOYG tokens\n"
            "▸ Return and try again\n\n"
            "Only holders may ascend."
        )
        return

    # Register the wallet in both wallet_registry and users tables
    await db.register_wallet(
        user_id=db_user['id'],
        telegram_id=user.id,
        wallet_address=wallet_address,
        token_balance=balance,
        verified=bool(YNTOYG_MINT_ADDRESS)  # True if post-launch with verification
    )

    short_addr = f"{wallet_address[:6]}...{wallet_address[-4:]}"

    await update.message.reply_text(
        f"✅ Wallet Connected\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Your Solana wallet has been linked:\n"
        f"{short_addr}\n\n"
        f"UNLOCKED:\n"
        f"▸ Point collection system\n"
        f"▸ Leaderboard ranking\n"
        f"▸ Dashboard access\n"
        f"▸ Future airdrop eligibility\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"The Covenant recognizes you, Gentleman.\n\n"
        f"Next: /claim to get your daily video!"
    )


# REMOVED: /connect command - social username collection removed for simplicity


async def claim(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /claim command to get daily video"""
    user = update.effective_user

    # Check maintenance mode first
    if await db.is_maintenance_mode():
        message = await db.get_maintenance_message()
        await update.message.reply_text(message)
        return

    # Check if claims are enabled
    if not await db.is_claims_enabled():
        await update.message.reply_text(
            "⏸️ Video claims are temporarily paused.\n\n"
            "Please check back later or follow our Telegram channel for updates!"
        )
        return

    # Check if user exists
    db_user = await db.get_user_by_telegram_id(user.id)
    if not db_user:
        await update.message.reply_text(
            "Please complete /start first to link your account."
        )
        return

    # Check if already claimed today
    if await db.has_claimed_today(db_user["id"]):
        # Get today's claim to check submissions
        todays_claim = await db.get_todays_claim(db_user["id"])
        video_id = todays_claim.get("video_id") if todays_claim else None
        submitted = await db.get_user_submissions_for_video(db_user["id"], video_id) if video_id else []

        # Check if there are remaining platforms
        remaining = [p for p in config.SUPPORTED_PLATFORMS if p not in submitted]

        if remaining:
            keyboard = get_submit_buttons(submitted)
            await update.message.reply_text(
                f"You've already claimed today's video!\n\n"
                f"Earn more points by submitting your post links:\n\n"
                f"Each platform = +{config.POINTS_SUBMIT} points",
                reply_markup=keyboard
            )
        else:
            await update.message.reply_text(
                f"You've claimed today's video and submitted to all platforms!\n\n"
                f"Come back tomorrow for a fresh video."
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

    # Create claim record (with telegram_id for points)
    await db.create_claim(db_user["id"], video["id"], user.id)

    # Store video_id for later /submit
    context.user_data['last_claimed_video_id'] = video["id"]

    # Send initial message with detailed platform instructions
    await update.message.reply_text(
        f"🎬 Your daily video is ready! (+{config.POINTS_CLAIM} pts)\n\n"
        f"━━━ HOW TO POST ━━━\n\n"
        f"1️⃣ SAVE the video below\n"
        f"2️⃣ POST on your socials\n"
        f"3️⃣ TAP button to submit link\n\n"
        f"━━━ POSTING GUIDE BY PLATFORM ━━━\n\n"
        f"📱 INSTAGRAM (strict on crypto)\n"
        f"✅ Post as REEL ← this counts!\n"
        f"✅ Add to Stories 2-4 hrs later\n"
        f"✅ Caption: \"vibes\" \"check this\"\n"
        f"✅ 3-5 hashtags IN the caption\n"
        f"❌ NO: \"profit\" \"investment\" \"moon\"\n"
        f"❌ NO: price talk or promises\n\n"
        f"🎵 TIKTOK (strict on crypto)\n"
        f"✅ Upload normally, hook in 3 sec\n"
        f"✅ Best times: Tue-Thu, 2-5 PM\n"
        f"✅ Educational/fun angle works\n"
        f"❌ NO: financial claims or hype\n"
        f"❌ NO: \"buy\" \"invest\" \"100x\"\n\n"
        f"🐦 TWITTER/X (crypto friendly!)\n"
        f"✅ Upload native video\n"
        f"✅ CAN mention $YNTOYG, crypto\n"
        f"✅ Quote-tweet for extra reach\n"
        f"✅ Hype and community vibes OK\n"
        f"✅ Tag other crypto accounts\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    # Prepare video - prioritize telegram_file_id
    file_id = video.get("telegram_file_id")
    video_url = video.get("video_url")

    if file_id:
        # Download from Telegram, uniquify, and send
        try:
            # Download video from Telegram
            file = await context.bot.get_file(file_id)
            temp_dir = Path(tempfile.gettempdir()) / "yg_claim_temp"
            temp_dir.mkdir(parents=True, exist_ok=True)

            import uuid
            temp_path = temp_dir / f"claim_{uuid.uuid4().hex[:8]}.mp4"
            await file.download_to_drive(str(temp_path))

            # Uniquify the video
            success, result_path, metadata = await serve_unique_video(str(temp_path))

            if success and Path(result_path).exists():
                # Send uniquified video with random filename
                with open(result_path, 'rb') as f:
                    await update.message.reply_document(
                        document=f,
                        filename=generate_random_filename(),
                        caption="📥 Save this video to your device, then post it!"
                    )

                # Cleanup
                uniquifier = get_uniquifier()
                await uniquifier.cleanup(result_path)
                if temp_path.exists():
                    temp_path.unlink()

                logger.info(f"Served unique video to user {user.id}, metadata: {metadata.get('unique_id', 'N/A')}")
            else:
                # Fallback: send original file
                await update.message.reply_document(
                    document=file_id,
                    caption="📥 Save this video to your device, then post it!"
                )
                if temp_path.exists():
                    temp_path.unlink()
                logger.warning(f"Uniquification failed, sent original: {result_path}")

        except Exception as e:
            logger.error(f"Error processing video: {e}")
            # Fallback to direct file_id
            await update.message.reply_document(
                document=file_id,
                caption="📥 Save this video to your device, then post it!"
            )

        # Send submit buttons after video
        keyboard = get_submit_buttons()
        await update.message.reply_text(
            f"Posted the video? Submit your link:\n\n"
            f"Each platform = +{config.POINTS_SUBMIT} points",
            reply_markup=keyboard
        )

    elif video_url:
        # Legacy: URL-based video (uniquify from URL)
        try:
            success, result_path, metadata = await serve_unique_video(video_url)

            if success and Path(result_path).exists():
                with open(result_path, 'rb') as f:
                    await update.message.reply_document(
                        document=f,
                        filename=generate_random_filename(),
                        caption="📥 Save this video to your device, then post it!"
                    )
                uniquifier = get_uniquifier()
                await uniquifier.cleanup(result_path)
            else:
                # Fallback to direct URL
                await update.message.reply_document(
                    document=video_url,
                    caption="📥 Save this video to your device, then post it!"
                )
        except Exception as e:
            logger.error(f"Error with URL video: {e}")
            await update.message.reply_document(
                document=video_url,
                caption="📥 Save this video to your device, then post it!"
            )

        # Send submit buttons after video
        keyboard = get_submit_buttons()
        await update.message.reply_text(
            f"Posted the video? Submit your link:\n\n"
            f"Each platform = +{config.POINTS_SUBMIT} points",
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            "⚠️ Video file not available. Please contact admin."
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

    # Get the most recent video claimed by user
    video_id = context.user_data.get('last_claimed_video_id')

    # Check if already submitted to this platform for this video
    if video_id:
        submitted = await db.get_user_submissions_for_video(db_user["id"], video_id)
        if platform in submitted:
            await update.message.reply_text(
                f"❌ You already submitted a {config.PLATFORM_NAMES.get(platform, platform.title())} link for today's video!\n\n"
                f"Try a different platform to earn more points."
            )
            return

    # Create repost record (with telegram_id for points)
    await db.create_repost(db_user["id"], video_id, platform, post_url, user.id)

    # Get remaining platforms for "submit more" prompt
    submitted_now = await db.get_user_submissions_for_video(db_user["id"], video_id) if video_id else [platform]
    remaining = [p for p in config.SUPPORTED_PLATFORMS if p not in submitted_now]

    platform_name = config.PLATFORM_NAMES.get(platform, platform.title())

    if remaining:
        keyboard = get_submit_buttons(submitted_now)
        await update.message.reply_text(
            f"✅ {platform_name} submitted! +{config.POINTS_SUBMIT} points\n\n"
            f"Want to earn more? Post to other platforms:",
            reply_markup=keyboard
        )
    else:
        # All platforms submitted!
        total = config.POINTS_CLAIM + (config.POINTS_SUBMIT * len(config.SUPPORTED_PLATFORMS))
        await update.message.reply_text(
            f"✅ {platform_name} submitted! +{config.POINTS_SUBMIT} points\n\n"
            f"🎉 Amazing! You've posted to all platforms!\n\n"
            f"Today's total: +{total} points\n"
            f"• Claim: +{config.POINTS_CLAIM} pts\n"
            f"• TikTok: +{config.POINTS_SUBMIT} pts\n"
            f"• Instagram: +{config.POINTS_SUBMIT} pts\n"
            f"• Twitter/X: +{config.POINTS_SUBMIT} pts\n\n"
            f"See you tomorrow for another video!"
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

    points = db_user.get('gentleman_score', 0)
    claims = db_user.get('total_claims', 0)
    streak = db_user.get('streak_count', 0)

    max_daily = config.POINTS_CLAIM + (config.POINTS_SUBMIT * len(config.SUPPORTED_PLATFORMS))

    await update.message.reply_text(
        f"📊 Your Stats, Gentleman\n\n"
        f"⭐ Points: {points}\n"
        f"📹 Videos Claimed: {claims}\n"
        f"🔥 Streak: {streak} days\n\n"
        f"━━━ POINT SYSTEM ━━━\n"
        f"▸ Claim video: +{config.POINTS_CLAIM} pts\n"
        f"▸ Submit link: +{config.POINTS_SUBMIT} pts each\n"
        f"▸ Max per day: +{max_daily} pts\n\n"
        f"Keep claiming and posting! 🏆"
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
    max_daily = config.POINTS_CLAIM + (config.POINTS_SUBMIT * len(config.SUPPORTED_PLATFORMS))
    await update.message.reply_text(
        f"🎩 $YNTOYG - How It Works\n\n"
        f"1️⃣ /start - Begin your journey\n"
        f"2️⃣ /wallet <addr> - Connect Solana wallet\n"
        f"3️⃣ /claim - Get your daily video\n"
        f"4️⃣ Post the video on TikTok/IG/Twitter\n"
        f"5️⃣ Tap Submit buttons to earn points\n\n"
        f"📊 /mystats - View your progress\n"
        f"🏆 /leaderboard - See top performers\n\n"
        f"━━━ POINT SYSTEM ━━━\n"
        f"▸ Claim: +{config.POINTS_CLAIM} pts\n"
        f"▸ Each platform: +{config.POINTS_SUBMIT} pts\n"
        f"▸ Max daily: +{max_daily} pts!\n\n"
        f"Learn more: https://yntoyg.com\n"
        f"Community: https://t.me/yntoyg"
    )


# ============ ADMIN COMMANDS ============

@admin_only
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin dashboard"""
    settings = await db.get_bot_settings()

    status_emoji = "✅" if settings.get("claims_enabled") else "⏸️"
    maint_emoji = "🔧" if settings.get("maintenance_mode") else "✅"

    await update.message.reply_text(
        f"⚙️ Admin Dashboard\n\n"
        f"📊 Current Settings:\n"
        f"• Claims: {status_emoji} {'Enabled' if settings.get('claims_enabled') else 'Paused'}\n"
        f"• Max Claims/Day: {settings.get('max_claims_per_day', 1)}\n"
        f"• Maintenance: {maint_emoji} {'ON' if settings.get('maintenance_mode') else 'OFF'}\n"
        f"• Announcement: {settings.get('announcement') or '(none)'}\n\n"
        f"📋 Admin Commands:\n"
        f"/admin - Show this dashboard\n"
        f"/admin_pause - Pause video claims\n"
        f"/admin_resume - Resume video claims\n"
        f"/admin_maintenance <on|off> [message] - Toggle maintenance\n"
        f"/admin_announce <message> - Set announcement\n"
        f"/admin_limits <number> - Set max claims per day\n"
        f"/admin_stats - Show bot statistics\n\n"
        f"📹 Video Management:\n"
        f"/addvideo - Add single video\n"
        f"/bulkupload - Add multiple videos (then /done)\n"
        f"/listvideosadmin - List all videos"
    )


@admin_only
async def admin_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pause video claims"""
    await db.update_bot_setting("claims_enabled", False)
    logger.info(f"Claims PAUSED by admin {update.effective_user.id}")
    await update.message.reply_text(
        "⏸️ Video claims have been PAUSED.\n\n"
        "Users will see a 'claims paused' message.\n"
        "Use /admin_resume to enable claims again."
    )


@admin_only
async def admin_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resume video claims"""
    await db.update_bot_setting("claims_enabled", True)
    logger.info(f"Claims RESUMED by admin {update.effective_user.id}")
    await update.message.reply_text(
        "✅ Video claims have been RESUMED.\n\n"
        "Users can now claim videos again."
    )


@admin_only
async def admin_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle maintenance mode"""
    args = context.args

    if not args:
        await update.message.reply_text(
            "Usage: /admin_maintenance <on|off> [custom message]\n\n"
            "Examples:\n"
            "/admin_maintenance on\n"
            "/admin_maintenance on Updating videos, back in 30 min!\n"
            "/admin_maintenance off"
        )
        return

    mode = args[0].lower()
    if mode == "on":
        custom_message = " ".join(args[1:]) if len(args) > 1 else None
        updates = {"maintenance_mode": True}
        if custom_message:
            updates["maintenance_message"] = f"🔧 {custom_message}"
        await db.update_bot_settings(updates)
        logger.info(f"Maintenance mode ON by admin {update.effective_user.id}")
        await update.message.reply_text(
            "🔧 Maintenance mode is now ON.\n\n"
            "All user commands will show the maintenance message.\n"
            "Use /admin_maintenance off when done."
        )
    elif mode == "off":
        await db.update_bot_setting("maintenance_mode", False)
        logger.info(f"Maintenance mode OFF by admin {update.effective_user.id}")
        await update.message.reply_text(
            "✅ Maintenance mode is now OFF.\n\n"
            "Bot is back to normal operation."
        )
    else:
        await update.message.reply_text("Invalid option. Use 'on' or 'off'.")


@admin_only
async def admin_announce(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set or clear announcement"""
    args = context.args

    if not args:
        await db.update_bot_setting("announcement", "")
        await update.message.reply_text("✅ Announcement cleared.")
        return

    announcement = " ".join(args)
    await db.update_bot_setting("announcement", announcement)
    logger.info(f"Announcement set by admin {update.effective_user.id}: {announcement}")
    await update.message.reply_text(
        f"📢 Announcement set:\n\n{announcement}"
    )


@admin_only
async def admin_limits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Adjust claim limits"""
    args = context.args

    if not args or not args[0].isdigit():
        await update.message.reply_text(
            "Usage: /admin_limits <number>\n\n"
            "Example: /admin_limits 2 (allows 2 claims per day)\n"
            "Use 0 to effectively disable claims."
        )
        return

    new_limit = int(args[0])
    await db.update_bot_setting("max_claims_per_day", new_limit)
    logger.info(f"Max claims set to {new_limit} by admin {update.effective_user.id}")

    if new_limit == 0:
        await update.message.reply_text(
            "⚠️ Max claims set to 0 - this effectively disables claims.\n"
            "Users cannot claim any videos."
        )
    else:
        await update.message.reply_text(
            f"✅ Max claims per day set to: {new_limit}\n\n"
            f"Users can now claim up to {new_limit} video(s) daily."
        )


@admin_only
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show bot statistics"""
    # Get some basic stats from database
    try:
        users_result = db.supabase.table("users").select("id", count="exact").execute()
        videos_result = db.supabase.table("videos").select("id", count="exact").eq("is_active", True).execute()
        claims_today = db.supabase.table("daily_claims").select("id", count="exact").eq(
            "claim_date", db.date.today().isoformat()
        ).execute()

        user_count = users_result.count or 0
        video_count = videos_result.count or 0
        claims_count = claims_today.count or 0

        await update.message.reply_text(
            f"📊 Bot Statistics\n\n"
            f"👥 Total Users: {user_count:,}\n"
            f"🎬 Active Videos: {video_count}\n"
            f"📹 Claims Today: {claims_count:,}\n"
        )
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        await update.message.reply_text("Error fetching statistics. Check logs.")


@admin_only
async def addvideo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start add video flow - admin sends this command then forwards a video"""
    context.user_data["awaiting_video_upload"] = True
    context.user_data["bulk_upload_mode"] = False
    context.user_data["bulk_upload_count"] = 0
    await update.message.reply_text(
        "🎬 Add Video to Pool\n\n"
        "Now send me the video file as a DOCUMENT (not as video).\n"
        "This preserves original quality.\n\n"
        "To send as document:\n"
        "📎 Attach → File → Select video → Send\n\n"
        "💡 For multiple videos, use /bulkupload instead\n\n"
        "Cancel with /cancel"
    )


@admin_only
async def bulkupload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start bulk video upload mode - keep uploading until /done"""
    context.user_data["awaiting_video_upload"] = True
    context.user_data["bulk_upload_mode"] = True
    context.user_data["bulk_upload_count"] = 0
    await update.message.reply_text(
        "📦 BULK UPLOAD MODE\n\n"
        "Send multiple videos as DOCUMENTS.\n"
        "I'll add each one to the pool.\n\n"
        "To send as document:\n"
        "📎 Attach → File → Select video(s) → Send\n\n"
        "When done, send /done to finish.\n"
        "Cancel with /cancel"
    )


@admin_only
async def listvideosadmin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all videos with management options"""
    videos = await db.get_all_videos_admin()

    if not videos:
        await update.message.reply_text(
            "📹 No videos in pool.\n\n"
            "Use /addvideo to add videos."
        )
        return

    text = "📹 <b>Video Pool</b>\n\n"
    keyboard_buttons = []

    for i, video in enumerate(videos, 1):
        status = "✅" if video.get("is_active") else "⏸️"
        title = video.get("title", "Untitled")
        claims = video.get("times_claimed", 0)
        has_file_id = "📁" if video.get("telegram_file_id") else "🔗"
        vid_id = video.get("id", "")
        short_id = vid_id[:8] if vid_id else "?"

        text += f"{i}. {status} {has_file_id} {title}\n"
        text += f"   Claims: {claims} | ID: {short_id}...\n\n"

        # Add copy button for each video
        keyboard_buttons.append([
            InlineKeyboardButton(
                f"📋 Copy ID #{i}: {short_id}...",
                callback_data=f"copyid_{vid_id}"
            )
        ])

    text += "<b>Tap button to get copyable ID</b>\n\n"
    text += "<b>Commands:</b>\n"
    text += "/video_enable &lt;id&gt; - Enable video\n"
    text += "/video_disable &lt;id&gt; - Disable video\n"
    text += "/video_delete &lt;id&gt; - Delete video"

    reply_markup = InlineKeyboardMarkup(keyboard_buttons)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)


@admin_only
async def video_enable(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enable a video"""
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /video_enable <video_id>")
        return

    video_id = args[0]
    result = await db.toggle_video_active(video_id, True)
    if result:
        await update.message.reply_text(f"✅ Video {video_id[:8]}... enabled")
    else:
        await update.message.reply_text("❌ Video not found")


@admin_only
async def video_disable(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Disable a video"""
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /video_disable <video_id>")
        return

    video_id = args[0]
    result = await db.toggle_video_active(video_id, False)
    if result:
        await update.message.reply_text(f"⏸️ Video {video_id[:8]}... disabled")
    else:
        await update.message.reply_text("❌ Video not found")


@admin_only
async def video_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a video"""
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /video_delete <video_id>")
        return

    video_id = args[0]
    result = await db.delete_video(video_id)
    if result:
        await update.message.reply_text(f"🗑️ Video {video_id[:8]}... deleted")
    else:
        await update.message.reply_text("❌ Video not found")


@admin_only
async def dev(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dev command to test video download without incrementing claim counter"""
    user = update.effective_user

    # Get random video
    video = await db.get_random_active_video()
    if not video:
        await update.message.reply_text("❌ No videos available in pool.")
        return

    await update.message.reply_text(
        f"🧪 DEV TEST - Downloading video...\n\n"
        f"📹 {video.get('title', 'Untitled')}\n"
        f"🆔 {video.get('id', '')[:8]}...\n\n"
        f"⚠️ Claim counter NOT incremented"
    )

    # Prepare video - prioritize telegram_file_id
    file_id = video.get("telegram_file_id")

    if file_id:
        try:
            # Download video from Telegram
            file = await context.bot.get_file(file_id)
            temp_dir = Path(tempfile.gettempdir()) / "yg_claim_temp"
            temp_dir.mkdir(parents=True, exist_ok=True)

            import uuid
            temp_path = temp_dir / f"dev_{uuid.uuid4().hex[:8]}.mp4"
            await file.download_to_drive(str(temp_path))

            # Uniquify the video
            success, result_path, metadata = await serve_unique_video(str(temp_path))

            if success and Path(result_path).exists():
                random_name = generate_random_filename()
                # Send uniquified video with random filename
                with open(result_path, 'rb') as f:
                    await update.message.reply_document(
                        document=f,
                        filename=random_name,
                        caption=f"🧪 DEV TEST\n\n"
                                f"📁 Filename: {random_name}\n"
                                f"🔑 Unique ID: {metadata.get('unique_id', 'N/A')}\n"
                                f"⏱️ Timestamp: {metadata.get('timestamp', 'N/A')}"
                    )

                # Cleanup
                uniquifier = get_uniquifier()
                await uniquifier.cleanup(result_path)
                if temp_path.exists():
                    temp_path.unlink()

                logger.info(f"DEV: Served test video to admin {user.id}, metadata: {metadata.get('unique_id', 'N/A')}")
            else:
                # Fallback: send original file
                await update.message.reply_document(
                    document=file_id,
                    caption="🧪 DEV TEST - Uniquification failed, sent original"
                )
                if temp_path.exists():
                    temp_path.unlink()

        except Exception as e:
            logger.error(f"DEV: Error serving video: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    else:
        await update.message.reply_text("❌ Video has no telegram_file_id")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel current operation"""
    # Check if we were in bulk upload mode
    if context.user_data.get("bulk_upload_mode"):
        count = context.user_data.get("bulk_upload_count", 0)
        if count > 0:
            await update.message.reply_text(
                f"❌ Bulk upload cancelled.\n\n"
                f"📊 {count} video(s) were already added before cancel."
            )
        else:
            await update.message.reply_text("❌ Bulk upload cancelled.")
    else:
        await update.message.reply_text("Operation cancelled.")

    context.user_data.pop("awaiting_video_upload", None)
    context.user_data.pop("bulk_upload_mode", None)
    context.user_data.pop("bulk_upload_count", None)
    # REMOVED: context.user_data.pop("connecting_platform", None)


@admin_only
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """End bulk upload mode"""
    if not context.user_data.get("bulk_upload_mode"):
        await update.message.reply_text("No bulk upload in progress.")
        return

    count = context.user_data.get("bulk_upload_count", 0)

    # Clear all upload flags
    context.user_data.pop("awaiting_video_upload", None)
    context.user_data.pop("bulk_upload_mode", None)
    context.user_data.pop("bulk_upload_count", None)

    if count == 0:
        await update.message.reply_text(
            "📦 Bulk upload ended.\n\n"
            "No videos were uploaded."
        )
    else:
        await update.message.reply_text(
            f"📦 Bulk upload complete!\n\n"
            f"✅ {count} video(s) added to pool\n\n"
            f"Use /listvideosadmin to see all videos."
        )


# ============ CALLBACK HANDLERS ============

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button callbacks"""
    query = update.callback_query
    user = query.from_user

    # Handle "Complete Setup" button - user clicked after joining Covenant
    if query.data == "complete_setup":
        await query.answer()

        # Check if user already exists
        existing_user = await db.get_user_by_telegram_id(user.id)
        if existing_user:
            await query.edit_message_text(
                f"You're already set up!\n\n"
                f"Type /claim to get your daily video."
            )
            return

        # Check group membership
        is_covenant_member = await check_covenant_membership(user.id, context)

        # Get pending onboarding data
        pending = await db.get_pending_onboarding(user.id)

        if not pending:
            await query.edit_message_text(
                f"Session expired.\n\n"
                f"Please start over at https://yntoyg.com"
            )
            return

        if is_covenant_member:
            # User completed group join → Finish onboarding
            email = pending["email"]
            original_token = pending["original_token"]

            await db.create_user(email, user.id)
            await db.consume_magic_token(original_token)
            await db.delete_pending_onboarding(user.id)

            # Generate dashboard auth token
            dashboard_token = await db.generate_dashboard_token(email)
            dashboard_url = f"https://yntoyg.com/api/auth/verify?token={dashboard_token}"

            await query.edit_message_text(
                f"Welcome to the Covenant.\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"ACCOUNT ACTIVATED\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Your email ({email}) is now linked.\n\n"
                f"VIEW YOUR DASHBOARD\n"
                f"▸ {dashboard_url}\n\n"
                f"AVAILABLE COMMANDS\n\n"
                f"▸ /claim - Get your daily video (+{config.POINTS_CLAIM} pts)\n"
                f"▸ Submit links (+{config.POINTS_SUBMIT} pts each)\n"
                f"▸ /wallet <address> - Connect Solana wallet\n"
                f"▸ /mystats - View your stats\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"From YN to YG."
            )
        else:
            # Still not in group
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("I've Joined → Complete Setup", callback_data="complete_setup")]
            ])

            await query.edit_message_text(
                f"You haven't joined the Covenant yet.\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"1. Click here: {config.YNTOYG_PORTAL_LINK}\n"
                f"2. Complete the Safeguard verification\n"
                f"3. Return and tap the button again\n\n"
                f"━━━━━━━━━━━━━━━━━━━━",
                reply_markup=keyboard
            )
        return

    await query.answer()

    # Handle submit platform buttons
    if query.data.startswith("submit_"):
        platform = query.data.replace("submit_", "")

        if platform not in config.SUPPORTED_PLATFORMS:
            return

        # Check if user exists
        db_user = await db.get_user_by_telegram_id(user.id)
        if not db_user:
            await query.message.reply_text(
                "Please complete /start first to link your account."
            )
            return

        # Get video_id from today's claim
        todays_claim = await db.get_todays_claim(db_user["id"])
        if not todays_claim:
            await query.message.reply_text(
                "❌ No claim found for today.\n\n"
                "Use /claim to get your daily video first!"
            )
            return

        video_id = todays_claim.get("video_id")

        # Check if already submitted to this platform
        submitted = await db.get_user_submissions_for_video(db_user["id"], video_id)
        platform_name = config.PLATFORM_NAMES.get(platform, platform.title())

        if platform in submitted:
            await query.message.reply_text(
                f"❌ You already submitted a {platform_name} link for today's video!\n\n"
                f"Try a different platform to earn more points."
            )
            return

        # Store awaiting platform and video_id in user_data
        context.user_data['awaiting_submit_platform'] = platform
        context.user_data['last_claimed_video_id'] = video_id

        await query.message.reply_text(
            f"📎 Send your {platform_name} link:\n\n"
            f"Just paste the URL of your post."
        )
        return

    if query.data.startswith("copyid_"):
        # Admin wants to copy a video ID - send it as a standalone message
        video_id = query.data.replace("copyid_", "")
        await query.message.reply_text(
            f"<code>{video_id}</code>",
            parse_mode="HTML"
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages - URL submissions after button click"""
    user = update.effective_user
    text = update.message.text.strip() if update.message.text else ""

    # Check if awaiting platform submission
    awaiting_platform = context.user_data.get('awaiting_submit_platform')
    if not awaiting_platform:
        return

    # Clear the awaiting state
    context.user_data.pop('awaiting_submit_platform', None)

    # Check if user exists
    db_user = await db.get_user_by_telegram_id(user.id)
    if not db_user:
        await update.message.reply_text(
            "Please complete /start first to link your account."
        )
        return

    # Validate URL matches expected platform
    platform_pattern = config.URL_PATTERNS.get(awaiting_platform)
    platform_name = config.PLATFORM_NAMES.get(awaiting_platform, awaiting_platform.title())

    if not platform_pattern or not re.search(platform_pattern, text):
        # Check if it matches a different platform
        detected_platform = None
        for plat, pattern in config.URL_PATTERNS.items():
            if re.search(pattern, text):
                detected_platform = plat
                break

        if detected_platform:
            detected_name = config.PLATFORM_NAMES.get(detected_platform, detected_platform.title())
            await update.message.reply_text(
                f"❌ That looks like a {detected_name} link, not {platform_name}.\n\n"
                f"Please send a valid {platform_name} URL, or use the buttons to submit to a different platform."
            )
        else:
            await update.message.reply_text(
                f"❌ Invalid URL.\n\n"
                f"Please send a valid {platform_name} post URL.\n\n"
                f"Example formats:\n"
                f"• TikTok: https://tiktok.com/@user/video/123...\n"
                f"• Instagram: https://instagram.com/reel/ABC...\n"
                f"• Twitter: https://x.com/user/status/123..."
            )
        return

    # Get video_id
    video_id = context.user_data.get('last_claimed_video_id')

    # Check if already submitted to this platform
    if video_id:
        submitted = await db.get_user_submissions_for_video(db_user["id"], video_id)
        if awaiting_platform in submitted:
            await update.message.reply_text(
                f"❌ You already submitted a {platform_name} link for today's video!\n\n"
                f"Try a different platform to earn more points."
            )
            return

    # Create repost record
    await db.create_repost(db_user["id"], video_id, awaiting_platform, text, user.id)

    # Get remaining platforms for "submit more" prompt
    submitted_now = await db.get_user_submissions_for_video(db_user["id"], video_id) if video_id else [awaiting_platform]
    remaining = [p for p in config.SUPPORTED_PLATFORMS if p not in submitted_now]

    if remaining:
        keyboard = get_submit_buttons(submitted_now)
        await update.message.reply_text(
            f"✅ {platform_name} submitted! +{config.POINTS_SUBMIT} points\n\n"
            f"Want to earn more? Post to other platforms:",
            reply_markup=keyboard
        )
    else:
        # All platforms submitted!
        total = config.POINTS_CLAIM + (config.POINTS_SUBMIT * len(config.SUPPORTED_PLATFORMS))
        await update.message.reply_text(
            f"✅ {platform_name} submitted! +{config.POINTS_SUBMIT} points\n\n"
            f"🎉 Amazing! You've posted to all platforms!\n\n"
            f"Today's total: +{total} points\n"
            f"• Claim: +{config.POINTS_CLAIM} pts\n"
            f"• TikTok: +{config.POINTS_SUBMIT} pts\n"
            f"• Instagram: +{config.POINTS_SUBMIT} pts\n"
            f"• Twitter/X: +{config.POINTS_SUBMIT} pts\n\n"
            f"See you tomorrow for another video!"
        )


async def handle_video_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle video uploads (both document and video types) for admin upload flow"""
    user = update.effective_user

    # Check if admin is awaiting video upload
    if not context.user_data.get("awaiting_video_upload"):
        return

    # Verify admin
    if user.id not in config.ADMIN_USER_IDS:
        return

    # Handle both document and video message types
    document = update.message.document
    video = update.message.video

    if document:
        # Sent as document/file
        mime = document.mime_type or ""
        filename = document.file_name or "video.mp4"

        if not mime.startswith("video/") and not filename.lower().endswith(('.mp4', '.mov', '.webm')):
            await update.message.reply_text(
                "❌ Please send a video file (.mp4, .mov, .webm)"
            )
            return

        file_id = document.file_id
        title = Path(filename).stem.replace('_', ' ').replace('-', ' ').title()
    elif video:
        # Sent as video (Telegram auto-detected)
        file_id = video.file_id
        filename = video.file_name or f"video_{video.file_unique_id}.mp4"
        title = Path(filename).stem.replace('_', ' ').replace('-', ' ').title()
    else:
        await update.message.reply_text("Please send a video file.")
        return

    # Check if we're in bulk upload mode
    is_bulk = context.user_data.get("bulk_upload_mode", False)

    try:
        # Add to database
        video_record = await db.add_video_by_file_id(file_id, title)
        vid_id = video_record.get("id", "")[:8]

        if is_bulk:
            # Bulk mode: increment counter, show brief confirmation
            count = context.user_data.get("bulk_upload_count", 0) + 1
            context.user_data["bulk_upload_count"] = count
            await update.message.reply_text(
                f"✅ #{count} added: {title}\n"
                f"Send more or /done to finish"
            )
        else:
            # Single mode: clear flag, show full confirmation
            context.user_data.pop("awaiting_video_upload", None)
            context.user_data.pop("bulk_upload_mode", None)
            context.user_data.pop("bulk_upload_count", None)
            await update.message.reply_text(
                f"✅ Video added to pool!\n\n"
                f"📹 Title: {title}\n"
                f"🆔 ID: {vid_id}...\n"
                f"📁 File ID stored\n"
                f"✅ Status: Active\n\n"
                f"Use /listvideosadmin to see all videos."
            )

        logger.info(f"Video added by admin {user.id}: {video_record.get('id')}")

    except Exception as e:
        logger.error(f"Error adding video: {e}")
        await update.message.reply_text(f"❌ Error adding video: {str(e)}")


# ============ CHAT MEMBER HANDLER (Auto-detect group joins) ============

async def handle_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Auto-detect when users join the Covenant group.
    If they have pending onboarding, complete it and DM them.
    """
    # Only process chat_member updates
    if not update.chat_member:
        return

    chat_id = update.chat_member.chat.id

    # Only care about our Covenant group
    if chat_id != config.YNTOYG_COVENANT_GROUP_ID:
        return

    # Get old and new member status
    old_member = update.chat_member.old_chat_member
    new_member = update.chat_member.new_chat_member

    if not new_member:
        return

    old_status = old_member.status if old_member else None
    new_status = new_member.status

    # Status values that mean "is a member"
    member_statuses = [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]

    was_member = old_status in member_statuses
    is_member = new_status in member_statuses

    # Only care about: was NOT member → IS now member (user just joined)
    if was_member or not is_member:
        return

    user = new_member.user
    logger.info(f"Detected new member in Covenant group: {user.id} (@{user.username})")

    # Check if this user has pending onboarding
    pending = await db.get_pending_onboarding(user.id)

    if not pending:
        logger.info(f"User {user.id} joined group but has no pending onboarding - ignoring")
        return

    # Complete their registration automatically!
    email = pending["email"]
    original_token = pending["original_token"]

    try:
        await db.create_user(email, user.id)
        await db.consume_magic_token(original_token)
        await db.delete_pending_onboarding(user.id)

        # Generate dashboard token for instant website access
        dashboard_token = await db.generate_dashboard_token(email)
        dashboard_url = f"https://yntoyg.com/api/auth/verify?token={dashboard_token}"

        # Send DM to user confirming their activation
        await context.bot.send_message(
            chat_id=user.id,
            text=(
                f"🎉 <b>Welcome to the Covenant!</b>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>ACCOUNT ACTIVATED</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<i>We detected you joined the group.</i>\n"
                f"Your email <i>{email}</i> is now linked.\n\n"
                f"<b>📊 VIEW YOUR DASHBOARD</b>\n"
                f"▸ {dashboard_url}\n\n"
                f"<b>⚡ START EARNING</b>\n\n"
                f"▸ /claim — <i>Get your daily video (+{config.POINTS_CLAIM} pts)</i>\n\n"
                f"▸ Submit links — <i>+{config.POINTS_SUBMIT} pts each platform</i>\n\n"
                f"▸ /wallet — <i>Connect Solana wallet</i>\n\n"
                f"▸ /mystats — <i>View your stats</i>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>From YN to YG.</b>"
            ),
            parse_mode="HTML"
        )
        logger.info(f"Auto-completed onboarding for user {user.id} via group join detection")

    except Exception as e:
        logger.error(f"Error auto-completing onboarding for user {user.id}: {e}")


# ============ MAIN ============

def main() -> None:
    """Start the bot"""
    # Create application
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("wallet", wallet))
    # REMOVED: CommandHandler("connect", connect) - social username collection removed
    application.add_handler(CommandHandler("claim", claim))
    application.add_handler(CommandHandler("submit", submit))
    application.add_handler(CommandHandler("mystats", mystats))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("help", help_command))

    # Add admin command handlers
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CommandHandler("admin_pause", admin_pause))
    application.add_handler(CommandHandler("admin_resume", admin_resume))
    application.add_handler(CommandHandler("admin_maintenance", admin_maintenance))
    application.add_handler(CommandHandler("admin_announce", admin_announce))
    application.add_handler(CommandHandler("admin_limits", admin_limits))
    application.add_handler(CommandHandler("admin_stats", admin_stats))

    # Add video management handlers
    application.add_handler(CommandHandler("addvideo", addvideo))
    application.add_handler(CommandHandler("bulkupload", bulkupload))
    application.add_handler(CommandHandler("listvideosadmin", listvideosadmin))
    application.add_handler(CommandHandler("video_enable", video_enable))
    application.add_handler(CommandHandler("video_disable", video_disable))
    application.add_handler(CommandHandler("video_delete", video_delete))
    application.add_handler(CommandHandler("dev", dev))
    application.add_handler(CommandHandler("done", done))
    application.add_handler(CommandHandler("cancel", cancel))

    # Add callback handler for inline keyboards
    application.add_handler(CallbackQueryHandler(button_callback))

    # Add chat member handler for auto-detecting group joins
    application.add_handler(ChatMemberHandler(handle_chat_member_update, ChatMemberHandler.CHAT_MEMBER))

    # Add handlers for video uploads - supports both document AND video types
    application.add_handler(MessageHandler(filters.Document.ALL, handle_video_upload))
    application.add_handler(MessageHandler(filters.VIDEO, handle_video_upload))

    # Add message handler for connection flow
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start polling
    logger.info("Starting YG Video Claim Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
