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
from anilist_api import AniListAPI, ImageGenerator

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "8282052807:AAHJw-9q_HZSwX9F4QQoCdpFEkxFqxFgCuA")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "6108185460").split(",")]
LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", "-1003662720845"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))

# Initialize Redis
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# Initialize API and Image Generator
anilist_api = AniListAPI(redis_client)
image_gen = ImageGenerator()

class AnimeBot:
    def __init__(self):
        self.app = None
        self.user_sessions = {}
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        # Save user to database
        user_key = f"user:{user.id}"
        user_data = {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'joined': datetime.now().isoformat(),
            'banned': False,
            'is_admin': user.id in ADMIN_IDS,
            'command_count': 0
        }
        redis_client.hset(user_key, mapping=user_data)
        redis_client.expire(user_key, 604800)  # 7 days
        
        welcome_text = (
            "🎌 *Welcome to AnimeKuun Bot!*\n\n"
            "Your ultimate AniList companion with:\n"
            "• 50+ anime/manga commands\n"
            "• Beautiful image cards\n"
            "• Real-time airing schedules\n"
            "• User statistics & comparisons\n"
            "• And much more!\n\n"
            "✨ *Quick Start:*\n"
            "`/search <title>` - Find anime/manga\n"
            "`/trending` - Trending now\n"
            "`/schedule` - Today's airing\n"
            "`/help` - Full command list\n\n"
            "Made with ❤️ for anime fans!"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔍 Search Anime", switch_inline_query_current_chat="search ")],
            [InlineKeyboardButton("📊 My Stats", callback_data="mystats"),
             InlineKeyboardButton("🌟 Top Anime", callback_data="topanime")],
            [InlineKeyboardButton("📚 Help", callback_data="help"),
             InlineKeyboardButton("👤 Profile", callback_data="profile")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
        # Log user join
        await self.log_action(f"👤 User joined: {user.id} (@{user.username})")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help menu"""
        user_id = update.effective_user.id
        
        help_text = (
            "📚 *AnimeKuun Bot Commands*\n\n"
            "*🔍 Search & Discovery:*\n"
            "`/search <title>` - Search anime/manga\n"
            "`/trending` - Trending anime\n"
            "`/popular` - Popular this season\n"
            "`/upcoming` - Upcoming releases\n"
            "`/seasonal` - Current season\n"
            "`/character <name>` - Search characters\n"
            "`/staff <name>` - Search creators\n"
            "`/genre <genre>` - Search by genre\n\n"
            "*🎬 Anime Information:*\n"
            "`/anime <id/title>` - Anime details\n"
            "`/manga <id/title>` - Manga details\n"
            "`/char <id/name>` - Character info\n"
            "`/studio <name>` - Studio info\n"
            "`/relations <id>` - Related media\n"
            "`/recommend <id>` - Recommendations\n"
            "`/reviews <id>` - User reviews\n"
            "`/trailer <id>` - YouTube trailer\n\n"
            "*👥 User & Lists:*\n"
            "`/user <username>` - AniList profile\n"
            "`/list <username>` - User's anime list\n"
            "`/favorites <username>` - User favorites\n"
            "`/compare <user1> <user2>` - Compare lists\n"
            "`/watching <username>` - Currently watching\n\n"
            "*📊 Statistics & Charts:*\n"
            "`/topanime` - Top-rated anime\n"
            "`/topmanga` - Top-rated manga\n"
            "`/topcharacters` - Popular characters\n"
            "`/genrestats` - Genre statistics\n"
            "`/scorestats <id>` - Score distribution\n"
            "`/yearstats <year>` - Anime by year\n\n"
            "*⚙️ Utilities:*\n"
            "`/schedule` - Today's airing\n"
            "`/airing <id>` - Next episode\n"
            "`/random` - Random anime\n"
            "`/similar <id>` - Similar anime\n"
            "`/quote` - Random anime quote\n"
            "`/birthdays` - Character birthdays\n"
            "`/news <id>` - Anime news\n"
            "`/calendar` - Monthly calendar\n\n"
            "*🛠️ Admin Commands:*\n"
            "`/admin` - Admin panel (Admins only)\n\n"
            "💡 *Tip:* Use inline mode: `@AnimeKuun_bot search <title>`"
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
            results = await anilist_api.search_anime(query, page=1, per_page=10)
            
            if not results:
                await update.message.reply_text("❌ No results found.")
                return
                
            message = "🔍 *Search Results:*\n\n"
            keyboard = []
            
            for i, item in enumerate(results[:10], 1):
                title = item.get('title', {}).get('english') or item.get('title', {}).get('romaji', 'N/A')
                message += f"{i}. *{title}* ({item.get('type', 'N/A')})\n"
                message += f"   ⭐ {item.get('averageScore', 'N/A')} | 📊 {item.get('popularity', 'N/A')}\n"
                message += f"   🆔 `{item.get('id')}`\n\n"
                
                keyboard.append([InlineKeyboardButton(
                    f"{i}. {title[:30]}...",
                    callback_data=f"anime_{item.get('id')}"
                )])
                
            keyboard.append([
                InlineKeyboardButton("⬅️ Previous", callback_data=f"search_prev_{query}_1"),
                InlineKeyboardButton("Next ➡️", callback_data=f"search_next_{query}_2")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            await update.message.reply_text("❌ Error searching. Please try again.")

    async def anime_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get detailed anime information"""
        if not context.args:
            await update.message.reply_text("Please provide anime ID or title. Example: `/anime 16498` or `/anime Attack on Titan`")
            return
            
        query = " ".join(context.args)
        await update.message.reply_chat_action("upload_photo")
        
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
            
            # Generate image card
            image_path = await image_gen.generate_anime_card(anime_data)
            
            # Create buttons
            keyboard = [
                [InlineKeyboardButton("🎭 Characters", callback_data=f"chars_{anime_data['id']}"),
                 InlineKeyboardButton("👨‍💼 Staff", callback_data=f"staff_{anime_data['id']}")],
                [InlineKeyboardButton("🔗 Relations", callback_data=f"rel_{anime_data['id']}"),
                 InlineKeyboardButton("🌟 Recommendations", callback_data=f"rec_{anime_data['id']}")],
                [InlineKeyboardButton("📺 Trailer", callback_data=f"trailer_{anime_data['id']}"),
                 InlineKeyboardButton("📊 Reviews", callback_data=f"reviews_{anime_data['id']}")],
                [InlineKeyboardButton("📋 Add to List", url=f"https://anilist.co/anime/{anime_data['id']}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send image with caption
            title = anime_data.get('title', {}).get('english') or anime_data.get('title', {}).get('romaji', 'N/A')
            caption = (
                f"*{title}*\n\n"
                f"⭐ *Score:* {anime_data.get('averageScore', 'N/A')}/100\n"
                f"📊 *Rank:* #{anime_data.get('rankings', [{}])[0].get('rank', 'N/A') if anime_data.get('rankings') else 'N/A'}\n"
                f"📈 *Popularity:* #{anime_data.get('popularity', 'N/A')}\n"
                f"🎬 *Type:* {anime_data.get('format', 'N/A')}\n"
                f"📅 *Status:* {anime_data.get('status', 'N/A').capitalize()}\n"
                f"📺 *Episodes:* {anime_data.get('episodes', 'N/A')}\n"
                f"⏱️ *Duration:* {anime_data.get('duration', 'N/A')} min\n"
                f"📅 *Aired:* {anime_data.get('startDate', {}).get('year', 'N/A')}\n"
                f"🏷️ *Genres:* {', '.join(anime_data.get('genres', []))}\n\n"
                f"_{anime_data.get('description', 'No description')[:200]}..._"
            )
            
            with open(image_path, 'rb') as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
            
            # Clean up image file
            os.remove(image_path)
            
        except Exception as e:
            logger.error(f"Anime info error: {e}")
            await update.message.reply_text("❌ Error fetching anime information.")

    # =========== TRENDING/POPULAR COMMANDS ===========
    
    async def trending_anime(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show trending anime"""
        await update.message.reply_chat_action("typing")
        
        try:
            results = await anilist_api.get_trending_anime(per_page=10)
            
            message = "🔥 *Trending Anime Now:*\n\n"
            for i, anime in enumerate(results, 1):
                title = anime.get('title', {}).get('english') or anime.get('title', {}).get('romaji', 'N/A')
                message += f"{i}. *{title}*\n"
                message += f"   ⭐ {anime.get('averageScore', 'N/A')} | 📈 {anime.get('trending', 'N/A')} trending\n"
                message += f"   🆔 `{anime.get('id')}` | 🎬 {anime.get('format', 'N/A')}\n\n"
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logger.error(f"Trending error: {e}")
            await update.message.reply_text("❌ Error fetching trending anime.")

    # =========== USER COMMANDS ===========
    
    async def user_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get AniList user profile"""
        if not context.args:
            await update.message.reply_text("Please provide AniList username. Example: `/user username`")
            return
            
        username = context.args[0]
        await update.message.reply_chat_action("upload_photo")
        
        try:
            user_data = await anilist_api.get_user_profile(username)
            
            if not user_data:
                await update.message.reply_text("❌ User not found.")
                return
            
            # Generate user profile card
            image_path = await image_gen.generate_user_card(user_data)
            
            # Prepare statistics
            stats = user_data.get('statistics', {}).get('anime', {})
            
            caption = (
                f"👤 *{user_data.get('name', 'N/A')}*\n"
                f"📊 *Level:* {user_data.get('donatorTier', 0)} | 🎯 *Days:* {user_data.get('daysWatched', 0):.1f}\n\n"
                f"*Anime Stats:*\n"
                f"• 📊 Mean Score: {stats.get('meanScore', 0)}/100\n"
                f"• 📈 Total: {stats.get('count', 0)} anime\n"
                f"• 👁️ Watching: {stats.get('watching', 0)}\n"
                f"• ✅ Completed: {stats.get('completed', 0)}\n"
                f"• ⏸️ On Hold: {stats.get('onHold', 0)}\n"
                f"• 📋 Planned: {stats.get('planned', 0)}\n"
                f"• ❌ Dropped: {stats.get('dropped', 0)}\n\n"
                f"🔗 [View on AniList](https://anilist.co/user/{username})"
            )
            
            with open(image_path, 'rb') as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN
                )
            
            os.remove(image_path)
            
        except Exception as e:
            logger.error(f"User profile error: {e}")
            await update.message.reply_text("❌ Error fetching user profile.")

    # =========== SCHEDULE COMMANDS ===========
    
    async def airing_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show today's airing schedule"""
        await update.message.reply_chat_action("typing")
        
        try:
            schedule = await anilist_api.get_airing_schedule()
            
            message = "📺 *Today's Airing Schedule:*\n\n"
            current_time = datetime.now()
            
            for i, anime in enumerate(schedule[:15], 1):
                title = anime.get('media', {}).get('title', {}).get('english') or \
                       anime.get('media', {}).get('title', {}).get('romaji', 'N/A')
                episode = anime.get('episode', 'N/A')
                airing_at = anime.get('airingAt', 0)
                
                # Convert timestamp to readable time
                airing_time = datetime.fromtimestamp(airing_at)
                time_str = airing_time.strftime("%H:%M")
                
                # Calculate time until airing
                time_diff = airing_time - current_time
                hours = int(time_diff.total_seconds() // 3600)
                minutes = int((time_diff.total_seconds() % 3600) // 60)
                
                message += f"{i}. *{title}* - Ep {episode}\n"
                message += f"   ⏰ {time_str} (in {hours}h {minutes}m)\n\n"
            
            if len(schedule) > 15:
                message += f"... and {len(schedule) - 15} more\n"
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logger.error(f"Schedule error: {e}")
            await update.message.reply_text("❌ Error fetching schedule.")

    # =========== ADMIN COMMANDS ===========
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin panel command"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only.")
            return
        
        admin_text = (
            "🛠️ *Admin Panel*\n\n"
            "*User Management:*\n"
            "`/users` - List all bot users\n"
            "`/ban <user_id>` - Ban user\n"
            "`/unban <user_id>` - Unban user\n"
            "`/pro <user_id>` - Promote to admin\n"
            "`/unpro <user_id>` - Demote from admin\n\n"
            "*Bot Controls:*\n"
            "`/ping` - Check bot status\n"
            "`/statsbot` - Bot statistics\n"
            "`/broadcast <message>` - Broadcast message\n"
            "`/announce <message>` - Send announcement\n"
            "`/logs [lines]` - View bot logs\n"
            "`/backup` - Backup user data\n"
            "`/restart` - Restart bot\n"
            "`/maintenance <on/off>` - Toggle maintenance\n"
            "`/settings` - Bot settings\n\n"
            "*Configuration:*\n"
            "`/config get <key>` - Get config value\n"
            "`/config set <key> <value>` - Set config\n"
            "`/config list` - List all configs\n\n"
            "Use `/admin` to show this panel again."
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
            f"*Uptime:* {self.get_uptime()}\n"
            f"*Users:* {len(redis_client.keys('user:*'))}\n"
            f"*Cache Size:* {redis_client.dbsize()} items"
        )
        
        await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)

    async def broadcast_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Broadcast message to all users"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only.")
            return
        
        if not context.args:
            await update.message.reply_text("Please provide a message to broadcast.")
            return
        
        message = " ".join(context.args)
        confirm_keyboard = [
            [InlineKeyboardButton("✅ Yes, Broadcast", callback_data=f"broadcast_confirm_{user_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(confirm_keyboard)
        
        await update.message.reply_text(
            f"📢 *Broadcast Confirmation*\n\n"
            f"Message: {message}\n\n"
            f"Total users: {len(redis_client.keys('user:*'))}\n"
            f"Are you sure?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
        # Store message temporarily
        redis_client.setex(f"broadcast:{user_id}", 300, message)

    async def promote_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Promote user to admin"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only.")
            return
        
        if not context.args:
            await update.message.reply_text("Please provide user ID. Example: `/pro 1234567890`")
            return
        
        try:
            target_id = int(context.args[0])
            
            # Get user data
            user_key = f"user:{target_id}"
            if not redis_client.exists(user_key):
                await update.message.reply_text("❌ User not found in database.")
                return
            
            # Promote user
            redis_client.hset(user_key, 'is_admin', 'true')
            
            # Update ADMIN_IDS list
            if target_id not in ADMIN_IDS:
                ADMIN_IDS.append(target_id)
                # Save to config (in real app, save to file/db)
            
            await update.message.reply_text(f"✅ User {target_id} promoted to admin.")
            await self.log_action(f"👑 User {target_id} promoted by {user_id}")
            
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")

    async def bot_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show bot statistics"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only.")
            return
        
        # Get total users
        user_keys = redis_client.keys("user:*")
        total_users = len(user_keys)
        
        # Get active users (last 24 hours)
        active_users = 0
        banned_users = 0
        admin_users = 0
        
        for key in user_keys:
            is_banned = redis_client.hget(key, 'banned') == 'true'
            is_admin = redis_client.hget(key, 'is_admin') == 'true'
            
            if is_banned:
                banned_users += 1
            if is_admin:
                admin_users += 1
        
        # Get command statistics
        total_commands = redis_client.get("stats:total_commands") or 0
        
        stats_text = (
            "📊 *Bot Statistics*\n\n"
            f"*👥 Users:* {total_users}\n"
            f"  • 👑 Admins: {admin_users}\n"
            f"  • 🔨 Banned: {banned_users}\n"
            f"  • ✅ Active: {total_users - banned_users}\n\n"
            f"*📈 Commands:* {total_commands}\n"
            f"*💾 Cache:* {redis_client.dbsize()} items\n"
            f"*⏱️ Uptime:* {self.get_uptime()}\n\n"
            f"*🔄 API Calls (Last 24h):*\n"
            f"  • AniList: {redis_client.get('stats:anilist_calls') or 0}\n"
            f"  • Images: {redis_client.get('stats:image_gen') or 0}"
        )
        
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

    async def list_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all bot users"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only.")
            return
        
        # Get page number
        page = int(context.args[0]) if context.args and context.args[0].isdigit() else 1
        per_page = 10
        
        # Get all users
        user_keys = redis_client.keys("user:*")
        total_pages = (len(user_keys) + per_page - 1) // per_page
        
        if page < 1 or page > total_pages:
            await update.message.reply_text(f"❌ Page must be between 1 and {total_pages}")
            return
        
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        message = f"👥 *Bot Users (Page {page}/{total_pages})*\n\n"
        
        for i, key in enumerate(user_keys[start_idx:end_idx], start_idx + 1):
            user_data = redis_client.hgetall(key)
            user_id = key.split(":")[1]
            username = user_data.get('username', 'No username')
            first_name = user_data.get('first_name', 'No name')
            is_admin = user_data.get('is_admin') == 'true'
            is_banned = user_data.get('banned') == 'true'
            
            status = "👑" if is_admin else "✅"
            if is_banned:
                status = "🔨"
            
            message += f"{i}. {status} `{user_id}` - {first_name} (@{username})\n"
        
        # Create pagination buttons
        keyboard = []
        if page > 1:
            keyboard.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"users_{page-1}"))
        if page < total_pages:
            keyboard.append(InlineKeyboardButton("Next ➡️", callback_data=f"users_{page+1}"))
        
        if keyboard:
            reply_markup = InlineKeyboardMarkup([keyboard])
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        else:
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

    async def ban_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ban a user from using the bot"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only.")
            return
        
        if not context.args:
            await update.message.reply_text("Please provide user ID. Example: `/ban 1234567890`")
            return
        
        try:
            target_id = int(context.args[0])
            
            if target_id in ADMIN_IDS:
                await update.message.reply_text("❌ Cannot ban another admin.")
                return
            
            # Ban user
            user_key = f"user:{target_id}"
            if redis_client.exists(user_key):
                redis_client.hset(user_key, 'banned', 'true')
                await update.message.reply_text(f"✅ User {target_id} has been banned.")
                await self.log_action(f"🔨 User {target_id} banned by {user_id}")
            else:
                await update.message.reply_text("❌ User not found in database.")
                
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")

    async def view_logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View bot logs"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only.")
            return
        
        # Get last N lines from log file
        lines = int(context.args[0]) if context.args and context.args[0].isdigit() else 20
        
        try:
            with open('bot.log', 'r') as f:
                log_lines = f.readlines()
            
            if lines > 100:
                lines = 100
                
            last_logs = log_lines[-lines:] if log_lines else ["No logs found"]
            logs_text = "📜 *Last {} Log Lines:*\n\n```\n".format(lines)
            logs_text += "".join(last_logs)
            logs_text += "\n```"
            
            # Split if too long
            if len(logs_text) > 4000:
                chunks = [logs_text[i:i+4000] for i in range(0, len(logs_text), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN_V2)
            else:
                await update.message.reply_text(logs_text, parse_mode=ParseMode.MARKDOWN_V2)
                
        except FileNotFoundError:
            await update.message.reply_text("❌ Log file not found.")

    # =========== UTILITY METHODS ===========
    
    def get_uptime(self):
        """Calculate bot uptime"""
        if hasattr(self, 'start_time'):
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
        return "Unknown"
    
    async def log_action(self, message: str):
        """Log action to log channel"""
        try:
            await self.app.bot.send_message(
                chat_id=LOG_CHANNEL,
                text=f"📝 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}"
            )
        except Exception as e:
            logger.error(f"Failed to log to channel: {e}")

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

    async def handle_anime_callback(self, query, anime_id):
        """Handle anime info callback"""
        await query.message.reply_chat_action("upload_photo")
        
        try:
            anime_data = await anilist_api.get_anime(anime_id)
            
            if anime_data:
                # Generate image card
                image_path = await image_gen.generate_anime_card(anime_data)
                
                # Create buttons
                keyboard = [
                    [InlineKeyboardButton("🎭 Characters", callback_data=f"chars_{anime_id}"),
                     InlineKeyboardButton("👨‍💼 Staff", callback_data=f"staff_{anime_id}")],
                    [InlineKeyboardButton("🔗 View on AniList", url=f"https://anilist.co/anime/{anime_id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Send image
                title = anime_data.get('title', {}).get('english') or anime_data.get('title', {}).get('romaji', 'N/A')
                caption = f"*{title}*\nClick buttons below for more info!"
                
                with open(image_path, 'rb') as photo:
                    await query.message.reply_photo(
                        photo=photo,
                        caption=caption,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=reply_markup
                    )
                
                os.remove(image_path)
            else:
                await query.message.reply_text("❌ Failed to fetch anime data.")
                
        except Exception as e:
            logger.error(f"Callback error: {e}")
            await query.message.reply_text("❌ Error fetching anime information.")

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
            
            message = f"🔍 *Search Results (Page {page}):*\n\n"
            keyboard = []
            
            for i, item in enumerate(results, 1):
                title = item.get('title', {}).get('english') or item.get('title', {}).get('romaji', 'N/A')
                message += f"{i}. *{title}* ({item.get('type', 'N/A')})\n"
                message += f"   ⭐ {item.get('averageScore', 'N/A')} | 📊 {item.get('popularity', 'N/A')}\n"
                message += f"   🆔 `{item.get('id')}`\n\n"
                
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
            await query.edit_message_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Search callback error: {e}")
            await query.edit_message_text("❌ Error loading more results.")

    async def execute_broadcast(self, query, admin_id):
        """Execute broadcast to all users"""
        await query.edit_message_text("📢 Broadcasting started...")
        
        # Get message from temp storage
        message = redis_client.get(f"broadcast:{admin_id}")
        if not message:
            await query.edit_message_text("❌ Broadcast message expired or not found.")
            return
        
        # Get all users
        user_keys = redis_client.keys("user:*")
        success_count = 0
        fail_count = 0
        
        for key in user_keys:
            user_id = key.split(":")[1]
            
            # Check if user is banned
            is_banned = redis_client.hget(key, 'banned') == 'true'
            if is_banned:
                continue
            
            try:
                await self.app.bot.send_message(
                    chat_id=user_id,
                    text=f"📢 *Announcement*\n\n{message}\n\n_From AnimeKuun Bot Admin_",
                    parse_mode=ParseMode.MARKDOWN
                )
                success_count += 1
                await asyncio.sleep(0.1)  # Rate limiting
            except Exception as e:
                fail_count += 1
                logger.error(f"Failed to send to {user_id}: {e}")
        
        # Clean up
        redis_client.delete(f"broadcast:{admin_id}")
        
        await query.edit_message_text(
            f"✅ Broadcast completed!\n\n"
            f"✅ Success: {success_count}\n"
            f"❌ Failed: {fail_count}\n"
            f"📊 Total: {success_count + fail_count}"
        )
        
        await self.log_action(f"📢 Broadcast sent by {admin_id}: {success_count}成功, {fail_count}失败")

    async def handle_users_callback(self, query, page):
        """Handle users list pagination"""
        user_keys = redis_client.keys("user:*")
        per_page = 10
        total_pages = (len(user_keys) + per_page - 1) // per_page
        
        if page < 1 or page > total_pages:
            await query.answer("Invalid page!")
            return
        
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        message = f"👥 *Bot Users (Page {page}/{total_pages})*\n\n"
        
        for i, key in enumerate(user_keys[start_idx:end_idx], start_idx + 1):
            user_data = redis_client.hgetall(key)
            user_id = key.split(":")[1]
            username = user_data.get('username', 'No username')
            first_name = user_data.get('first_name', 'No name')
            is_admin = user_data.get('is_admin') == 'true'
            is_banned = user_data.get('banned') == 'true'
            
            status = "👑" if is_admin else "✅"
            if is_banned:
                status = "🔨"
            
            message += f"{i}. {status} `{user_id}` - {first_name} (@{username})\n"
        
        # Create pagination buttons
        keyboard = []
        if page > 1:
            keyboard.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"users_{page-1}"))
        if page < total_pages:
            keyboard.append(InlineKeyboardButton("Next ➡️", callback_data=f"users_{page+1}"))
        
        reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None
        await query.edit_message_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

    # =========== SETUP & RUN ===========
    
    def setup_handlers(self):
        """Setup all command handlers"""
        
        # User commands
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help_command))
        
        # Search commands
        self.app.add_handler(CommandHandler("search", self.search_anime))
        self.app.add_handler(CommandHandler("anime", self.anime_info))
        self.app.add_handler(CommandHandler("trending", self.trending_anime))
        self.app.add_handler(CommandHandler("user", self.user_profile))
        self.app.add_handler(CommandHandler("schedule", self.airing_schedule))
        
        # Add more command handlers here for other commands
        # self.app.add_handler(CommandHandler("popular", self.popular_anime))
        # self.app.add_handler(CommandHandler("upcoming", self.upcoming_anime))
        # etc...
        
        # Admin commands
        self.app.add_handler(CommandHandler("admin", self.admin_panel))
        self.app.add_handler(CommandHandler("ping", self.ping_command))
        self.app.add_handler(CommandHandler("broadcast", self.broadcast_message))
        self.app.add_handler(CommandHandler("pro", self.promote_user))
        self.app.add_handler(CommandHandler("statsbot", self.bot_statistics))
        self.app.add_handler(CommandHandler("users", self.list_users))
        self.app.add_handler(CommandHandler("ban", self.ban_user))
        self.app.add_handler(CommandHandler("logs", self.view_logs))
        
        # Callback handlers
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Set bot commands menu
        commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Show all commands"),
            BotCommand("search", "Search anime/manga"),
            BotCommand("anime", "Get anime details"),
            BotCommand("trending", "Trending anime"),
            BotCommand("user", "AniList user profile"),
            BotCommand("schedule", "Airing schedule"),
            BotCommand("admin", "Admin panel (admin only)"),
        ]
        
        async def set_commands():
            await self.app.bot.set_my_commands(commands)
        
        self.app.post_init = set_commands

    async def run(self):
        """Run the bot"""
        self.start_time = datetime.now()
        
        # Create application
        self.app = Application.builder().token(BOT_TOKEN).build()
        
        # Setup handlers
        self.setup_handlers()
        
        # Log startup
        logger.info("Starting AnimeKuun Bot...")
        await self.log_action("🤖 Bot started successfully!")
        
        # Start bot
        await self.app.initialize()
        await self.app.start()
        
        # Set webhook for Railway
        webhook_url = os.getenv("RAILWAY_STATIC_URL")
        if webhook_url:
            await self.app.bot.set_webhook(f"{webhook_url}/{BOT_TOKEN}")
            logger.info(f"Webhook set to: {webhook_url}")
        else:
            logger.info("Using polling mode")
            await self.app.updater.start_polling()
        
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
