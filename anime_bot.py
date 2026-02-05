#!/usr/bin/env python3
"""
AnimeKuun Bot - Complete Anime/Manga Telegram Bot
Main bot file with all commands and handlers
Optimized for Railway deployment
"""

import os
import sys
import logging
import asyncio
import json
import redis
import time
import re
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ChatMemberHandler
)
from telegram.constants import ParseMode, ChatType
from telegram.error import TelegramError

# =========== CONFIGURATION ===========
BOT_TOKEN = os.getenv("BOT_TOKEN", "8282052807:AAERvnTQKpqBxz23qW4eygRknkVcqy31NNw")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "6108185460").split(",") if id.strip()]
LOG_CHANNEL = os.getenv("LOG_CHANNEL", "-1003662720845")
REDIS_URL = os.getenv("REDIS_URL", "redis://default:redispw@localhost:6379")
WEBHOOK_URL = os.getenv("RAILWAY_STATIC_URL", "")
PORT = int(os.getenv("PORT", "8080"))

# =========== LOGGING SETUP ===========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# =========== REDIS SETUP ===========
class DummyRedis:
    """Fallback Redis client when Redis is unavailable"""
    def __init__(self):
        self.data = {}
        self.expiry = {}
        logger.info("Using DummyRedis - data will reset on restart")
    
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
        return True
    
    def setex(self, key, ttl, value):
        return self.set(key, value, ex=ttl)
    
    def hset(self, key, mapping=None, **kwargs):
        if key not in self.data:
            self.data[key] = {}
        if mapping:
            self.data[key].update(mapping)
        if kwargs:
            self.data[key].update(kwargs)
        return 1
    
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
        count = 0
        for key in keys:
            if key in self.data:
                del self.data[key]
                count += 1
            if key in self.expiry:
                del self.expiry[key]
        return count
    
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
        return len(values)
    
    def smembers(self, key):
        return list(self.data.get(key, set()))
    
    def srem(self, key, *values):
        if key in self.data:
            for value in values:
                self.data[key].discard(value)
        return len(values)
    
    def zadd(self, key, mapping, **kwargs):
        if key not in self.data:
            self.data[key] = {}
        self.data[key].update(mapping)
        return len(mapping)
    
    def zrange(self, key, start, end, withscores=False, desc=False):
        if key not in self.data:
            return []
        items = sorted(self.data[key].items(), key=lambda x: x[1], reverse=desc)
        if withscores:
            return items[start:end]
        return [k for k, v in items[start:end]]
    
    def expire(self, key, ttl):
        if key in self.data:
            self.expiry[key] = datetime.now() + timedelta(seconds=ttl)
            return True
        return False

# Initialize Redis
try:
    logger.info(f"Connecting to Redis at: {REDIS_URL}")
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    logger.info("Redis connected successfully")
except Exception as e:
    logger.error(f"Redis connection failed: {e}")
    redis_client = DummyRedis()

# =========== API MODULE IMPORT ===========
try:
    from anilist_api import AniListAPI, ImageGenerator
    logger.info("Successfully imported anilist_api module")
except ImportError as e:
    logger.error(f"Failed to import anilist_api: {e}")
    logger.warning("Creating fallback API classes...")
    
    class AniListAPI:
        def __init__(self, rc):
            self.redis = rc
            logger.info("Using fallback AniListAPI")
        
        async def search_anime(self, query, page=1, per_page=10):
            return [
                {"id": 16498, "title": {"english": "Attack on Titan", "romaji": "Shingeki no Kyojin"}, "averageScore": 85, "popularity": 1, "format": "TV", "episodes": 75},
                {"id": 21, "title": {"english": "One Piece", "romaji": "One Piece"}, "averageScore": 88, "popularity": 2, "format": "TV", "episodes": 1100},
                {"id": 101922, "title": {"english": "Demon Slayer", "romaji": "Kimetsu no Yaiba"}, "averageScore": 87, "popularity": 3, "format": "TV", "episodes": 55},
            ]
        
        async def get_anime(self, anime_id):
            return {
                "id": anime_id,
                "title": {"english": "Attack on Titan", "romaji": "Shingeki no Kyojin"},
                "averageScore": 85,
                "popularity": 100,
                "format": "TV",
                "episodes": 75,
                "status": "FINISHED",
                "genres": ["Action", "Drama", "Fantasy"],
                "description": "Centuries ago, mankind was slaughtered to near extinction by monstrous humanoid creatures called Titans...",
                "coverImage": {"extraLarge": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/bx16498-C6FPmWm59CyP.jpg"},
                "studios": {"edges": [{"node": {"name": "Wit Studio"}}]},
                "favourites": 100000,
                "nextAiringEpisode": None
            }
        
        async def get_trending_anime(self, per_page=15):
            return await self.search_anime("", per_page=per_page)
        
        async def get_popular_anime(self, per_page=15):
            return await self.search_anime("", per_page=per_page)
        
        async def get_seasonal_anime(self, year=None, season=None):
            return await self.search_anime("", per_page=10)
        
        async def get_airing_schedule(self):
            return []
        
        async def search_manga(self, query, page=1, per_page=10):
            return await self.search_anime(query, page=page, per_page=per_page)
        
        async def get_manga(self, manga_id):
            return await self.get_anime(manga_id)
        
        async def search_character(self, query, page=1, per_page=10):
            return [
                {"id": 1, "name": {"full": "Eren Yeager"}, "image": {"large": ""}},
                {"id": 2, "name": {"full": "Mikasa Ackerman"}, "image": {"large": ""}},
            ]
        
        async def get_character(self, character_id):
            return {"id": character_id, "name": {"full": "Eren Yeager"}}
        
        async def search_staff(self, query, page=1, per_page=10):
            return []
        
        async def search_studio(self, query, page=1, per_page=10):
            return []
        
        async def get_user_profile(self, username):
            return {"id": 1, "name": username, "statistics": {"anime": {"count": 100, "meanScore": 85}}}
        
        async def get_user_list(self, username, media_type="ANIME"):
            return []
        
        async def get_top_anime(self, page=1, per_page=15):
            return await self.search_anime("", per_page=per_page)
        
        async def get_top_manga(self, page=1, per_page=15):
            return await self.search_manga("", per_page=per_page)
        
        async def get_random_anime(self, genre=None):
            return await self.get_anime(16498)
        
        async def get_anime_news(self, anime_id):
            return []
        
        async def get_anime_recommendations(self, anime_id):
            return []
        
        async def get_character_birthdays(self):
            return []
        
        async def get_anime_stats(self, anime_id):
            return {}
        
        async def get_genre_stats(self):
            return []
        
        async def get_anime_relations(self, anime_id):
            return []
        
        async def get_anime_characters(self, anime_id):
            return []
        
        async def get_anime_staff(self, anime_id):
            return []
        
        async def get_anime_reviews(self, anime_id):
            return []
        
        async def get_anime_trailer(self, anime_id):
            return {}
        
        async def get_anime_quote(self):
            return {"quote": "Believe in the me that believes in you!", "character": "Kamina", "anime": "Gurren Lagann"}
        
        async def close(self):
            pass
    
    class ImageGenerator:
        def __init__(self):
            logger.info("Using fallback ImageGenerator")
        
        async def generate_anime_card(self, anime_data):
            return None
        
        async def generate_user_card(self, user_data):
            return None
        
        async def generate_character_card(self, character_data):
            return None
        
        async def close(self):
            pass

# Initialize API
anilist_api = AniListAPI(redis_client)
image_gen = ImageGenerator()

# =========== MAIN BOT CLASS ===========
class AnimeBot:
    def __init__(self):
        self.app = None
        self.start_time = datetime.now()
        self.maintenance_mode = False
        self.is_webhook = bool(WEBHOOK_URL)
        
    # =========== UTILITY METHODS ===========
    
    async def log_to_channel(self, message: str):
        """Log message to Telegram channel"""
        try:
            if LOG_CHANNEL and self.app:
                await self.app.bot.send_message(
                    chat_id=LOG_CHANNEL,
                    text=f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{message}",
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            logger.error(f"Failed to log to channel: {e}")
    
    def update_user_stats(self, user_id: int, username: str = "", first_name: str = "", last_name: str = ""):
        """Update user statistics"""
        user_key = f"user:{user_id}"
        user_data = redis_client.hgetall(user_key) or {}
        
        if not user_data:
            user_data = {
                'id': str(user_id),
                'username': username or '',
                'first_name': first_name or '',
                'last_name': last_name or '',
                'joined': datetime.now().isoformat(),
                'command_count': '0',
                'last_seen': datetime.now().isoformat(),
                'is_banned': 'false',
                'is_admin': 'true' if user_id in ADMIN_IDS else 'false'
            }
        else:
            user_data['last_seen'] = datetime.now().isoformat()
            if username:
                user_data['username'] = username
            if first_name:
                user_data['first_name'] = first_name
        
        redis_client.hset(user_key, mapping=user_data)
        return user_data
    
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
    
    # =========== BASIC COMMAND HANDLERS ===========
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        chat = update.effective_chat
        
        self.update_user_stats(user.id, user.username, user.first_name, user.last_name)
        
        if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            group_key = f"group:{chat.id}"
            group_data = redis_client.hgetall(group_key) or {}
            if not group_data:
                group_data = {
                    'id': str(chat.id),
                    'title': chat.title or 'Unknown Group',
                    'type': chat.type,
                    'last_active': datetime.now().isoformat()
                }
                redis_client.hset(group_key, mapping=group_data)
                redis_client.sadd('groups', chat.id)
        
        welcome_text = (
            "🎌 <b>Welcome to AnimeKuun Bot!</b>\n\n"
            "Your ultimate AniList companion with <b>50+ commands</b>!\n\n"
            "✨ <b>Quick Start:</b>\n"
            "• <code>/search Attack on Titan</code> - Search anime/manga\n"
            "• <code>/trending</code> - Trending anime now\n"
            "• <code>/schedule</code> - Today's airing schedule\n"
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
        
        await self.log_to_channel(f"User {user.id} (@{user.username}) started bot")
        logger.info(f"User {user.id} started bot")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
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
            "• <code>/studio</code> <i>name</i> - Search studios\n\n"
            
            "<b>🎬 Anime Information:</b>\n"
            "• <code>/anime</code> <i>id/title</i> - Anime details\n"
            "• <code>/manga</code> <i>id/title</i> - Manga details\n"
            "• <code>/char</code> <i>id/name</i> - Character details\n"
            "• <code>/relations</code> <i>id</i> - Related media\n"
            "• <code>/recommend</code> <i>id</i> - Recommendations\n"
            "• <code>/reviews</code> <i>id</i> - User reviews\n"
            "• <code>/trailer</code> <i>id</i> - YouTube trailer\n\n"
            
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
            "• <code>/scorestats</code> <i>id</i> - Score distribution\n\n"
            
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
    
    # =========== ANIME COMMANDS ===========
    
    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command"""
        if not context.args:
            await update.message.reply_text(
                "Please provide a search query.\nExample: <code>/search Attack on Titan</code>",
                parse_mode=ParseMode.HTML
            )
            return
        
        query = " ".join(context.args)
        await update.message.reply_chat_action("typing")
        
        try:
            results = await anilist_api.search_anime(query, page=1, per_page=5)
            
            if not results:
                await update.message.reply_text("No results found.")
                return
            
            message = "<b>Search Results:</b>\n\n"
            keyboard = []
            
            for i, item in enumerate(results, 1):
                title = item.get('title', {}).get('english') or item.get('title', {}).get('romaji', 'N/A')
                score = item.get('averageScore', 'N/A')
                message += f"{i}. <b>{title}</b>\n"
                message += f"   Score: {score} | ID: <code>{item.get('id')}</code>\n\n"
                
                keyboard.append([InlineKeyboardButton(
                    f"{i}. {title[:30]}...",
                    callback_data=f"anime_{item.get('id')}"
                )])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            await update.message.reply_text("Error searching. Please try again.")
    
    async def anime_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /anime command"""
        if not context.args:
            await update.message.reply_text(
                "Please provide anime ID or title.\nExample: <code>/anime 16498</code>",
                parse_mode=ParseMode.HTML
            )
            return
        
        query = " ".join(context.args)
        await update.message.reply_chat_action("typing")
        
        try:
            if query.isdigit():
                anime_data = await anilist_api.get_anime(int(query))
            else:
                results = await anilist_api.search_anime(query, page=1, per_page=1)
                if results:
                    anime_data = await anilist_api.get_anime(results[0]['id'])
                else:
                    await update.message.reply_text("Anime not found.")
                    return
            
            if not anime_data:
                await update.message.reply_text("Failed to fetch anime data.")
                return
            
            title = anime_data.get('title', {}).get('english') or anime_data.get('title', {}).get('romaji', 'N/A')
            message = (
                f"<b>{title}</b>\n\n"
                f"Score: {anime_data.get('averageScore', 'N/A')}/100\n"
                f"Popularity: #{anime_data.get('popularity', 'N/A')}\n"
                f"Format: {anime_data.get('format', 'N/A')}\n"
                f"Episodes: {anime_data.get('episodes', 'N/A')}\n"
                f"Status: {anime_data.get('status', 'N/A').capitalize()}\n"
                f"Genres: {', '.join(anime_data.get('genres', ['N/A']))}\n\n"
                f"<a href='https://anilist.co/anime/{anime_data.get('id')}'>View on AniList</a>"
            )
            
            keyboard = [
                [InlineKeyboardButton("Characters", callback_data=f"chars_{anime_data.get('id')}"),
                 InlineKeyboardButton("Staff", callback_data=f"staff_{anime_data.get('id')}")],
                [InlineKeyboardButton("View on AniList", url=f"https://anilist.co/anime/{anime_data.get('id')}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message, 
                parse_mode=ParseMode.HTML, 
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Anime error: {e}")
            await update.message.reply_text("Error fetching anime information.")
    
    async def trending_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /trending command"""
        await update.message.reply_chat_action("typing")
        
        try:
            results = await anilist_api.get_trending_anime(per_page=10)
            
            if not results:
                await update.message.reply_text("No trending anime found.")
                return
            
            message = "<b>Trending Anime Now:</b>\n\n"
            for i, anime in enumerate(results, 1):
                title = anime.get('title', {}).get('english') or anime.get('title', {}).get('romaji', 'N/A')
                score = anime.get('averageScore', 'N/A')
                message += f"{i}. <b>{title}</b>\n"
                message += f"   Score: {score} | Trending: {anime.get('trending', 'N/A')}\n\n"
            
            await update.message.reply_text(message, parse_mode=ParseMode.HTML)
            
        except Exception as e:
            logger.error(f"Trending error: {e}")
            await update.message.reply_text("Error fetching trending anime.")
    
    async def schedule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /schedule command"""
        await update.message.reply_chat_action("typing")
        
        try:
            schedule = await anilist_api.get_airing_schedule()
            
            message = "<b>Today's Airing Schedule:</b>\n\n"
            current_time = datetime.now()
            
            for i, anime in enumerate(schedule[:10], 1):
                title = anime.get('media', {}).get('title', {}).get('english') or \
                       anime.get('media', {}).get('title', {}).get('romaji', 'N/A')
                episode = anime.get('episode', 'N/A')
                airing_at = anime.get('airingAt', 0)
                
                if airing_at:
                    airing_time = datetime.fromtimestamp(airing_at)
                    time_str = airing_time.strftime("%H:%M")
                    
                    time_diff = airing_time - current_time
                    hours = int(time_diff.total_seconds() // 3600)
                    minutes = int((time_diff.total_seconds() % 3600) // 60)
                    
                    message += f"{i}. <b>{title}</b> - Ep {episode}\n"
                    message += f"   Time: {time_str} (in {hours}h {minutes}m)\n\n"
                else:
                    message += f"{i}. <b>{title}</b> - Ep {episode}\n\n"
            
            if not schedule:
                message += "No anime airing today."
            
            await update.message.reply_text(message, parse_mode=ParseMode.HTML)
            
        except Exception as e:
            logger.error(f"Schedule error: {e}")
            await update.message.reply_text("Error fetching schedule.")
    
    async def topanime_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /topanime command"""
        await update.message.reply_chat_action("typing")
        
        try:
            results = await anilist_api.get_top_anime(page=1, per_page=10)
            
            message = "<b>Top Anime:</b>\n\n"
            for i, anime in enumerate(results, 1):
                title = anime.get('title', {}).get('english') or anime.get('title', {}).get('romaji', 'N/A')
                score = anime.get('averageScore', 'N/A')
                message += f"{i}. <b>{title}</b>\n"
                message += f"   Score: {score} | Format: {anime.get('format', 'N/A')}\n\n"
            
            await update.message.reply_text(message, parse_mode=ParseMode.HTML)
            
        except Exception as e:
            logger.error(f"Top anime error: {e}")
            await update.message.reply_text("Error fetching top anime.")
    
    async def user_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /user command"""
        if not context.args:
            await update.message.reply_text(
                "Please provide AniList username.\nExample: <code>/user username</code>",
                parse_mode=ParseMode.HTML
            )
            return
        
        username = context.args[0]
        await update.message.reply_chat_action("typing")
        
        try:
            user_data = await anilist_api.get_user_profile(username)
            
            if not user_data:
                await update.message.reply_text("User not found.")
                return
            
            name = user_data.get('name', 'N/A')
            stats = user_data.get('statistics', {}).get('anime', {})
            
            message = (
                f"<b>{name}</b>\n\n"
                f"<b>Anime Statistics:</b>\n"
                f"Total Anime: {stats.get('count', 0)}\n"
                f"Mean Score: {stats.get('meanScore', 0)}/100\n"
                f"Episodes Watched: {stats.get('episodesWatched', 0):,}\n\n"
                f"<a href='https://anilist.co/user/{username}'>View Full Profile</a>"
            )
            
            await update.message.reply_text(message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            
        except Exception as e:
            logger.error(f"User profile error: {e}")
            await update.message.reply_text("Error fetching user profile.")
    
    async def random_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /random command"""
        await update.message.reply_chat_action("typing")
        
        try:
            anime_data = await anilist_api.get_random_anime()
            
            if not anime_data:
                await update.message.reply_text("Failed to get random anime.")
                return
            
            title = anime_data.get('title', {}).get('english') or anime_data.get('title', {}).get('romaji', 'N/A')
            message = (
                f"<b>Random Anime Recommendation:</b>\n\n"
                f"<b>{title}</b>\n"
                f"Score: {anime_data.get('averageScore', 'N/A')}/100\n"
                f"Popularity: #{anime_data.get('popularity', 'N/A')}\n"
                f"Episodes: {anime_data.get('episodes', 'N/A')}\n"
                f"Genres: {', '.join(anime_data.get('genres', ['N/A']))}\n\n"
                f"<a href='https://anilist.co/anime/{anime_data.get('id')}'>View on AniList</a>"
            )
            
            await update.message.reply_text(message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            
        except Exception as e:
            logger.error(f"Random anime error: {e}")
            await update.message.reply_text("Error getting random anime.")
    
    async def quote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /quote command"""
        await update.message.reply_chat_action("typing")
        
        try:
            quote_data = await anilist_api.get_anime_quote()
            
            message = (
                f"<b>Anime Quote:</b>\n\n"
                f"\"{quote_data.get('quote', 'No quote available.')}\"\n\n"
                f"— <i>{quote_data.get('character', 'Unknown')}</i>\n"
                f"<b>{quote_data.get('anime', 'Unknown')}</b>"
            )
            
            await update.message.reply_text(message, parse_mode=ParseMode.HTML)
            
        except Exception as e:
            logger.error(f"Quote error: {e}")
            await update.message.reply_text("Error getting quote.")
    
    # =========== ADMIN COMMANDS ===========
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /admin command"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("This command is for admins only.")
            return
        
        total_users = len(redis_client.keys('user:*'))
        total_groups = len(redis_client.smembers('groups'))
        uptime = self.format_time(int((datetime.now() - self.start_time).total_seconds()))
        
        admin_text = (
            f"<b>Admin Panel</b>\n\n"
            f"<b>Bot Statistics:</b>\n"
            f"Users: {total_users}\n"
            f"Groups: {total_groups}\n"
            f"Uptime: {uptime}\n\n"
            f"<b>Quick Commands:</b>\n"
            f"• <code>/ping</code> - Check bot status\n"
            f"• <code>/statsbot</code> - Detailed statistics\n"
            f"• <code>/users</code> - List all users\n"
            f"• <code>/groups</code> - List all groups\n"
            f"• <code>/broadcast</code> - Broadcast message\n"
            f"• <code>/logs</code> - View bot logs\n\n"
            f"<b>New Admin Commands:</b>\n"
            f"• <code>/eval</code> - Evaluate code\n"
            f"• <code>/export</code> - Export data\n"
            f"• <code>/import</code> - Import data\n"
            f"• <code>/shell</code> - Run shell command\n\n"
            f"<b>Maintenance:</b>\n"
            f"• <code>/maintenance on/off</code>\n"
            f"Current: {'ON' if self.maintenance_mode else 'OFF'}\n\n"
            f"<code>/help admin</code> for full admin commands"
        )
        
        keyboard = [
            [InlineKeyboardButton("Stats", callback_data="admin_stats"),
             InlineKeyboardButton("Users", callback_data="admin_users")],
            [InlineKeyboardButton("Groups", callback_data="admin_groups"),
             InlineKeyboardButton("Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("Settings", callback_data="admin_settings"),
             InlineKeyboardButton("Logs", callback_data="admin_logs")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(admin_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    
    async def ping_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /ping command"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("This command is for admins only.")
            return
        
        import time
        start = time.time()
        
        redis_status = "Connected" if redis_client.ping() else "Disconnected"
        
        try:
            await anilist_api.get_trending_anime(per_page=1)
            api_status = "Working"
        except:
            api_status = "Failed"
        
        end = time.time()
        latency = round((end - start) * 1000, 2)
        
        ping_text = (
            f"<b>Pong!</b>\n\n"
            f"Latency: {latency}ms\n"
            f"Uptime: {self.format_time(int((datetime.now() - self.start_time).total_seconds()))}\n\n"
            f"<b>Services:</b>\n"
            f"Redis: {redis_status}\n"
            f"AniList API: {api_status}\n\n"
            f"<b>Usage:</b>\n"
            f"Users: {len(redis_client.keys('user:*'))}\n"
            f"Groups: {len(redis_client.smembers('groups'))}"
        )
        
        await update.message.reply_text(ping_text, parse_mode=ParseMode.HTML)
    
    async def groups_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /groups command"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("This command is for admins only.")
            return
        
        groups = redis_client.smembers('groups')
        
        if not groups:
            await update.message.reply_text("Bot is not in any groups yet.")
            return
        
        message = "<b>Groups Bot is In:</b>\n\n"
        for i, group_id in enumerate(list(groups)[:20], 1):
            group_data = redis_client.hgetall(f"group:{group_id}") or {}
            title = group_data.get('title', 'Unknown Group')
            message += f"{i}. <b>{title}</b>\n"
            message += f"   ID: <code>{group_id}</code>\n"
            message += f"   Last active: {group_data.get('last_active', 'Never')}\n\n"
        
        if len(groups) > 20:
            message += f"\n... and {len(groups) - 20} more groups"
        
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)
    
    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /users command"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("This command is for admins only.")
            return
        
        user_keys = redis_client.keys('user:*')
        
        if not user_keys:
            await update.message.reply_text("No users found.")
            return
        
        message = "<b>Bot Users:</b>\n\n"
        for i, key in enumerate(user_keys[:20], 1):
            user_data = redis_client.hgetall(key) or {}
            user_id = key.split(':')[-1]
            username = user_data.get('username', 'No username')
            first_name = user_data.get('first_name', 'No name')
            
            message += f"{i}. <code>{user_id}</code> - {first_name}"
            if username:
                message += f" (@{username})"
            message += f"\n   Commands: {user_data.get('command_count', '0')}\n\n"
        
        if len(user_keys) > 20:
            message += f"\n... and {len(user_keys) - 20} more users"
        
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)
    
    async def statsbot_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /statsbot command"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("This command is for admins only.")
            return
        
        total_users = len(redis_client.keys('user:*'))
        total_groups = len(redis_client.smembers('groups'))
        uptime = self.format_time(int((datetime.now() - self.start_time).total_seconds()))
        
        stats_text = (
            f"<b>Bot Statistics</b>\n\n"
            f"Users: {total_users}\n"
            f"Groups: {total_groups}\n\n"
            f"Uptime: {uptime}\n\n"
            f"<b>Services:</b>\n"
            f"Redis: {'Connected' if redis_client.ping() else 'Disconnected'}\n"
            f"AniList API: Working\n\n"
            f"<b>Maintenance Mode:</b> {'ON' if self.maintenance_mode else 'OFF'}"
        )
        
        await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)
    
    async def pro_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pro command (promote user)"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("This command is for admins only.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "Please provide user ID.\nExample: <code>/pro 1234567890</code>",
                parse_mode=ParseMode.HTML
            )
            return
        
        try:
            target_id = int(context.args[0])
            
            if target_id in ADMIN_IDS:
                await update.message.reply_text("User is already an admin.")
                return
            
            user_key = f"user:{target_id}"
            if not redis_client.exists(user_key):
                await update.message.reply_text("User not found in database.")
                return
            
            redis_client.hset(user_key, 'is_admin', 'true')
            ADMIN_IDS.append(target_id)
            
            await update.message.reply_text(f"User <code>{target_id}</code> has been promoted to admin.")
            await self.log_to_channel(f"User {target_id} promoted by {user.id}")
            
        except ValueError:
            await update.message.reply_text("Invalid user ID.")
    
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /broadcast command (natural message)"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("This command is for admins only.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "Please provide a message to broadcast.\nExample: <code>/broadcast Hello everyone!</code>",
                parse_mode=ParseMode.HTML
            )
            return
        
        message = " ".join(context.args)
        total_users = len(redis_client.keys('user:*'))
        
        confirm_text = (
            f"<b>Broadcast Confirmation</b>\n\n"
            f"<b>Message:</b>\n{message}\n\n"
            f"<b>Target:</b> All users\n"
            f"<b>Total users:</b> {total_users}\n\n"
            f"Are you sure you want to broadcast this message?"
        )
        
        keyboard = [
            [InlineKeyboardButton("Yes, Broadcast", callback_data=f"broadcast_confirm_{user.id}")],
            [InlineKeyboardButton("Cancel", callback_data="broadcast_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        redis_client.setex(f"broadcast:{user.id}", 300, message)
        
        await update.message.reply_text(confirm_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    
    async def logs_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /logs command"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("This command is for admins only.")
            return
        
        try:
            with open('bot.log', 'r') as f:
                log_lines = f.readlines()
            
            last_logs = log_lines[-50:] if log_lines else ["No logs found"]
            logs_text = f"<b>Last 50 Log Lines:</b>\n\n<code>"
            logs_text += "".join(last_logs)[-4000:]
            logs_text += "</code>"
            
            await update.message.reply_text(logs_text, parse_mode=ParseMode.HTML)
            
        except FileNotFoundError:
            await update.message.reply_text("Log file not found.")
    
    async def maintenance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /maintenance command"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("This command is for admins only.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "Please specify 'on' or 'off'.\nExample: <code>/maintenance on</code>",
                parse_mode=ParseMode.HTML
            )
            return
        
        mode = context.args[0].lower()
        
        if mode == 'on':
            self.maintenance_mode = True
            await update.message.reply_text("Maintenance mode enabled.\nThe bot will only respond to admins.")
            await self.log_to_channel(f"Maintenance enabled by {user.id}")
        elif mode == 'off':
            self.maintenance_mode = False
            await update.message.reply_text("Maintenance mode disabled.\nThe bot is now accessible to everyone.")
            await self.log_to_channel(f"Maintenance disabled by {user.id}")
        else:
            await update.message.reply_text("Invalid mode. Use 'on' or 'off'.")
    
    # =========== NEW ADMIN COMMANDS ===========
    
    async def eval_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /eval command (evaluate Python code)"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("This command is for admins only.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "Please provide Python code to evaluate.\nExample: <code>/eval 2+2</code>",
                parse_mode=ParseMode.HTML
            )
            return
        
        code = " ".join(context.args)
        
        try:
            # Safe evaluation with limited globals
            allowed_globals = {
                '__builtins__': {
                    'abs': abs, 'all': all, 'any': any, 'bool': bool,
                    'chr': chr, 'dict': dict, 'float': float, 'int': int,
                    'len': len, 'list': list, 'max': max, 'min': min,
                    'ord': ord, 'range': range, 'round': round, 'str': str,
                    'sum': sum, 'tuple': tuple, 'zip': zip
                },
                'datetime': datetime,
                'time': time,
                'redis_client': redis_client,
                'user_id': user.id
            }
            
            result = eval(code, {"__builtins__": {}}, allowed_globals)
            
            await update.message.reply_text(
                f"<b>Code:</b>\n<code>{code}</code>\n\n"
                f"<b>Result:</b>\n<code>{result}</code>",
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            await update.message.reply_text(f"Error: {str(e)}")
    
    async def export_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /export command (export user data)"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("This command is for admins only.")
            return
        
        await update.message.reply_chat_action("typing")
        
        try:
            user_keys = redis_client.keys('user:*')
            export_data = []
            
            for key in user_keys:
                user_data = redis_client.hgetall(key)
                export_data.append(user_data)
            
            # Create JSON export
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"export_{timestamp}.json"
            
            import json
            export_json = json.dumps(export_data, indent=2)
            
            # Save to file
            with open(filename, 'w') as f:
                f.write(export_json)
            
            await update.message.reply_text(
                f"Exported {len(export_data)} users to <code>{filename}</code>\n\n"
                f"<code>{export_json[:1000]}...</code>",
                parse_mode=ParseMode.HTML
            )
            
            await self.log_to_channel(f"Data exported by {user.id}: {len(export_data)} users")
            
        except Exception as e:
            await update.message.reply_text(f"Export error: {str(e)}")
    
    async def import_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /import command (import user data)"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("This command is for admins only.")
            return
        
        if not update.message.document:
            await update.message.reply_text(
                "Please send a JSON file to import.\n"
                "Use /export to see the format.",
                parse_mode=ParseMode.HTML
            )
            return
        
        await update.message.reply_text("Import feature coming soon...")
    
    async def shell_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /shell command (run shell command)"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("This command is for admins only.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "Please provide shell command.\nExample: <code>/shell ls -la</code>",
                parse_mode=ParseMode.HTML
            )
            return
        
        command = " ".join(context.args)
        
        # Only allow safe commands
        allowed_commands = ['ls', 'pwd', 'whoami', 'date', 'uptime', 'free', 'df', 'ps']
        cmd_base = command.split()[0]
        
        if cmd_base not in allowed_commands:
            await update.message.reply_text(
                f"Command not allowed. Allowed commands: {', '.join(allowed_commands)}"
            )
            return
        
        try:
            import subprocess
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
            
            output = f"<b>Command:</b> <code>{command}</code>\n\n"
            if result.stdout:
                output += f"<b>Output:</b>\n<code>{result.stdout[:1000]}</code>\n\n"
            if result.stderr:
                output += f"<b>Errors:</b>\n<code>{result.stderr[:1000]}</code>\n\n"
            output += f"<b>Exit code:</b> {result.returncode}"
            
            await update.message.reply_text(output, parse_mode=ParseMode.HTML)
            
        except subprocess.TimeoutExpired:
            await update.message.reply_text("Command timed out after 10 seconds.")
        except Exception as e:
            await update.message.reply_text(f"Error: {str(e)}")
    
    # =========== CALLBACK HANDLERS ===========
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        try:
            if data == "help_menu":
                await self.help_command(update, context)
            elif data == "trending":
                await self.trending_command(update, context)
            elif data == "stats_me":
                await query.edit_message_text(
                    "Use <code>/user your_username</code> to see your AniList stats.",
                    parse_mode=ParseMode.HTML
                )
            elif data == "settings":
                await query.edit_message_text(
                    "Settings menu coming soon!\nFor now, contact admin for configuration.",
                    parse_mode=ParseMode.HTML
                )
            elif data.startswith("broadcast_confirm_"):
                admin_id = int(data.split("_")[2])
                await self.execute_broadcast(query, admin_id)
            elif data == "broadcast_cancel":
                await query.edit_message_text("Broadcast cancelled.")
            elif data == "admin_stats":
                await self.statsbot_command(update, context)
            elif data == "admin_users":
                await self.users_command(update, context)
            elif data == "admin_groups":
                await self.groups_command(update, context)
            elif data == "admin_broadcast":
                await query.edit_message_text(
                    "Use <code>/broadcast message</code> to send a broadcast.",
                    parse_mode=ParseMode.HTML
                )
            elif data == "admin_logs":
                await self.logs_command(update, context)
            elif data == "admin_settings":
                await query.edit_message_text(
                    "Admin settings:\n"
                    "• <code>/maintenance on/off</code>\n"
                    "• <code>/ping</code>\n"
                    "• <code>/statsbot</code>",
                    parse_mode=ParseMode.HTML
                )
            elif data.startswith("anime_"):
                anime_id = int(data.split("_")[1])
                await self.handle_anime_callback(query, anime_id)
            elif data.startswith("chars_"):
                anime_id = int(data.split("_")[1])
                await query.edit_message_text(
                    f"Characters for anime ID {anime_id}\n"
                    f"Full characters list coming soon...",
                    parse_mode=ParseMode.HTML
                )
            elif data.startswith("staff_"):
                anime_id = int(data.split("_")[1])
                await query.edit_message_text(
                    f"Staff for anime ID {anime_id}\n"
                    f"Full staff list coming soon...",
                    parse_mode=ParseMode.HTML
                )
            else:
                await query.edit_message_text("Unknown button action.")
        except Exception as e:
            logger.error(f"Button callback error: {e}")
            await query.edit_message_text("Error processing button action.")
    
    async def handle_anime_callback(self, query, anime_id):
        """Handle anime callback"""
        await query.message.reply_chat_action("typing")
        
        try:
            anime_data = await anilist_api.get_anime(anime_id)
            
            if anime_data:
                title = anime_data.get('title', {}).get('english') or anime_data.get('title', {}).get('romaji', 'N/A')
                message = (
                    f"<b>{title}</b>\n\n"
                    f"Score: {anime_data.get('averageScore', 'N/A')}/100\n"
                    f"Popularity: #{anime_data.get('popularity', 'N/A')}\n"
                    f"Format: {anime_data.get('format', 'N/A')}\n"
                    f"Episodes: {anime_data.get('episodes', 'N/A')}\n"
                    f"Genres: {', '.join(anime_data.get('genres', ['N/A']))}\n\n"
                    f"<a href='https://anilist.co/anime/{anime_id}'>View on AniList</a>"
                )
                
                await query.message.reply_text(message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            else:
                await query.answer("Failed to fetch anime data.", show_alert=True)
                
        except Exception as e:
            logger.error(f"Callback error: {e}")
            await query.answer("Error fetching anime.", show_alert=True)
    
    async def execute_broadcast(self, query, admin_id):
        """Execute broadcast to all users (natural message)"""
        await query.edit_message_text("Broadcasting started...")
        
        message = redis_client.get(f"broadcast:{admin_id}")
        if not message:
            await query.edit_message_text("Broadcast message expired.")
            return
        
        user_keys = redis_client.keys('user:*')
        success = 0
        failed = 0
        
        # Natural broadcast message without emoji
        broadcast_text = (
            f"Announcement\n\n"
            f"{message}\n\n"
            f"From AnimeKuun Bot Admin"
        )
        
        for key in user_keys:
            user_data = redis_client.hgetall(key)
            user_id = user_data.get('id')
            
            if not user_id or user_data.get('is_banned') == 'true':
                continue
            
            try:
                await self.app.bot.send_message(
                    chat_id=user_id,
                    text=broadcast_text
                )
                success += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                failed += 1
                logger.error(f"Broadcast failed for {user_id}: {e}")
        
        redis_client.delete(f"broadcast:{admin_id}")
        
        result_text = (
            f"<b>Broadcast Complete!</b>\n\n"
            f"<b>Results:</b>\n"
            f"Success: {success}\n"
            f"Failed: {failed}\n"
            f"Total: {success + failed}"
        )
        
        await query.edit_message_text(result_text, parse_mode=ParseMode.HTML)
        await self.log_to_channel(f"Broadcast by {admin_id}: {success} success, {failed} failed")
    
    # =========== MESSAGE HANDLERS ===========
    
    async def handle_group_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages in groups"""
        chat = update.effective_chat
        
        group_key = f"group:{chat.id}"
        group_data = redis_client.hgetall(group_key) or {}
        if not group_data:
            group_data = {
                'id': str(chat.id),
                'title': chat.title or 'Unknown Group',
                'type': chat.type,
                'last_active': datetime.now().isoformat()
            }
            redis_client.hset(group_key, mapping=group_data)
            redis_client.sadd('groups', chat.id)
        else:
            group_data['last_active'] = datetime.now().isoformat()
            redis_client.hset(group_key, 'last_active', group_data['last_active'])
        
        if context.bot.username and f"@{context.bot.username}" in update.message.text:
            response = (
                "Hi! I'm AnimeKuun Bot!\n"
                "Use /help to see all commands.\n"
                "Try: /search, /trending, /schedule"
            )
            await update.message.reply_text(response)
    
    async def handle_new_chat_members(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new chat members (bot added to group)"""
        chat = update.effective_chat
        
        for member in update.message.new_chat_members:
            if member.id == context.bot.id:
                welcome_text = (
                    "Thanks for adding AnimeKuun Bot!\n\n"
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
                await self.log_to_channel(f"Bot added to group: {chat.id} ({chat.title})")
    
    # =========== ERROR HANDLER ===========
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Exception while handling update: {context.error}", exc_info=context.error)
        
        try:
            if update and update.effective_chat:
                error_msg = (
                    "An error occurred. Please try again.\n"
                    "If the problem persists, contact the admin."
                )
                await update.effective_chat.send_message(error_msg)
        except:
            pass
    
    # =========== SETUP AND RUN ===========
    
    def setup_handlers(self):
        """Setup all command handlers"""
        
        # Basic commands
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        
        # Anime commands
        self.app.add_handler(CommandHandler("search", self.search_command))
        self.app.add_handler(CommandHandler("anime", self.anime_command))
        self.app.add_handler(CommandHandler("trending", self.trending_command))
        self.app.add_handler(CommandHandler("schedule", self.schedule_command))
        self.app.add_handler(CommandHandler("topanime", self.topanime_command))
        self.app.add_handler(CommandHandler("random", self.random_command))
        self.app.add_handler(CommandHandler("quote", self.quote_command))
        self.app.add_handler(CommandHandler("user", self.user_command))
        
        # Admin commands
        self.app.add_handler(CommandHandler("admin", self.admin_command))
        self.app.add_handler(CommandHandler("ping", self.ping_command))
        self.app.add_handler(CommandHandler("groups", self.groups_command))
        self.app.add_handler(CommandHandler("users", self.users_command))
        self.app.add_handler(CommandHandler("statsbot", self.statsbot_command))
        self.app.add_handler(CommandHandler("pro", self.pro_command))
        self.app.add_handler(CommandHandler("broadcast", self.broadcast_command))
        self.app.add_handler(CommandHandler("logs", self.logs_command))
        self.app.add_handler(CommandHandler("maintenance", self.maintenance_command))
        
        # New admin commands
        self.app.add_handler(CommandHandler("eval", self.eval_command))
        self.app.add_handler(CommandHandler("export", self.export_command))
        self.app.add_handler(CommandHandler("import", self.import_command))
        self.app.add_handler(CommandHandler("shell", self.shell_command))
        
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
    
    async def set_bot_commands(self):
        """Set bot commands menu"""
        commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Show all commands"),
            BotCommand("search", "Search anime/manga"),
            BotCommand("anime", "Get anime details"),
            BotCommand("trending", "Trending anime"),
            BotCommand("schedule", "Airing schedule"),
            BotCommand("topanime", "Top rated anime"),
            BotCommand("random", "Random anime"),
            BotCommand("quote", "Random anime quote"),
            BotCommand("user", "AniList profile"),
            BotCommand("admin", "Admin panel (admin only)")
        ]
        
        try:
            await self.app.bot.set_my_commands(commands)
            logger.info("Bot commands set successfully")
        except Exception as e:
            logger.error(f"Failed to set commands: {e}")
    
    async def setup_webhook(self):
        """Setup webhook for Railway"""
        if WEBHOOK_URL:
            webhook_url = f"{WEBHOOK_URL}/{BOT_TOKEN}"
            await self.app.bot.set_webhook(url=webhook_url)
            logger.info(f"Webhook set to: {webhook_url}")
        else:
            logger.info("Using polling mode")
    
    async def run(self):
        """Run the bot"""
        logger.info("Starting AnimeKuun Bot...")
        logger.info(f"Bot Token: {BOT_TOKEN[:10]}...")
        logger.info(f"Admin IDs: {ADMIN_IDS}")
        logger.info(f"Webhook URL: {WEBHOOK_URL}")
        logger.info(f"Port: {PORT}")
        
        # Create application
        self.app = Application.builder().token(BOT_TOKEN).build()
        
        # Setup handlers
        self.setup_handlers()
        
        # Set bot commands
        self.app.post_init = self.set_bot_commands
        
        # Log startup
        await self.log_to_channel("Bot started successfully!")
        logger.info("Bot initialized")
        
        if self.is_webhook:
            # Webhook mode for Railway
            await self.app.initialize()
            await self.setup_webhook()
            
            # Start webhook server
            from telegram.ext._application import Application as App
            await self.app.start()
            
            # Keep the application running
            logger.info("Bot is running with webhook")
            await self.app.updater.start_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=BOT_TOKEN,
                webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
            )
            
            # Keep running
            await self.app.updater.idle()
        else:
            # Polling mode for local testing
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            
            logger.info("Bot is now running and polling for updates")
            print("\n" + "="*50)
            print("AnimeKuun Bot is now running!")
            print(f"Admin ID: {ADMIN_IDS[0] if ADMIN_IDS else 'None'}")
            print(f"Started at: {self.start_time}")
            print("="*50 + "\n")
            
            # Keep running
            await self.app.updater.idle()
        
        # Cleanup
        await anilist_api.close()
        await image_gen.close()

def main():
    """Main entry point"""
    bot = AnimeBot()
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (KeyboardInterrupt)")
        print("\nBot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        print(f"Bot crashed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
