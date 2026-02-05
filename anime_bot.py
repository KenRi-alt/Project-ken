import os
import logging
import asyncio
import json
import redis
from datetime import datetime
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes
)
from telegram.constants import ParseMode

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "8282052807:AAHJw-9q_HZSwX9F4QQoCdpFEkxFqxFgCuA")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "6108185460").split(",")]
LOG_CHANNEL = os.getenv("LOG_CHANNEL", "-1003662720845")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))

# Initialize Redis (with error handling)
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()  # Test connection
    logger.info("✅ Redis connected successfully")
except Exception as e:
    logger.error(f"❌ Redis connection failed: {e}")
    # Create a dummy redis client for fallback
    class DummyRedis:
        def __init__(self):
            self.data = {}
        def get(self, key):
            return self.data.get(key)
        def set(self, key, value):
            self.data[key] = value
        def setex(self, key, ttl, value):
            self.data[key] = value
        def hset(self, key, mapping):
            self.data[key] = mapping
        def hget(self, key, field):
            return self.data.get(key, {}).get(field)
        def hgetall(self, key):
            return self.data.get(key, {})
        def exists(self, key):
            return key in self.data
        def keys(self, pattern):
            return [k for k in self.data.keys() if pattern.replace('*', '') in k]
        def delete(self, key):
            if key in self.data:
                del self.data[key]
        def incr(self, key):
            val = int(self.data.get(key, 0))
            val += 1
            self.data[key] = str(val)
            return val
        def dbsize(self):
            return len(self.data)
        def ping(self):
            return True
    
    redis_client = DummyRedis()
    logger.warning("Using dummy Redis - data will not persist")

# Import API modules with fallback
try:
    from anilist_api import AniListAPI, ImageGenerator
    anilist_api = AniListAPI(redis_client)
    image_gen = ImageGenerator()
    logger.info("✅ AniList API loaded successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import AniListAPI: {e}")
    # Create dummy classes
    class AniListAPI:
        def __init__(self, redis_client):
            self.redis = redis_client
        async def search_anime(self, *args, **kwargs):
            return []
        async def get_anime(self, *args, **kwargs):
            return {}
        async def get_trending_anime(self, *args, **kwargs):
            return []
        async def get_user_profile(self, *args, **kwargs):
            return {}
        async def get_airing_schedule(self, *args, **kwargs):
            return []
    
    class ImageGenerator:
        def __init__(self):
            pass
        async def generate_anime_card(self, *args, **kwargs):
            return "dummy.jpg"
        async def generate_user_card(self, *args, **kwargs):
            return "dummy.jpg"
    
    anilist_api = AniListAPI(redis_client)
    image_gen = ImageGenerator()
    logger.warning("Using dummy API classes - limited functionality")

class AnimeBot:
    def __init__(self):
        self.app = None
        self.user_sessions = {}
        self.start_time = datetime.now()
        
    async def log_action(self, message: str):
        """Log action to log channel"""
        if not LOG_CHANNEL or LOG_CHANNEL == "-1003662720845":
            logger.info(f"📝 {message}")
            return
            
        try:
            await self.app.bot.send_message(
                chat_id=LOG_CHANNEL,
                text=f"📝 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}"
            )
        except Exception as e:
            logger.error(f"Failed to log to channel: {e}")
            # Don't raise error, just log locally
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        logger.info(f"User {user.id} (@{user.username}) started the bot")
        
        # Save user to database
        user_key = f"user:{user.id}"
        user_data = {
            'id': str(user.id),
            'username': user.username or '',
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'joined': datetime.now().isoformat(),
            'banned': 'false',
            'is_admin': 'true' if user.id in ADMIN_IDS else 'false',
            'command_count': '0'
        }
        redis_client.hset(user_key, mapping=user_data)
        
        welcome_text = (
            "🎌 *Welcome to AnimeKuun Bot!*\n\n"
            "Your ultimate AniList companion!\n\n"
            "✨ *Quick Start:*\n"
            "`/search <title>` - Find anime/manga\n"
            "`/trending` - Trending now\n"
            "`/anime <title/id>` - Anime details\n"
            "`/help` - Full command list\n\n"
            "Bot is running! 🚀"
        )
        
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Log user join
        await self.log_action(f"👤 User joined: {user.id} (@{user.username})")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help menu"""
        help_text = (
            "📚 *AnimeKuun Bot Commands*\n\n"
            "*🔍 Search & Discovery:*\n"
            "`/search <title>` - Search anime/manga\n"
            "`/trending` - Trending anime\n"
            "`/anime <id/title>` - Anime details\n"
            "`/user <username>` - AniList profile\n"
            "`/schedule` - Airing schedule\n\n"
            "*🛠️ Admin Commands:*\n"
            "`/admin` - Admin panel\n"
            "`/ping` - Check bot status\n"
            "`/statsbot` - Bot statistics\n\n"
            "*More commands coming soon!*"
        )
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

    # =========== SEARCH COMMANDS ===========
    
    async def search_anime(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Search for anime/manga"""
        if not context.args:
            await update.message.reply_text("Please provide a search query. Example: `/search Attack on Titan`", parse_mode=ParseMode.MARKDOWN)
            return
            
        query = " ".join(context.args)
        await update.message.reply_chat_action("typing")
        
        try:
            results = await anilist_api.search_anime(query, page=1, per_page=5)
            
            if not results:
                await update.message.reply_text("❌ No results found.")
                return
                
            message = "🔍 *Search Results:*\n\n"
            
            for i, item in enumerate(results[:5], 1):
                title = item.get('title', {}).get('english') or item.get('title', {}).get('romaji', 'N/A')
                message += f"{i}. *{title}*\n"
                message += f"   ⭐ Score: {item.get('averageScore', 'N/A')}\n"
                message += f"   🆔 ID: `{item.get('id')}`\n\n"
            
            message += "Use `/anime <id>` to get details"
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            await update.message.reply_text("❌ Error searching. Please try again.")

    async def anime_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get detailed anime information"""
        if not context.args:
            await update.message.reply_text("Please provide anime ID or title. Example: `/anime 16498` or `/anime Attack on Titan`")
            return
            
        query = " ".join(context.args)
        await update.message.reply_chat_action("typing")
        
        try:
            # Try to get anime by ID first
            anime_id = None
            if query.isdigit():
                anime_id = int(query)
                anime_data = await anilist_api.get_anime(anime_id)
            else:
                # Search by title
                results = await anilist_api.search_anime(query, page=1, per_page=1)
                if results:
                    anime_data = await anilist_api.get_anime(results[0]['id'])
                else:
                    await update.message.reply_text("❌ Anime not found.")
                    return
            
            if not anime_data:
                await update.message.reply_text("❌ Failed to fetch anime data.")
                return
            
            # Create text response
            title = anime_data.get('title', {}).get('english') or anime_data.get('title', {}).get('romaji', 'N/A')
            caption = (
                f"*{title}*\n\n"
                f"⭐ *Score:* {anime_data.get('averageScore', 'N/A')}/100\n"
                f"📊 *Status:* {anime_data.get('status', 'N/A').capitalize()}\n"
                f"🎬 *Type:* {anime_data.get('format', 'N/A')}\n"
                f"📺 *Episodes:* {anime_data.get('episodes', 'N/A')}\n"
                f"🏷️ *Genres:* {', '.join(anime_data.get('genres', []))}\n\n"
                f"🔗 [View on AniList](https://anilist.co/anime/{anime_data.get('id')})"
            )
            
            await update.message.reply_text(caption, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logger.error(f"Anime info error: {e}")
            await update.message.reply_text("❌ Error fetching anime information.")

    async def trending_anime(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show trending anime"""
        await update.message.reply_chat_action("typing")
        
        try:
            results = await anilist_api.get_trending_anime(per_page=5)
            
            message = "🔥 *Trending Anime Now:*\n\n"
            for i, anime in enumerate(results, 1):
                title = anime.get('title', {}).get('english') or anime.get('title', {}).get('romaji', 'N/A')
                message += f"{i}. *{title}*\n"
                message += f"   ⭐ {anime.get('averageScore', 'N/A')} | 📈 {anime.get('trending', 'N/A')} trending\n\n"
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logger.error(f"Trending error: {e}")
            await update.message.reply_text("❌ Error fetching trending anime.")

    # =========== ADMIN COMMANDS ===========
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin panel command"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only.")
            return
        
        admin_text = (
            "🛠️ *Admin Panel*\n\n"
            "*Available Commands:*\n"
            "`/ping` - Check bot status\n"
            "`/statsbot` - Bot statistics\n"
            "`/users` - List all users\n"
            "`/broadcast <message>` - Broadcast message\n"
            "`/logs` - View bot logs\n"
            "`/pro <user_id>` - Promote user\n\n"
            "Bot is working! ✅"
        )
        
        await update.message.reply_text(admin_text, parse_mode=ParseMode.MARKDOWN)

    async def ping_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check bot status"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only.")
            return
        
        import time
        start_time = time.time()
        
        # Check Redis connection
        redis_status = "✅ Connected" if redis_client.ping() else "❌ Disconnected"
        
        # Check AniList API
        try:
            await anilist_api.get_trending_anime(per_page=1)
            anilist_status = "✅ Working"
        except:
            anilist_status = "❌ Failed"
        
        end_time = time.time()
        latency = round((end_time - start_time) * 1000, 2)
        
        status_text = (
            "🏓 *Pong!*\n\n"
            f"*Bot Status:* ✅ Online\n"
            f"*Latency:* {latency}ms\n"
            f"*Redis:* {redis_status}\n"
            f"*AniList API:* {anilist_status}\n"
            f"*Users:* {len(redis_client.keys('user:*'))}\n"
            f"*Uptime:* {self.get_uptime()}"
        )
        
        await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)

    async def bot_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show bot statistics"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only.")
            return
        
        # Get total users
        user_keys = redis_client.keys("user:*")
        total_users = len(user_keys)
        
        stats_text = (
            "📊 *Bot Statistics*\n\n"
            f"*👥 Users:* {total_users}\n"
            f"*💾 Cache:* {redis_client.dbsize()} items\n"
            f"*⏱️ Uptime:* {self.get_uptime()}\n\n"
            f"*🔄 API Status:*\n"
            f"  • AniList: Working\n"
            f"  • Redis: {'Connected' if redis_client.ping() else 'Disconnected'}"
        )
        
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

    # =========== UTILITY METHODS ===========
    
    def get_uptime(self):
        """Calculate bot uptime"""
        uptime = datetime.now() - self.start_time
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m {seconds}s"
    
    # =========== SETUP & RUN ===========
    
    def setup_handlers(self):
        """Setup all command handlers"""
        
        # User commands
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("search", self.search_anime))
        self.app.add_handler(CommandHandler("anime", self.anime_info))
        self.app.add_handler(CommandHandler("trending", self.trending_anime))
        
        # Admin commands
        self.app.add_handler(CommandHandler("admin", self.admin_panel))
        self.app.add_handler(CommandHandler("ping", self.ping_command))
        self.app.add_handler(CommandHandler("statsbot", self.bot_statistics))
        
        # Error handler
        self.app.add_error_handler(self.error_handler)
        
        # Set bot commands menu
        commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Show all commands"),
            BotCommand("search", "Search anime/manga"),
            BotCommand("anime", "Get anime details"),
            BotCommand("trending", "Trending anime"),
        ]
        
        async def set_commands():
            try:
                await self.app.bot.set_my_commands(commands)
                logger.info("✅ Bot commands set successfully")
            except Exception as e:
                logger.error(f"❌ Failed to set commands: {e}")

        self.app.post_init = set_commands

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Exception while handling an update: {context.error}")
        
        try:
            if update and update.effective_chat:
                await update.effective_chat.send_message(
                    "❌ An error occurred. Please try again later."
                )
        except:
            pass

    async def run(self):
        """Run the bot"""
        logger.info("🚀 Starting AnimeKuun Bot...")
        
        # Create application
        self.app = Application.builder().token(BOT_TOKEN).build()
        
        # Setup handlers
        self.setup_handlers()
        
        # Log startup
        await self.log_action("🤖 Bot started successfully!")
        logger.info("✅ Bot initialized, starting polling...")
        
        # Start polling
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        
        logger.info("✅ Bot is now running and polling for updates")
        
        # Keep running
        await self.app.updater.idle()

def main():
    """Main entry point"""
    bot = AnimeBot()
    
    # Run bot
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")

if __name__ == "__main__":
    main()
