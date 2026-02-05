import os
import logging
import asyncio
import json
import redis
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, ChatMember
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ChatMemberHandler
)
from telegram.constants import ParseMode, ChatType, ChatMemberStatus
from telegram.error import TelegramError

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "8282052807:AAHJw-9q_HZSwX9F4QQoCdpFEkxFqxFgCuA")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "6108185460").split(",")]
LOG_CHANNEL = os.getenv("LOG_CHANNEL", "-1003662720845")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))
MAX_REQUESTS_PER_MINUTE = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "30"))

# Initialize Redis
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    logger.info("✅ Redis connected")
except Exception as e:
    logger.error(f"❌ Redis failed: {e}")
    # Fallback to in-memory storage
    class MemoryStorage:
        def __init__(self):
            self.data = {}
            self.expiry = {}
        def get(self, key):
            if key in self.expiry and datetime.now() > self.expiry[key]:
                del self.data[key]
                del self.expiry[key]
                return None
            return self.data.get(key)
        def set(self, key, value, ex=None):
            self.data[key] = value
            if ex:
                self.expiry[key] = datetime.now() + timedelta(seconds=ex)
        def setex(self, key, ttl, value):
            self.set(key, value, ex=ttl)
        def hset(self, key, mapping=None, **kwargs):
            if key not in self.data:
                self.data[key] = {}
            if mapping:
                self.data[key].update(mapping)
            self.data[key].update(kwargs)
        def hget(self, key, field):
            return self.data.get(key, {}).get(field)
        def hgetall(self, key):
            return self.data.get(key, {}).copy()
        def exists(self, key):
            return key in self.data
        def keys(self, pattern):
            pattern = pattern.replace('*', '.*')
            return [k for k in self.data.keys() if re.match(pattern, k)]
        def delete(self, *keys):
            for key in keys:
                if key in self.data:
                    del self.data[key]
                if key in self.expiry:
                    del self.expiry[key]
        def incr(self, key):
            val = int(self.get(key) or 0)
            val += 1
            self.set(key, str(val))
            return val
        def dbsize(self):
            return len(self.data)
        def ping(self):
            return True
        def sadd(self, key, *values):
            if key not in self.data:
                self.data[key] = set()
            for value in values:
                self.data[key].add(value)
        def smembers(self, key):
            return self.data.get(key, set()).copy()
        def srem(self, key, *values):
            if key in self.data:
                for value in values:
                    self.data[key].discard(value)
        def zadd(self, key, mapping, **kwargs):
            if key not in self.data:
                self.data[key] = {}
            self.data[key].update(mapping)
        def zrange(self, key, start, end, withscores=False, desc=False):
            if key not in self.data:
                return []
            items = sorted(self.data[key].items(), key=lambda x: x[1], reverse=desc)
            if withscores:
                return items[start:end]
            return [k for k, v in items[start:end]]
    
    redis_client = MemoryStorage()
    logger.warning("Using memory storage - data will reset on restart")

# Import API
try:
    from anilist_api import AniListAPI, ImageGenerator
    anilist_api = AniListAPI(redis_client)
    image_gen = ImageGenerator()
except ImportError as e:
    logger.error(f"Failed to import modules: {e}")
    # Create minimal fallback
    class AniListAPI:
        def __init__(self, rc): self.redis = rc
        async def search_anime(self, *a, **k): return []
        async def get_anime(self, *a, **k): return {}
        async def get_trending_anime(self, *a, **k): return []
        async def get_popular_anime(self, *a, **k): return []
        async def get_seasonal_anime(self, *a, **k): return []
        async def get_upcoming_anime(self, *a, **k): return []
        async def get_airing_schedule(self, *a, **k): return []
        async def search_manga(self, *a, **k): return []
        async def get_manga(self, *a, **k): return {}
        async def search_character(self, *a, **k): return []
        async def get_character(self, *a, **k): return {}
        async def search_staff(self, *a, **k): return []
        async def search_studio(self, *a, **k): return []
        async def get_user_profile(self, *a, **k): return {}
        async def get_user_list(self, *a, **k): return []
        async def get_top_anime(self, *a, **k): return []
        async def get_top_manga(self, *a, **k): return []
        async def get_random_anime(self, *a, **k): return {}
        async def get_anime_news(self, *a, **k): return []
        async def get_anime_recommendations(self, *a, **k): return []
        async def get_character_birthdays(self, *a, **k): return []
        async def get_anime_stats(self, *a, **k): return {}
        async def get_genre_stats(self, *a, **k): return []
        async def get_anime_relations(self, *a, **k): return []
        async def get_anime_characters(self, *a, **k): return []
        async def get_anime_staff(self, *a, **k): return []
        async def get_anime_reviews(self, *a, **k): return []
        async def get_anime_trailer(self, *a, **k): return {}
        async def close(self): pass
    
    class ImageGenerator:
        def __init__(self): pass
        async def generate_anime_card(self, *a, **k): return None
        async def generate_user_card(self, *a, **k): return None
        async def generate_character_card(self, *a, **k): return None
    
    anilist_api = AniListAPI(redis_client)
    image_gen = ImageGenerator()

class AnimeBot:
    def __init__(self):
        self.app = None
        self.start_time = datetime.now()
        self.maintenance = False
        self.rate_limits = {}
        
    # =========== UTILITY FUNCTIONS ===========
    
    async def log_action(self, message: str):
        """Log action to log channel"""
        try:
            if LOG_CHANNEL:
                await self.app.bot.send_message(
                    chat_id=LOG_CHANNEL,
                    text=f"📝 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}",
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            logger.error(f"Log channel error: {e}")
    
    def check_rate_limit(self, user_id: int) -> bool:
        """Check if user is rate limited"""
        key = f"rate:{user_id}"
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        requests = redis_client.zrange(key, 0, -1, withscores=True)
        requests = [(user, ts) for user, ts in requests if ts > minute_ago.timestamp()]
        
        if len(requests) >= MAX_REQUESTS_PER_MINUTE:
            return False
        
        redis_client.zadd(key, {str(now.timestamp()): now.timestamp()})
        redis_client.expire(key, 120)
        return True
    
    def format_time(self, seconds: int) -> str:
        """Format seconds to human readable time"""
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:
            parts.append(f"{secs}s")
        
        return " ".join(parts)
    
    def paginate_list(self, items: List, page: int, per_page: int = 10) -> Tuple[List, int]:
        """Paginate a list"""
        total = len(items)
        total_pages = (total + per_page - 1) // per_page
        
        if page < 1:
            page = 1
        elif page > total_pages:
            page = total_pages
        
        start = (page - 1) * per_page
        end = start + per_page
        
        return items[start:end], total_pages
    
    # =========== USER COMMAND HANDLERS ===========
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command"""
        user = update.effective_user
        chat = update.effective_chat
        
        # Check rate limit
        if not self.check_rate_limit(user.id):
            await update.message.reply_text("⚠️ Too many requests. Please wait a minute.")
            return
        
        # Update user stats
        user_key = f"user:{user.id}"
        user_data = {
            'id': str(user.id),
            'username': user.username or '',
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'language': user.language_code or 'en',
            'joined': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat(),
            'command_count': '0',
            'is_banned': 'false',
            'is_admin': 'true' if user.id in ADMIN_IDS else 'false'
        }
        redis_client.hset(user_key, mapping=user_data)
        
        # Update group stats if in group
        if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            group_key = f"group:{chat.id}"
            group_data = {
                'id': str(chat.id),
                'title': chat.title or '',
                'type': chat.type,
                'members': str(chat.get_member_count()),
                'last_active': datetime.now().isoformat()
            }
            redis_client.hset(group_key, mapping=group_data)
            redis_client.sadd('groups', chat.id)
        
        welcome_text = (
            "🎌 <b>Welcome to AnimeKuun Bot!</b>\n\n"
            "Your ultimate AniList companion with <b>50+ commands</b>!\n\n"
            "✨ <b>Quick Start:</b>\n"
            "• <code>/search Attack on Titan</code> - Search anime\n"
            "• <code>/trending</code> - Trending now\n"
            "• <code>/schedule</code> - Airing schedule\n"
            "• <code>/topanime</code> - Top rated anime\n"
            "• <code>/help</code> - Full command list\n\n"
            "💬 <b>Works in groups too!</b>\n"
            "Try me in any group chat!\n\n"
            "Made with ❤️ for anime fans worldwide!"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔍 Search Anime", switch_inline_query_current_chat="search ")],
            [InlineKeyboardButton("📊 My Stats", callback_data="stats_me"),
             InlineKeyboardButton("🌟 Trending", callback_data="trending")],
            [InlineKeyboardButton("📚 Commands", callback_data="help_menu"),
             InlineKeyboardButton("⚙️ Settings", callback_data="settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        
        await self.log_action(f"👤 User {user.id} (@{user.username}) started bot")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command with categories"""
        user = update.effective_user
        args = context.args
        
        if args and args[0].lower() == 'admin' and user.id in ADMIN_IDS:
            await self.admin_help(update, context)
            return
        
        help_text = (
            "📚 <b>AnimeKuun Bot Commands</b>\n\n"
            
            "<b>🔍 Search & Discovery:</b>\n"
            "• <code>/search</code> <i>title</i> - Search anime/manga\n"
            "• <code>/trending</code> - Trending anime\n"
            "• <code>/popular</code> - Popular this season\n"
            "• <code>/upcoming</code> - Upcoming releases\n"
            "• <code>/seasonal</code> - Current season\n"
            "• <code>/character</code> <i>name</i> - Search characters\n"
            "• <code>/staff</code> <i>name</i> - Search creators\n"
            "• <code>/studio</code> <i>name</i> - Search studios\n"
            "• <code>/genre</code> <i>genre</i> - Search by genre\n\n"
            
            "<b>🎬 Anime Information:</b>\n"
            "• <code>/anime</code> <i>id/title</i> - Anime details\n"
            "• <code>/manga</code> <i>id/title</i> - Manga details\n"
            "• <code>/char</code> <i>id/name</i> - Character details\n"
            "• <code>/relations</code> <i>id</i> - Related media\n"
            "• <code>/recommend</code> <i>id</i> - Recommendations\n"
            "• <code>/reviews</code> <i>id</i> - User reviews\n"
            "• <code>/trailer</code> <i>id</i> - YouTube trailer\n"
            "• <code>/stats</code> <i>id</i> - Score statistics\n\n"
            
            "<b>👥 User & Lists:</b>\n"
            "• <code>/user</code> <i>username</i> - AniList profile\n"
            "• <code>/list</code> <i>username</i> - User's anime list\n"
            "• <code>/favorites</code> <i>username</i> - User favorites\n"
            "• <code>/compare</code> <i>user1 user2</i> - Compare lists\n"
            "• <code>/watching</code> <i>username</i> - Currently watching\n\n"
            
            "<b>📊 Statistics & Charts:</b>\n"
            "• <code>/topanime</code> - Top-rated anime\n"
            "• <code>/topmanga</code> - Top-rated manga\n"
            "• <code>/topcharacters</code> - Popular characters\n"
            "• <code>/topstudios</code> - Top studios\n"
            "• <code>/genrestats</code> - Genre statistics\n"
            "• <code>/scorestats</code> <i>id</i> - Score distribution\n"
            "• <code>/yearstats</code> <i>year</i> - Anime by year\n\n"
            
            "<b>⚙️ Utilities:</b>\n"
            "• <code>/schedule</code> - Today's airing\n"
            "• <code>/airing</code> <i>id</i> - Next episode\n"
            "• <code>/random</code> - Random anime\n"
            "• <code>/similar</code> <i>id</i> - Similar anime\n"
            "• <code>/quote</code> - Random anime quote\n"
            "• <code>/birthdays</code> - Character birthdays\n"
            "• <code>/news</code> <i>id</i> - Anime news\n"
            "• <code>/calendar</code> - Monthly calendar\n\n"
            
            "<b>🛠️ Admin Commands:</b>\n"
            "• <code>/admin</code> - Admin panel\n"
            "• <code>/help admin</code> - Admin commands\n\n"
            
            "💡 <b>Tip:</b> Use <code>@AnimeKuun_bot search</code> in any chat for inline search!"
        )
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)
    
    async def admin_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin help command"""
        admin_text = (
            "🛠️ <b>Admin Commands</b>\n\n"
            
            "<b>User Management:</b>\n"
            "• <code>/users</code> [page] - List all users\n"
            "• <code>/ban</code> <i>user_id</i> - Ban user\n"
            "• <code>/unban</code> <i>user_id</i> - Unban user\n"
            "• <code>/pro</code> <i>user_id</i> - Promote to admin\n"
            "• <code>/unpro</code> <i>user_id</i> - Demote admin\n"
            "• <code>/warn</code> <i>user_id reason</i> - Warn user\n"
            "• <code>/unwarn</code> <i>user_id</i> - Remove warnings\n\n"
            
            "<b>Group Management:</b>\n"
            "• <code>/groups</code> [page] - List all groups\n"
            "• <code>/gban</code> <i>group_id</i> - Ban group\n"
            "• <code>/ungban</code> <i>group_id</i> - Unban group\n"
            "• <code>/gsettings</code> <i>group_id</i> - Group settings\n\n"
            
            "<b>Bot Controls:</b>\n"
            "• <code>/ping</code> - Check bot status\n"
            "• <code>/statsbot</code> - Bot statistics\n"
            "• <code>/broadcast</code> <i>message</i> - Broadcast to users\n"
            "• <code>/announce</code> <i>message</i> - Announce to groups\n"
            "• <code>/logs</code> [lines] - View bot logs\n"
            "• <code>/backup</code> - Backup data\n"
            "• <code>/restart</code> - Restart bot\n"
            "• <code>/maintenance</code> <i>on/off</i> - Toggle maintenance\n"
            "• <code>/settings</code> - Bot settings\n\n"
            
            "<b>Configuration:</b>\n"
            "• <code>/config get</code> <i>key</i> - Get config\n"
            "• <code>/config set</code> <i>key value</i> - Set config\n"
            "• <code>/config list</code> - List configs\n"
            "• <code>/config reset</code> <i>key</i> - Reset config\n\n"
            
            "<b>Miscellaneous:</b>\n"
            "• <code>/eval</code> <i>code</i> - Evaluate code\n"
            "• <code>/shell</code> <i>command</i> - Run shell command\n"
            "• <code>/export</code> - Export data\n"
            "• <code>/import</code> - Import data\n"
        )
        
        await update.message.reply_text(admin_text, parse_mode=ParseMode.HTML)
    
    # =========== ANIME COMMANDS ===========
    
    async def search_anime(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Search anime/manga"""
        if not context.args:
            await update.message.reply_text("Please provide a search query.\nExample: <code>/search Attack on Titan</code>", parse_mode=ParseMode.HTML)
            return
        
        query = " ".join(context.args)
        await update.message.reply_chat_action("typing")
        
        try:
            results = await anilist_api.search_anime(query, page=1, per_page=10)
            
            if not results:
                await update.message.reply_text("❌ No results found.")
                return
            
            message = "🔍 <b>Search Results:</b>\n\n"
            keyboard = []
            
            for i, item in enumerate(results[:10], 1):
                title = item.get('title', {}).get('english') or item.get('title', {}).get('romaji', 'N/A')
                score = item.get('averageScore', 'N/A')
                popularity = item.get('popularity', 'N/A')
                media_type = item.get('type', 'ANIME')
                
                message += f"{i}. <b>{title}</b>\n"
                message += f"   ⭐ {score} | 📊 #{popularity} | 🎬 {media_type}\n"
                message += f"   🆔 <code>{item.get('id')}</code>\n\n"
                
                keyboard.append([InlineKeyboardButton(
                    f"{i}. {title[:30]}...",
                    callback_data=f"anime_{item.get('id')}"
                )])
            
            # Add pagination buttons if needed
            if len(results) > 10:
                keyboard.append([
                    InlineKeyboardButton("⬅️ Previous", callback_data=f"search_prev_{query}_1"),
                    InlineKeyboardButton("Next ➡️", callback_data=f"search_next_{query}_2")
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            await update.message.reply_text("❌ Error searching. Please try again.")
    
    async def anime_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get detailed anime info"""
        if not context.args:
            await update.message.reply_text("Please provide anime ID or title.\nExample: <code>/anime 16498</code> or <code>/anime Attack on Titan</code>", parse_mode=ParseMode.HTML)
            return
        
        query = " ".join(context.args)
        await update.message.reply_chat_action("upload_photo")
        
        try:
            # Try to get by ID first
            if query.isdigit():
                anime_data = await anilist_api.get_anime(int(query))
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
            
            # Try to generate image card
            try:
                image_path = await image_gen.generate_anime_card(anime_data)
                if image_path and os.path.exists(image_path):
                    # Create inline keyboard
                    keyboard = [
                        [
                            InlineKeyboardButton("🎭 Characters", callback_data=f"chars_{anime_data['id']}"),
                            InlineKeyboardButton("👨‍💼 Staff", callback_data=f"staff_{anime_data['id']}")
                        ],
                        [
                            InlineKeyboardButton("🔗 Relations", callback_data=f"rel_{anime_data['id']}"),
                            InlineKeyboardButton("🌟 Similar", callback_data=f"rec_{anime_data['id']}")
                        ],
                        [
                            InlineKeyboardButton("📺 Trailer", callback_data=f"trailer_{anime_data['id']}"),
                            InlineKeyboardButton("📊 Reviews", callback_data=f"reviews_{anime_data['id']}")
                        ],
                        [
                            InlineKeyboardButton("📋 Add to List", url=f"https://anilist.co/anime/{anime_data['id']}")
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    # Prepare caption
                    title = anime_data.get('title', {}).get('english') or anime_data.get('title', {}).get('romaji', 'N/A')
                    caption = (
                        f"<b>{title}</b>\n\n"
                        f"⭐ <b>Score:</b> {anime_data.get('averageScore', 'N/A')}/100\n"
                        f"📊 <b>Popularity:</b> #{anime_data.get('popularity', 'N/A')}\n"
                        f"🎬 <b>Format:</b> {anime_data.get('format', 'N/A')}\n"
                        f"📺 <b>Episodes:</b> {anime_data.get('episodes', 'N/A')}\n"
                        f"📅 <b>Status:</b> {anime_data.get('status', 'N/A').capitalize()}\n"
                        f"🏷️ <b>Genres:</b> {', '.join(anime_data.get('genres', ['N/A']))}\n\n"
                        f"<i>{anime_data.get('description', 'No description available.')[:300]}...</i>"
                    )
                    
                    with open(image_path, 'rb') as photo:
                        await update.message.reply_photo(
                            photo=photo,
                            caption=caption,
                            parse_mode=ParseMode.HTML,
                            reply_markup=reply_markup
                        )
                    os.remove(image_path)
                    return
            except Exception as e:
                logger.error(f"Image generation failed: {e}")
                # Fall through to text-only response
            
            # Text-only fallback
            title = anime_data.get('title', {}).get('english') or anime_data.get('title', {}).get('romaji', 'N/A')
            message = (
                f"🎬 <b>{title}</b>\n\n"
                f"📝 <b>Description:</b>\n"
                f"{anime_data.get('description', 'No description available.')[:500]}...\n\n"
                f"⭐ <b>Score:</b> {anime_data.get('averageScore', 'N/A')}/100\n"
                f"📊 <b>Popularity:</b> #{anime_data.get('popularity', 'N/A')}\n"
                f"🎬 <b>Format:</b> {anime_data.get('format', 'N/A')}\n"
                f"📺 <b>Episodes:</b> {anime_data.get('episodes', 'N/A')}\n"
                f"⏱️ <b>Duration:</b> {anime_data.get('duration', 'N/A')} min\n"
                f"📅 <b>Status:</b> {anime_data.get('status', 'N/A').capitalize()}\n"
                f"🏷️ <b>Genres:</b> {', '.join(anime_data.get('genres', ['N/A']))}\n"
                f"🎞️ <b>Studios:</b> {', '.join([s.get('node', {}).get('name', 'N/A') for s in anime_data.get('studios', {}).get('edges', [])[:3]])}\n\n"
                f"🔗 <a href='https://anilist.co/anime/{anime_data['id']}'>View on AniList</a>"
            )
            
            await update.message.reply_text(message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            
        except Exception as e:
            logger.error(f"Anime info error: {e}")
            await update.message.reply_text("❌ Error fetching anime information.")
    
    async def trending_anime(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show trending anime"""
        await update.message.reply_chat_action("typing")
        
        try:
            results = await anilist_api.get_trending_anime(per_page=15)
            
            if not results:
                await update.message.reply_text("❌ No trending anime found.")
                return
            
            message = "🔥 <b>Trending Anime Now:</b>\n\n"
            
            for i, anime in enumerate(results[:15], 1):
                title = anime.get('title', {}).get('english') or anime.get('title', {}).get('romaji', 'N/A')
                score = anime.get('averageScore', 'N/A')
                trending = anime.get('trending', 'N/A')
                episodes = anime.get('episodes', 'N/A')
                
                message += f"{i}. <b>{title}</b>\n"
                message += f"   ⭐ {score} | 📈 {trending} trending | 📺 {episodes} eps\n"
                message += f"   🆔 <code>{anime.get('id')}</code>\n\n"
            
            await update.message.reply_text(message, parse_mode=ParseMode.HTML)
            
        except Exception as e:
            logger.error(f"Trending error: {e}")
            await update.message.reply_text("❌ Error fetching trending anime.")
    
    async def popular_anime(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show popular anime"""
        await update.message.reply_chat_action("typing")
        
        try:
            results = await anilist_api.get_popular_anime(per_page=15)
            
            message = "🌟 <b>Popular Anime:</b>\n\n"
            
            for i, anime in enumerate(results[:15], 1):
                title = anime.get('title', {}).get('english') or anime.get('title', {}).get('romaji', 'N/A')
                score = anime.get('averageScore', 'N/A')
                popularity = anime.get('popularity', 'N/A')
                
                message += f"{i}. <b>{title}</b>\n"
                message += f"   ⭐ {score} | 📊 #{popularity} | 🎬 {anime.get('format', 'N/A')}\n\n"
            
            await update.message.reply_text(message, parse_mode=ParseMode.HTML)
            
        except Exception as e:
            logger.error(f"Popular error: {e}")
            await update.message.reply_text("❌ Error fetching popular anime.")
    
    async def seasonal_anime(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current seasonal anime"""
        await update.message.reply_chat_action("typing")
        
        try:
            results = await anilist_api.get_seasonal_anime()
            
            message = "🌸 <b>Current Season Anime:</b>\n\n"
            
            for i, anime in enumerate(results[:15], 1):
                title = anime.get('title', {}).get('english') or anime.get('title', {}).get('romaji', 'N/A')
                score = anime.get('averageScore', 'N/A')
                status = anime.get('status', 'N/A').capitalize()
                
                message += f"{i}. <b>{title}</b>\n"
                message += f"   ⭐ {score} | 📅 {status} | 🎬 {anime.get('format', 'N/A')}\n\n"
            
            await update.message.reply_text(message, parse_mode=ParseMode.HTML)
            
        except Exception as e:
            logger.error(f"Seasonal error: {e}")
            await update.message.reply_text("❌ Error fetching seasonal anime.")
    
    async def airing_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show airing schedule"""
        await update.message.reply_chat_action("typing")
        
        try:
            schedule = await anilist_api.get_airing_schedule()
            
            message = "📺 <b>Today's Airing Schedule:</b>\n\n"
            current_time = datetime.now()
            
            for i, anime in enumerate(schedule[:15], 1):
                title = anime.get('media', {}).get('title', {}).get('english') or \
                       anime.get('media', {}).get('title', {}).get('romaji', 'N/A')
                episode = anime.get('episode', 'N/A')
                airing_at = anime.get('airingAt', 0)
                
                # Convert timestamp to time
                airing_time = datetime.fromtimestamp(airing_at)
                time_str = airing_time.strftime("%H:%M")
                
                # Calculate time until airing
                time_diff = airing_time - current_time
                hours = int(time_diff.total_seconds() // 3600)
                minutes = int((time_diff.total_seconds() % 3600) // 60)
                
                message += f"{i}. <b>{title}</b> - Ep {episode}\n"
                message += f"   ⏰ {time_str} (in {hours}h {minutes}m)\n\n"
            
            if len(schedule) > 15:
                message += f"📋 ... and {len(schedule) - 15} more episodes today"
            
            await update.message.reply_text(message, parse_mode=ParseMode.HTML)
            
        except Exception as e:
            logger.error(f"Schedule error: {e}")
            await update.message.reply_text("❌ Error fetching airing schedule.")
    
    async def top_anime(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show top anime"""
        page = int(context.args[0]) if context.args and context.args[0].isdigit() else 1
        
        await update.message.reply_chat_action("typing")
        
        try:
            results = await anilist_api.get_top_anime(page=page, per_page=15)
            
            message = f"🏆 <b>Top Anime (Page {page}):</b>\n\n"
            
            for i, anime in enumerate(results, 1):
                title = anime.get('title', {}).get('english') or anime.get('title', {}).get('romaji', 'N/A')
                score = anime.get('averageScore', 'N/A')
                year = anime.get('startDate', {}).get('year', 'N/A')
                
                message += f"{i}. <b>{title}</b>\n"
                message += f"   ⭐ {score} | 📅 {year} | 🎬 {anime.get('format', 'N/A')}\n\n"
            
            # Add pagination buttons
            keyboard = []
            if page > 1:
                keyboard.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"top_anime_{page-1}"))
            keyboard.append(InlineKeyboardButton("Next ➡️", callback_data=f"top_anime_{page+1}"))
            
            reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None
            await update.message.reply_text(message, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Top anime error: {e}")
            await update.message.reply_text("❌ Error fetching top anime.")
    
    async def random_anime(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get random anime"""
        await update.message.reply_chat_action("typing")
        
        try:
            genre = context.args[0] if context.args else None
            anime_data = await anilist_api.get_random_anime(genre)
            
            if not anime_data:
                await update.message.reply_text("❌ Failed to get random anime.")
                return
            
            title = anime_data.get('title', {}).get('english') or anime_data.get('title', {}).get('romaji', 'N/A')
            message = (
                f"🎲 <b>Random Anime Recommendation:</b>\n\n"
                f"🎬 <b>{title}</b>\n"
                f"⭐ <b>Score:</b> {anime_data.get('averageScore', 'N/A')}/100\n"
                f"📊 <b>Popularity:</b> #{anime_data.get('popularity', 'N/A')}\n"
                f"📺 <b>Episodes:</b> {anime_data.get('episodes', 'N/A')}\n"
                f"🏷️ <b>Genres:</b> {', '.join(anime_data.get('genres', ['N/A']))}\n\n"
                f"📝 {anime_data.get('description', 'No description available.')[:300]}...\n\n"
                f"🔗 <a href='https://anilist.co/anime/{anime_data['id']}'>View on AniList</a>"
            )
            
            await update.message.reply_text(message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            
        except Exception as e:
            logger.error(f"Random anime error: {e}")
            await update.message.reply_text("❌ Error getting random anime.")
    
    # =========== MANGA COMMANDS ===========
    
    async def search_manga(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Search manga"""
        if not context.args:
            await update.message.reply_text("Please provide a search query.\nExample: <code>/manga Berserk</code>", parse_mode=ParseMode.HTML)
            return
        
        query = " ".join(context.args)
        await update.message.reply_chat_action("typing")
        
        try:
            results = await anilist_api.search_manga(query, page=1, per_page=10)
            
            if not results:
                await update.message.reply_text("❌ No results found.")
                return
            
            message = "🔍 <b>Manga Search Results:</b>\n\n"
            
            for i, item in enumerate(results[:10], 1):
                title = item.get('title', {}).get('english') or item.get('title', {}).get('romaji', 'N/A')
                score = item.get('averageScore', 'N/A')
                chapters = item.get('chapters', 'N/A')
                
                message += f"{i}. <b>{title}</b>\n"
                message += f"   ⭐ {score} | 📖 {chapters} chapters\n"
                message += f"   🆔 <code>{item.get('id')}</code>\n\n"
            
            await update.message.reply_text(message, parse_mode=ParseMode.HTML)
            
        except Exception as e:
            logger.error(f"Manga search error: {e}")
            await update.message.reply_text("❌ Error searching manga.")
    
    # =========== USER PROFILE COMMANDS ===========
    
    async def user_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get AniList user profile"""
        if not context.args:
            await update.message.reply_text("Please provide AniList username.\nExample: <code>/user username</code>", parse_mode=ParseMode.HTML)
            return
        
        username = context.args[0]
        await update.message.reply_chat_action("upload_photo")
        
        try:
            user_data = await anilist_api.get_user_profile(username)
            
            if not user_data:
                await update.message.reply_text("❌ User not found.")
                return
            
            # Try to generate image card
            try:
                image_path = await image_gen.generate_user_card(user_data)
                if image_path and os.path.exists(image_path):
                    # Prepare caption
                    name = user_data.get('name', 'N/A')
                    about = user_data.get('about', 'No bio available.')[:200]
                    stats = user_data.get('statistics', {}).get('anime', {})
                    
                    caption = (
                        f"👤 <b>{name}</b>\n\n"
                        f"📊 <b>Anime Stats:</b>\n"
                        f"• Total: {stats.get('count', 0)} anime\n"
                        f"• Mean Score: {stats.get('meanScore', 0)}/100\n"
                        f"• Days Watched: {stats.get('minutesWatched', 0) / 1440:.1f} days\n\n"
                        f"📝 {about}...\n\n"
                        f"🔗 <a href='https://anilist.co/user/{username}'>View on AniList</a>"
                    )
                    
                    with open(image_path, 'rb') as photo:
                        await update.message.reply_photo(
                            photo=photo,
                            caption=caption,
                            parse_mode=ParseMode.HTML
                        )
                    os.remove(image_path)
                    return
            except Exception as e:
                logger.error(f"User card generation failed: {e}")
                # Fall through to text-only
            
            # Text-only fallback
            name = user_data.get('name', 'N/A')
            stats = user_data.get('statistics', {}).get('anime', {})
            message = (
                f"👤 <b>{name}</b>\n\n"
                f"📊 <b>Anime Statistics:</b>\n"
                f"• Total Anime: {stats.get('count', 0)}\n"
                f"• Mean Score: {stats.get('meanScore', 0)}/100\n"
                f"• Days Watched: {stats.get('minutesWatched', 0) / 1440:.1f} days\n"
                f"• Episodes Watched: {stats.get('episodesWatched', 0):,}\n\n"
                f"📅 <b>Account Created:</b>\n"
                f"• Donator Tier: {user_data.get('donatorTier', 0)}\n"
                f"• Last Updated: {datetime.fromtimestamp(user_data.get('updatedAt', 0)).strftime('%Y-%m-%d') if user_data.get('updatedAt') else 'N/A'}\n\n"
                f"🔗 <a href='https://anilist.co/user/{username}'>View Full Profile</a>"
            )
            
            await update.message.reply_text(message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            
        except Exception as e:
            logger.error(f"User profile error: {e}")
            await update.message.reply_text("❌ Error fetching user profile.")
    
    # =========== CHARACTER COMMANDS ===========
    
    async def search_character(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Search characters"""
        if not context.args:
            await update.message.reply_text("Please provide character name.\nExample: <code>/character Luffy</code>", parse_mode=ParseMode.HTML)
            return
        
        query = " ".join(context.args)
        await update.message.reply_chat_action("typing")
        
        try:
            results = await anilist_api.search_character(query, page=1, per_page=10)
            
            if not results:
                await update.message.reply_text("❌ No results found.")
                return
            
            message = "👤 <b>Character Search Results:</b>\n\n"
            
            for i, char in enumerate(results[:10], 1):
                name = char.get('name', {}).get('full', 'N/A')
                media = char.get('media', {}).get('edges', [])
                anime_name = media[0].get('node', {}).get('title', {}).get('romaji', 'N/A') if media else 'N/A'
                
                message += f"{i}. <b>{name}</b>\n"
                message += f"   📺 {anime_name}\n"
                message += f"   🆔 <code>{char.get('id')}</code>\n\n"
            
            await update.message.reply_text(message, parse_mode=ParseMode.HTML)
            
        except Exception as e:
            logger.error(f"Character search error: {e}")
            await update.message.reply_text("❌ Error searching characters.")
    
    # =========== ADMIN COMMANDS ===========
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin panel"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only.")
            return
        
        # Get bot stats
        total_users = len(redis_client.keys('user:*'))
        total_groups = len(redis_client.smembers('groups'))
        total_commands = redis_client.get('stats:total_commands') or 0
        
        admin_text = (
            f"🛠️ <b>Admin Panel</b>\n\n"
            f"📊 <b>Bot Statistics:</b>\n"
            f"• Users: {total_users}\n"
            f"• Groups: {total_groups}\n"
            f"• Commands: {total_commands}\n"
            f"• Uptime: {self.format_time(int((datetime.now() - self.start_time).total_seconds()))}\n\n"
            f"🔧 <b>Quick Commands:</b>\n"
            f"• <code>/ping</code> - Check bot status\n"
            f"• <code>/statsbot</code> - Detailed statistics\n"
            f"• <code>/users</code> - List all users\n"
            f"• <code>/groups</code> - List all groups\n"
            f"• <code>/broadcast</code> - Broadcast message\n"
            f"• <code>/logs</code> - View bot logs\n\n"
            f"⚙️ <b>Maintenance:</b>\n"
            f"• <code>/maintenance on/off</code>\n"
            f"• Current: {'🔴 ON' if self.maintenance else '🟢 OFF'}\n\n"
            f"📚 <code>/help admin</code> - Full admin commands"
        )
        
        keyboard = [
            [InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
             InlineKeyboardButton("👥 Users", callback_data="admin_users")],
            [InlineKeyboardButton("👥 Groups", callback_data="admin_groups"),
             InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"),
             InlineKeyboardButton("📜 Logs", callback_data="admin_logs")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(admin_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    
    async def ping_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ping command"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only.")
            return
        
        import time
        start = time.time()
        
        # Check services
        redis_status = "✅" if redis_client.ping() else "❌"
        
        try:
            await anilist_api.get_trending_anime(per_page=1)
            api_status = "✅"
        except:
            api_status = "❌"
        
        end = time.time()
        latency = round((end - start) * 1000, 2)
        
        # Get system stats
        import psutil
        cpu = psutil.cpu_percent()
        memory = psutil.virtual_memory().percent
        
        ping_text = (
            f"🏓 <b>Pong!</b>\n\n"
            f"⏱️ <b>Latency:</b> {latency}ms\n"
            f"🕐 <b>Uptime:</b> {self.format_time(int((datetime.now() - self.start_time).total_seconds()))}\n\n"
            f"🔧 <b>Services:</b>\n"
            f"• Redis: {redis_status}\n"
            f"• AniList API: {api_status}\n\n"
            f"💻 <b>System:</b>\n"
            f"• CPU: {cpu}%\n"
            f"• Memory: {memory}%\n\n"
            f"📊 <b>Usage:</b>\n"
            f"• Users: {len(redis_client.keys('user:*'))}\n"
            f"• Groups: {len(redis_client.smembers('groups'))}\n"
            f"• Commands: {redis_client.get('stats:total_commands') or 0}"
        )
        
        await update.message.reply_text(ping_text, parse_mode=ParseMode.HTML)
    
    async def list_groups(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all groups bot is in"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only.")
            return
        
        page = int(context.args[0]) if context.args and context.args[0].isdigit() else 1
        per_page = 10
        
        group_ids = list(redis_client.smembers('groups'))
        groups_page, total_pages = self.paginate_list(group_ids, page, per_page)
        
        if not groups_page:
            await update.message.reply_text("🤖 Bot is not in any groups yet.")
            return
        
        message = f"👥 <b>Groups (Page {page}/{total_pages}):</b>\n\n"
        
        for i, gid in enumerate(groups_page, 1):
            group_key = f"group:{gid}"
            group_data = redis_client.hgetall(group_key)
            
            title = group_data.get('title', 'Unknown Group')
            group_type = group_data.get('type', 'group')
            members = group_data.get('members', '?')
            last_active = group_data.get('last_active', 'Never')
            
            message += f"{i}. <b>{title}</b>\n"
            message += f"   🆔 <code>{gid}</code>\n"
            message += f"   👥 {members} members | {group_type}\n"
            message += f"   ⏰ Last active: {last_active}\n\n"
        
        # Pagination buttons
        keyboard = []
        if page > 1:
            keyboard.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"groups_{page-1}"))
        if page < total_pages:
            keyboard.append(InlineKeyboardButton("Next ➡️", callback_data=f"groups_{page+1}"))
        
        reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None
        await update.message.reply_text(message, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    
    async def promote_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Promote user to admin"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only.")
            return
        
        if not context.args:
            await update.message.reply_text("Please provide user ID.\nExample: <code>/pro 1234567890</code>", parse_mode=ParseMode.HTML)
            return
        
        try:
            target_id = int(context.args[0])
            
            if target_id in ADMIN_IDS:
                await update.message.reply_text("⚠️ User is already an admin.")
                return
            
            # Update user data
            user_key = f"user:{target_id}"
            if not redis_client.exists(user_key):
                await update.message.reply_text("❌ User not found in database.")
                return
            
            redis_client.hset(user_key, 'is_admin', 'true')
            ADMIN_IDS.append(target_id)
            
            await update.message.reply_text(f"✅ User <code>{target_id}</code> has been promoted to admin.")
            await self.log_action(f"👑 User {target_id} promoted by {user.id}")
            
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")
    
    async def bot_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Detailed bot statistics"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only.")
            return
        
        # Get all statistics
        total_users = len(redis_client.keys('user:*'))
        total_groups = len(redis_client.smembers('groups'))
        total_commands = int(redis_client.get('stats:total_commands') or 0)
        anilist_calls = int(redis_client.get('stats:anilist_calls') or 0)
        images_generated = int(redis_client.get('stats:image_gen') or 0)
        
        # Get user activity
        active_today = 0
        active_week = 0
        week_ago = datetime.now() - timedelta(days=7)
        
        for key in redis_client.keys('user:*'):
            user_data = redis_client.hgetall(key)
            last_seen = user_data.get('last_seen')
            if last_seen:
                last_seen_date = datetime.fromisoformat(last_seen)
                if last_seen_date.date() == datetime.now().date():
                    active_today += 1
                if last_seen_date > week_ago:
                    active_week += 1
        
        # Get command stats
        popular_commands = {}
        for key in redis_client.keys('stats:cmd:*'):
            cmd = key.split(':')[-1]
            count = int(redis_client.get(key) or 0)
            popular_commands[cmd] = count
        
        top_commands = sorted(popular_commands.items(), key=lambda x: x[1], reverse=True)[:5]
        
        stats_text = (
            f"📊 <b>Bot Statistics</b>\n\n"
            f"👥 <b>Users:</b> {total_users}\n"
            f"• Active today: {active_today}\n"
            f"• Active this week: {active_week}\n\n"
            f"👥 <b>Groups:</b> {total_groups}\n\n"
            f"📈 <b>Usage:</b>\n"
            f"• Total commands: {total_commands}\n"
            f"• AniList API calls: {anilist_calls}\n"
            f"• Images generated: {images_generated}\n\n"
            f"🏆 <b>Top Commands:</b>\n"
        )
        
        for cmd, count in top_commands:
            stats_text += f"• /{cmd}: {count}\n"
        
        stats_text += f"\n⏱️ <b>Uptime:</b> {self.format_time(int((datetime.now() - self.start_time).total_seconds()))}"
        
        await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)
    
    async def broadcast_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Broadcast message to all users"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only.")
            return
        
        if not context.args:
            await update.message.reply_text("Please provide a message to broadcast.\nExample: <code>/broadcast Hello everyone!</code>", parse_mode=ParseMode.HTML)
            return
        
        message = " ".join(context.args)
        confirm_text = (
            f"📢 <b>Broadcast Confirmation</b>\n\n"
            f"<b>Message:</b>\n{message}\n\n"
            f"<b>Target:</b> All users\n"
            f"<b>Total users:</b> {len(redis_client.keys('user:*'))}\n\n"
            f"Are you sure you want to broadcast this message?"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Yes, Broadcast", callback_data=f"broadcast_confirm_{user.id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Store message temporarily
        redis_client.setex(f"broadcast:{user.id}", 300, message)
        
        await update.message.reply_text(confirm_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    
    async def view_logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View bot logs"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only.")
            return
        
        lines = int(context.args[0]) if context.args and context.args[0].isdigit() else 50
        
        try:
            with open('bot.log', 'r') as f:
                log_lines = f.readlines()
            
            if lines > 100:
                lines = 100
            
            last_logs = log_lines[-lines:] if log_lines else ["No logs found"]
            logs_text = f"📜 <b>Last {lines} Log Lines:</b>\n\n<code>"
            logs_text += "".join(last_logs)
            logs_text += "</code>"
            
            # Split if too long
            if len(logs_text) > 4000:
                chunks = [logs_text[i:i+4000] for i in range(0, len(logs_text), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text(logs_text, parse_mode=ParseMode.HTML)
                
        except FileNotFoundError:
            await update.message.reply_text("❌ Log file not found.")
    
    async def maintenance_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Toggle maintenance mode"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only.")
            return
        
        if not context.args:
            await update.message.reply_text("Please specify 'on' or 'off'.\nExample: <code>/maintenance on</code>", parse_mode=ParseMode.HTML)
            return
        
        mode = context.args[0].lower()
        
        if mode == 'on':
            self.maintenance = True
            await update.message.reply_text("🔴 <b>Maintenance mode enabled.</b>\nThe bot will only respond to admins.")
            await self.log_action(f"🔧 Maintenance enabled by {user.id}")
        elif mode == 'off':
            self.maintenance = False
            await update.message.reply_text("🟢 <b>Maintenance mode disabled.</b>\nThe bot is now accessible to everyone.")
            await self.log_action(f"🔧 Maintenance disabled by {user.id}")
        else:
            await update.message.reply_text("❌ Invalid mode. Use 'on' or 'off'.")
    
    async def list_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all users"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only.")
            return
        
        page = int(context.args[0]) if context.args and context.args[0].isdigit() else 1
        per_page = 15
        
        user_keys = redis_client.keys('user:*')
        users_page, total_pages = self.paginate_list(user_keys, page, per_page)
        
        if not users_page:
            await update.message.reply_text("❌ No users found.")
            return
        
        message = f"👤 <b>Users (Page {page}/{total_pages}):</b>\n\n"
        
        for i, key in enumerate(users_page, 1):
            user_data = redis_client.hgetall(key)
            user_id = key.split(':')[-1]
            username = user_data.get('username', 'No username')
            first_name = user_data.get('first_name', 'No name')
            is_admin = user_data.get('is_admin') == 'true'
            is_banned = user_data.get('is_banned') == 'true'
            command_count = user_data.get('command_count', '0')
            
            status = "👑" if is_admin else "✅"
            if is_banned:
                status = "🔨"
            
            message += f"{i}. {status} <code>{user_id}</code> - {first_name}"
            if username:
                message += f" (@{username})"
            message += f"\n   📊 Commands: {command_count}\n\n"
        
        # Pagination buttons
        keyboard = []
        if page > 1:
            keyboard.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"users_{page-1}"))
        if page < total_pages:
            keyboard.append(InlineKeyboardButton("Next ➡️", callback_data=f"users_{page+1}"))
        
        reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None
        await update.message.reply_text(message, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    
    async def ban_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ban a user"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only.")
            return
        
        if not context.args:
            await update.message.reply_text("Please provide user ID.\nExample: <code>/ban 1234567890</code>", parse_mode=ParseMode.HTML)
            return
        
        try:
            target_id = int(context.args[0])
            
            if target_id in ADMIN_IDS:
                await update.message.reply_text("❌ Cannot ban another admin.")
                return
            
            user_key = f"user:{target_id}"
            if not redis_client.exists(user_key):
                await update.message.reply_text("❌ User not found.")
                return
            
            redis_client.hset(user_key, 'is_banned', 'true')
            
            reason = " ".join(context.args[1:]) if len(context.args) > 1 else "No reason provided"
            await update.message.reply_text(f"✅ User <code>{target_id}</code> has been banned.\nReason: {reason}")
            await self.log_action(f"🔨 User {target_id} banned by {user.id}: {reason}")
            
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")
    
    async def unban_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unban a user"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only.")
            return
        
        if not context.args:
            await update.message.reply_text("Please provide user ID.\nExample: <code>/unban 1234567890</code>", parse_mode=ParseMode.HTML)
            return
        
        try:
            target_id = int(context.args[0])
            
            user_key = f"user:{target_id}"
            if not redis_client.exists(user_key):
                await update.message.reply_text("❌ User not found.")
                return
            
            redis_client.hset(user_key, 'is_banned', 'false')
            await update.message.reply_text(f"✅ User <code>{target_id}</code> has been unbanned.")
            await self.log_action(f"🔓 User {target_id} unbanned by {user.id}")
            
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")
    
    # =========== CALLBACK HANDLERS ===========
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data.startswith("anime_"):
            anime_id = int(data.split("_")[1])
            await self.handle_anime_callback(query, anime_id)
        elif data.startswith("search_"):
            parts = data.split("_")
            if len(parts) >= 4:
                action = parts[1]
                search_query = "_".join(parts[2:-1])
                page = int(parts[-1])
                await self.handle_search_callback(query, search_query, page, action)
        elif data.startswith("broadcast_confirm_"):
            admin_id = int(data.split("_")[2])
            await self.execute_broadcast(query, admin_id)
        elif data == "broadcast_cancel":
            await query.edit_message_text("❌ Broadcast cancelled.")
        elif data.startswith("users_"):
            page = int(data.split("_")[1])
            await self.handle_users_callback(query, page)
        elif data.startswith("groups_"):
            page = int(data.split("_")[1])
            await self.handle_groups_callback(query, page)
        elif data == "help_menu":
            await query.edit_message_text("ℹ️ Use <code>/help</code> for command list.", parse_mode=ParseMode.HTML)
        elif data == "trending":
            await query.edit_message_text("🔥 Use <code>/trending</code> for trending anime.", parse_mode=ParseMode.HTML)
        elif data == "stats_me":
            await query.edit_message_text("📊 Use <code>/user your_username</code> for stats.", parse_mode=ParseMode.HTML)
        elif data == "settings":
            await query.edit_message_text("⚙️ Settings menu coming soon!", parse_mode=ParseMode.HTML)
    
    async def handle_anime_callback(self, query, anime_id):
        """Handle anime callback"""
        await query.message.reply_chat_action("typing")
        
        try:
            anime_data = await anilist_api.get_anime(anime_id)
            
            if anime_data:
                title = anime_data.get('title', {}).get('english') or anime_data.get('title', {}).get('romaji', 'N/A')
                message = (
                    f"🎬 <b>{title}</b>\n\n"
                    f"⭐ <b>Score:</b> {anime_data.get('averageScore', 'N/A')}/100\n"
                    f"📊 <b>Popularity:</b> #{anime_data.get('popularity', 'N/A')}\n"
                    f"🎬 <b>Format:</b> {anime_data.get('format', 'N/A')}\n"
                    f"📺 <b>Episodes:</b> {anime_data.get('episodes', 'N/A')}\n"
                    f"🏷️ <b>Genres:</b> {', '.join(anime_data.get('genres', ['N/A']))}\n\n"
                    f"🔗 <a href='https://anilist.co/anime/{anime_id}'>View on AniList</a>"
                )
                
                await query.message.reply_text(message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            else:
                await query.answer("Failed to fetch anime data.", show_alert=True)
                
        except Exception as e:
            logger.error(f"Callback error: {e}")
            await query.answer("Error fetching anime.", show_alert=True)
    
    async def handle_search_callback(self, query, search_query, page, action):
        """Handle search pagination"""
        if action == "next":
            page += 1
        elif action == "prev":
            page -= 1
            if page < 1:
                page = 1
        
        await query.message.reply_chat_action("typing")
        
        try:
            results = await anilist_api.search_anime(search_query, page=page, per_page=10)
            
            if not results:
                await query.edit_message_text("❌ No more results.")
                return
            
            message = f"🔍 <b>Search Results (Page {page}):</b>\n\n"
            keyboard = []
            
            for i, item in enumerate(results, 1):
                title = item.get('title', {}).get('english') or item.get('title', {}).get('romaji', 'N/A')
                message += f"{i}. <b>{title}</b>\n"
                message += f"   ⭐ {item.get('averageScore', 'N/A')} | 📊 #{item.get('popularity', 'N/A')}\n"
                message += f"   🆔 <code>{item.get('id')}</code>\n\n"
                
                keyboard.append([InlineKeyboardButton(
                    f"{i}. {title[:30]}...",
                    callback_data=f"anime_{item.get('id')}"
                )])
            
            # Pagination buttons
            nav_buttons = []
            if page > 1:
                nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"search_prev_{search_query}_{page-1}"))
            nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"search_next_{search_query}_{page+1}"))
            keyboard.append(nav_buttons)
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Search callback error: {e}")
            await query.edit_message_text("❌ Error loading more results.")
    
    async def execute_broadcast(self, query, admin_id):
        """Execute broadcast"""
        await query.edit_message_text("📢 Broadcasting started...")
        
        message = redis_client.get(f"broadcast:{admin_id}")
        if not message:
            await query.edit_message_text("❌ Broadcast message expired.")
            return
        
        user_keys = redis_client.keys('user:*')
        success = 0
        failed = 0
        
        broadcast_text = (
            f"📢 <b>Announcement</b>\n\n"
            f"{message}\n\n"
            f"<i>From AnimeKuun Bot Admin</i>"
        )
        
        for key in user_keys:
            user_data = redis_client.hgetall(key)
            user_id = user_data.get('id')
            
            if user_data.get('is_banned') == 'true':
                continue
            
            try:
                await self.app.bot.send_message(
                    chat_id=user_id,
                    text=broadcast_text,
                    parse_mode=ParseMode.HTML
                )
                success += 1
                await asyncio.sleep(0.05)  # Rate limiting
            except Exception as e:
                failed += 1
                logger.error(f"Broadcast failed for {user_id}: {e}")
        
        redis_client.delete(f"broadcast:{admin_id}")
        
        result_text = (
            f"✅ <b>Broadcast Complete!</b>\n\n"
            f"📊 <b>Results:</b>\n"
            f"• ✅ Success: {success}\n"
            f"• ❌ Failed: {failed}\n"
            f"• 📋 Total: {success + failed}"
        )
        
        await query.edit_message_text(result_text, parse_mode=ParseMode.HTML)
        await self.log_action(f"📢 Broadcast by {admin_id}: {success}成功, {failed}失败")
    
    async def handle_users_callback(self, query, page):
        """Handle users pagination"""
        user_keys = redis_client.keys('user:*')
        per_page = 15
        total_pages = (len(user_keys) + per_page - 1) // per_page
        
        if page < 1 or page > total_pages:
            await query.answer("Invalid page!")
            return
        
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        message = f"👤 <b>Users (Page {page}/{total_pages}):</b>\n\n"
        
        for i, key in enumerate(user_keys[start_idx:end_idx], start_idx + 1):
            user_data = redis_client.hgetall(key)
            user_id = key.split(':')[1]
            username = user_data.get('username', 'No username')
            first_name = user_data.get('first_name', 'No name')
            is_admin = user_data.get('is_admin') == 'true'
            is_banned = user_data.get('is_banned') == 'true'
            
            status = "👑" if is_admin else "✅"
            if is_banned:
                status = "🔨"
            
            message += f"{i}. {status} <code>{user_id}</code> - {first_name}"
            if username:
                message += f" (@{username})"
            message += f"\n   📊 Commands: {user_data.get('command_count', '0')}\n\n"
        
        # Pagination buttons
        keyboard = []
        if page > 1:
            keyboard.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"users_{page-1}"))
        if page < total_pages:
            keyboard.append(InlineKeyboardButton("Next ➡️", callback_data=f"users_{page+1}"))
        
        reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None
        await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    
    async def handle_groups_callback(self, query, page):
        """Handle groups pagination"""
        group_ids = list(redis_client.smembers('groups'))
        per_page = 10
        total_pages = (len(group_ids) + per_page - 1) // per_page
        
        if page < 1 or page > total_pages:
            await query.answer("Invalid page!")
            return
        
        groups_page, _ = self.paginate_list(group_ids, page, per_page)
        
        message = f"👥 <b>Groups (Page {page}/{total_pages}):</b>\n\n"
        
        for i, gid in enumerate(groups_page, 1):
            group_data = redis_client.hgetall(f"group:{gid}")
            title = group_data.get('title', 'Unknown Group')
            members = group_data.get('members', '?')
            last_active = group_data.get('last_active', 'Never')
            
            message += f"{i}. <b>{title}</b>\n"
            message += f"   🆔 <code>{gid}</code>\n"
            message += f"   👥 {members} members\n"
            message += f"   ⏰ {last_active}\n\n"
        
        # Pagination buttons
        keyboard = []
        if page > 1:
            keyboard.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"groups_{page-1}"))
        if page < total_pages:
            keyboard.append(InlineKeyboardButton("Next ➡️", callback_data=f"groups_{page+1}"))
        
        reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None
        await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    
    # =========== MESSAGE HANDLERS ===========
    
    async def handle_group_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle group messages"""
        chat = update.effective_chat
        
        # Update group info
        group_key = f"group:{chat.id}"
        group_data = {
            'id': str(chat.id),
            'title': chat.title or '',
            'type': chat.type,
            'members': str(chat.get_member_count()) if hasattr(chat, 'get_member_count') else '?',
            'last_active': datetime.now().isoformat()
        }
        redis_client.hset(group_key, mapping=group_data)
        redis_client.sadd('groups', chat.id)
        
        # Check if bot is mentioned
        if context.bot.username and f"@{context.bot.username}" in update.message.text:
            await update.message.reply_text(
                "🤖 Hi! I'm AnimeKuun Bot!\n"
                "Use /help to see all commands.\n"
                "Try: /search, /trending, /schedule"
            )
    
    async def handle_new_chat_members(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new chat members"""
        chat = update.effective_chat
        
        for member in update.message.new_chat_members:
            if member.id == context.bot.id:
                # Bot was added to group
                welcome_text = (
                    "🎌 Thanks for adding <b>AnimeKuun Bot</b>!\n\n"
                    "I can help with:\n"
                    "• Searching anime/manga\n"
                    "• Getting airing schedules\n"
                    "• User statistics\n"
                    "• And much more!\n\n"
                    "Try these commands:\n"
                    "• <code>/search Attack on Titan</code>\n"
                    "• <code>/trending</code>\n"
                    "• <code>/schedule</code>\n\n"
                    "Use /help for full command list!"
                )
                
                await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)
                
                # Log group addition
                await self.log_action(f"🤖 Bot added to group: {chat.id} ({chat.title})")
    
    # =========== ERROR HANDLER ===========
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Exception while handling update: {context.error}", exc_info=context.error)
        
        try:
            if update and update.effective_chat:
                error_msg = (
                    "❌ An error occurred. Please try again.\n"
                    "If the problem persists, contact the admin."
                )
                await update.effective_chat.send_message(error_msg)
        except:
            pass
    
    # =========== SETUP & RUN ===========
    
    def setup_handlers(self):
        """Setup all handlers"""
        
        # User commands
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("search", self.search_anime))
        self.app.add_handler(CommandHandler("anime", self.anime_info))
        self.app.add_handler(CommandHandler("trending", self.trending_anime))
        self.app.add_handler(CommandHandler("popular", self.popular_anime))
        self.app.add_handler(CommandHandler("seasonal", self.seasonal_anime))
        self.app.add_handler(CommandHandler("schedule", self.airing_schedule))
        self.app.add_handler(CommandHandler("topanime", self.top_anime))
        self.app.add_handler(CommandHandler("random", self.random_anime))
        self.app.add_handler(CommandHandler("manga", self.search_manga))
        self.app.add_handler(CommandHandler("user", self.user_profile))
        self.app.add_handler(CommandHandler("character", self.search_character))
        
        # Admin commands
        self.app.add_handler(CommandHandler("admin", self.admin_panel))
        self.app.add_handler(CommandHandler("ping", self.ping_command))
        self.app.add_handler(CommandHandler("groups", self.list_groups))
        self.app.add_handler(CommandHandler("pro", self.promote_user))
        self.app.add_handler(CommandHandler("statsbot", self.bot_statistics))
        self.app.add_handler(CommandHandler("broadcast", self.broadcast_message))
        self.app.add_handler(CommandHandler("logs", self.view_logs))
        self.app.add_handler(CommandHandler("maintenance", self.maintenance_mode))
        self.app.add_handler(CommandHandler("users", self.list_users))
        self.app.add_handler(CommandHandler("ban", self.ban_user))
        self.app.add_handler(CommandHandler("unban", self.unban_user))
        
        # Message handlers
        self.app.add_handler(MessageHandler(
            filters.ChatType.GROUP & filters.TEXT & ~filters.COMMAND,
            self.handle_group_message
        ))
        
        # Callback handlers
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
        
        # New chat members handler
        self.app.add_handler(MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS,
            self.handle_new_chat_members
        ))
        
        # Error handler
        self.app.add_error_handler(self.error_handler)
        
        # Set bot commands
        async def set_commands():
            commands = [
                BotCommand("start", "Start the bot"),
                BotCommand("help", "Show all commands"),
                BotCommand("search", "Search anime/manga"),
                BotCommand("anime", "Get anime details"),
                BotCommand("trending", "Trending anime"),
                BotCommand("popular", "Popular anime"),
                BotCommand("schedule", "Airing schedule"),
                BotCommand("topanime", "Top rated anime"),
                BotCommand("random", "Random anime"),
                BotCommand("user", "AniList profile"),
                BotCommand("admin", "Admin panel (admin only)")
            ]
            await self.app.bot.set_my_commands(commands)
        
        self.app.post_init = set_commands
    
    async def run(self):
        """Run the bot"""
        logger.info("🚀 Starting AnimeKuun Bot...")
        
        self.app = Application.builder().token(BOT_TOKEN).build()
        self.setup_handlers()
        
        await self.log_action("🤖 Bot started successfully!")
        logger.info("✅ Bot initialized")
        
        # Start polling
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        
        logger.info("✅ Bot is now running and polling")
        
        # Keep running
        await self.app.updater.idle()
        
        # Cleanup
        await anilist_api.close()

def main():
    """Main entry point"""
    bot = AnimeBot()
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")

if __name__ == "__main__":
    main()
