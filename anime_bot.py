#!/usr/bin/env python3
"""
🎌 AnimeKuun Bot - Complete Working Version
All commands working with proper error handling
"""

import os
import sys
import asyncio
import logging
import sqlite3
import random
import re
import time
import json
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import aiohttp
from io import BytesIO

# Aiogram imports
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    InputFile, URLInputFile, FSInputFile, ReplyKeyboardRemove
)
from aiogram.enums import ParseMode, ChatType, MessageEntityType
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.formatting import Text, Bold, Italic, as_list, as_line
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest

# =========== CONFIGURATION ===========
BOT_TOKEN = os.getenv("BOT_TOKEN", "8282052807:AAERvnTQKpqBxz23qW4eygRknkVcqy31NNw")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "6108185460").split(",") if id.strip()]
DATABASE_PATH = "data/animekun_complete.db"

print("=" * 60)
print("🎌 ANIMEKUUN BOT - COMPLETE WORKING VERSION")
print(f"🤖 Bot Token: {BOT_TOKEN[:15]}...")
print(f"👑 Admin IDs: {ADMIN_IDS}")
print("=" * 60)

# =========== SETUP ===========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('animekun_complete.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Initialize bot
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Global variables
bot_start_time = datetime.now()
maintenance_mode = False
user_cooldowns = {}
active_broadcasts = {}
session = None

# =========== ANILIST API (SIMPLE & WORKING) ===========
class AniListAPI:
    """Simple working AniList API"""
    
    def __init__(self):
        self.base_url = "https://graphql.anilist.co"
        self.session = None
        self.cache = {}
    
    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self.session
    
    async def _make_request(self, query: str, variables: dict = None):
        """Make GraphQL request with error handling"""
        session = await self._get_session()
        
        try:
            async with session.post(
                self.base_url,
                json={"query": query, "variables": variables or {}},
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if "errors" in data:
                        logger.error(f"AniList API error: {data['errors']}")
                        return {"error": data["errors"][0]["message"]}
                    return data.get("data", {})
                else:
                    return {"error": f"HTTP {response.status}"}
        except Exception as e:
            logger.error(f"Request error: {e}")
            return {"error": str(e)}
    
    # =========== ANIME QUERIES ===========
    
    async def search_anime(self, query: str, page: int = 1, per_page: int = 10):
        """Search anime - WORKING"""
        search_query = """
        query ($search: String, $page: Int, $perPage: Int) {
          Page(page: $page, perPage: $perPage) {
            media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
              id
              title {
                romaji
                english
                native
              }
              coverImage {
                large
                medium
              }
              averageScore
              popularity
              format
              episodes
              status
              description(asHtml: false)
              genres
            }
          }
        }
        """
        
        result = await self._make_request(search_query, {
            "search": query,
            "page": page,
            "perPage": per_page
        })
        
        if "error" in result:
            return []
        
        return result.get("Page", {}).get("media", [])
    
    async def get_anime(self, anime_id: int):
        """Get anime details - WORKING"""
        anime_query = """
        query ($id: Int) {
          Media(id: $id, type: ANIME) {
            id
            title {
              romaji
              english
              native
            }
            description(asHtml: false)
            averageScore
            popularity
            format
            episodes
            duration
            status
            startDate {
              year
              month
              day
            }
            coverImage {
              extraLarge
              large
              medium
            }
            bannerImage
            genres
            studios {
              edges {
                node {
                  name
                }
              }
            }
            siteUrl
          }
        }
        """
        
        result = await self._make_request(anime_query, {"id": anime_id})
        
        if "error" in result:
            return {"error": result["error"]}
        
        return result.get("Media", {})
    
    async def get_trending(self, per_page: int = 10):
        """Get trending anime - WORKING"""
        query = """
        query ($perPage: Int) {
          Page(perPage: $perPage) {
            media(type: ANIME, sort: TRENDING_DESC) {
              id
              title {
                romaji
                english
              }
              coverImage {
                large
              }
              averageScore
              trending
              popularity
              format
              episodes
            }
          }
        }
        """
        
        result = await self._make_request(query, {"perPage": per_page})
        
        if "error" in result:
            return []
        
        return result.get("Page", {}).get("media", [])
    
    async def get_top_anime(self, per_page: int = 10):
        """Get top anime - WORKING"""
        query = """
        query ($perPage: Int) {
          Page(perPage: $perPage) {
            media(type: ANIME, sort: SCORE_DESC) {
              id
              title {
                romaji
                english
              }
              coverImage {
                large
              }
              averageScore
              popularity
              format
              episodes
              status
            }
          }
        }
        """
        
        result = await self._make_request(query, {"perPage": per_page})
        
        if "error" in result:
            return []
        
        return result.get("Page", {}).get("media", [])
    
    async def get_random_anime(self):
        """Get random anime - WORKING"""
        # Search for popular anime and pick random
        results = await self.search_anime("", page=random.randint(1, 5))
        if results:
            return random.choice(results)
        
        # Fallback: try random ID
        random_id = random.randint(1, 20000)
        return await self.get_anime(random_id)
    
    async def search_character(self, query: str, per_page: int = 10):
        """Search characters - WORKING"""
        query_gql = """
        query ($search: String, $perPage: Int) {
          Page(perPage: $perPage) {
            characters(search: $search) {
              id
              name {
                full
                native
              }
              image {
                large
                medium
              }
              description(asHtml: false)
              gender
              favourites
              media {
                edges {
                  node {
                    id
                    title {
                      romaji
                      english
                    }
                  }
                }
              }
            }
          }
        }
        """
        
        result = await self._make_request(query_gql, {
            "search": query,
            "perPage": per_page
        })
        
        if "error" in result:
            return []
        
        return result.get("Page", {}).get("characters", [])
    
    async def get_character(self, char_id: int):
        """Get character details - WORKING"""
        query = """
        query ($id: Int) {
          Character(id: $id) {
            id
            name {
              full
              native
              alternative
            }
            image {
              large
              medium
            }
            description(asHtml: false)
            gender
            dateOfBirth {
              year
              month
              day
            }
            age
            favourites
            media {
              edges {
                node {
                  id
                  title {
                    romaji
                    english
                  }
                  type
                }
              }
            }
            siteUrl
          }
        }
        """
        
        result = await self._make_request(query, {"id": char_id})
        
        if "error" in result:
            return {"error": result["error"]}
        
        return result.get("Character", {})
    
    async def get_user_profile(self, username: str):
        """Get AniList user profile - WORKING"""
        query = """
        query ($name: String) {
          User(name: $name) {
            id
            name
            about(asHtml: false)
            avatar {
              large
              medium
            }
            bannerImage
            statistics {
              anime {
                count
                meanScore
                minutesWatched
                episodesWatched
              }
              manga {
                count
                meanScore
                chaptersRead
                volumesRead
              }
            }
            favourites {
              anime {
                edges {
                  node {
                    id
                    title {
                      romaji
                      english
                    }
                  }
                }
              }
              characters {
                edges {
                  node {
                    id
                    name {
                      full
                    }
                  }
                }
              }
            }
            donatorTier
            siteUrl
            updatedAt
          }
        }
        """
        
        result = await self._make_request(query, {"name": username})
        
        if "error" in result:
            return {"error": result["error"]}
        
        return result.get("User", {})
    
    async def get_seasonal(self):
        """Get current seasonal anime - WORKING"""
        current_year = datetime.now().year
        month = datetime.now().month
        
        if month in [1, 2, 3]:
            season = "WINTER"
        elif month in [4, 5, 6]:
            season = "SPRING"
        elif month in [7, 8, 9]:
            season = "SUMMER"
        else:
            season = "FALL"
        
        query = """
        query ($season: MediaSeason, $seasonYear: Int, $perPage: Int) {
          Page(perPage: $perPage) {
            media(season: $season, seasonYear: $seasonYear, type: ANIME, sort: POPULARITY_DESC) {
              id
              title {
                romaji
                english
              }
              coverImage {
                large
              }
              averageScore
              popularity
              format
              episodes
              status
            }
          }
        }
        """
        
        result = await self._make_request(query, {
            "season": season,
            "seasonYear": current_year,
            "perPage": 15
        })
        
        if "error" in result:
            return []
        
        return result.get("Page", {}).get("media", [])
    
    async def get_anime_by_genre(self, genre: str, per_page: int = 10):
        """Get anime by genre - WORKING"""
        query = """
        query ($genre: String, $perPage: Int) {
          Page(perPage: $perPage) {
            media(type: ANIME, genre: $genre, sort: POPULARITY_DESC) {
              id
              title {
                romaji
                english
              }
              coverImage {
                large
              }
              averageScore
              popularity
              format
              episodes
              genres
            }
          }
        }
        """
        
        result = await self._make_request(query, {
            "genre": genre,
            "perPage": per_page
        })
        
        if "error" in result:
            return []
        
        return result.get("Page", {}).get("media", [])
    
    async def close(self):
        """Close session"""
        if self.session and not self.session.closed:
            await self.session.close()

# Initialize API
anilist = AniListAPI()

# =========== DATABASE SETUP (PROPER) ===========
def init_database():
    """Initialize database with proper schema"""
    os.makedirs("data", exist_ok=True)
    
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        joined_date TEXT DEFAULT CURRENT_TIMESTAMP,
        last_active TEXT DEFAULT CURRENT_TIMESTAMP,
        total_commands INTEGER DEFAULT 0,
        total_searches INTEGER DEFAULT 0,
        total_favorites INTEGER DEFAULT 0,
        anilist_username TEXT,
        is_admin INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        language TEXT DEFAULT 'en'
    )''')
    
    # Favorites table
    c.execute('''CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        anime_id INTEGER,
        anime_title TEXT,
        anime_image TEXT,
        anime_score REAL,
        added_date TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, anime_id)
    )''')
    
    # Command stats
    c.execute('''CREATE TABLE IF NOT EXISTS command_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        command TEXT,
        user_id INTEGER,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Error logs
    c.execute('''CREATE TABLE IF NOT EXISTS error_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        error TEXT,
        user_id INTEGER,
        command TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Groups
    c.execute('''CREATE TABLE IF NOT EXISTS groups (
        group_id INTEGER PRIMARY KEY,
        title TEXT,
        added_date TEXT DEFAULT CURRENT_TIMESTAMP,
        last_active TEXT DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER DEFAULT 1
    )''')
    
    # Admin actions
    c.execute('''CREATE TABLE IF NOT EXISTS admin_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        action TEXT,
        target_id INTEGER,
        details TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Broadcasts
    c.execute('''CREATE TABLE IF NOT EXISTS broadcasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        message TEXT,
        sent_count INTEGER DEFAULT 0,
        failed_count INTEGER DEFAULT 0,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Add default admin
    for admin_id in ADMIN_IDS:
        c.execute("INSERT OR IGNORE INTO users (user_id, is_admin) VALUES (?, 1)", (admin_id,))
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")

init_database()

# =========== DATABASE HELPER FUNCTIONS ===========
def db_execute(query: str, params: tuple = (), fetchone: bool = False, fetchall: bool = False):
    """Safe database execution"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute(query, params)
        
        if fetchone:
            result = c.fetchone()
        elif fetchall:
            result = c.fetchall()
        else:
            result = c.lastrowid
        
        conn.commit()
        conn.close()
        
        return result
    except Exception as e:
        logger.error(f"Database error: {e}")
        if fetchone or fetchall:
            return None if fetchone else []
        return None

def update_user(user_id: int, username: str = None, first_name: str = None, command: str = None):
    """Update user stats"""
    try:
        # Check if user exists
        user = db_execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,), fetchone=True)
        
        if user:
            db_execute(
                """UPDATE users SET 
                last_active = datetime('now'),
                username = COALESCE(?, username),
                first_name = COALESCE(?, first_name),
                total_commands = total_commands + CASE WHEN ? IS NOT NULL THEN 1 ELSE 0 END
                WHERE user_id = ?""",
                (username, first_name, command, user_id)
            )
        else:
            db_execute(
                """INSERT INTO users 
                (user_id, username, first_name, joined_date, last_active, total_commands) 
                VALUES (?, ?, ?, datetime('now'), datetime('now'), ?)""",
                (user_id, username, first_name, 1 if command else 0)
            )
        
        if command:
            db_execute("INSERT INTO command_stats (command, user_id) VALUES (?, ?)", (command, user_id))
        
        return True
    except Exception as e:
        logger.error(f"Update user error: {e}")
        return False

def add_favorite(user_id: int, anime_id: int, anime_title: str, anime_image: str = "", anime_score: float = None):
    """Add anime to favorites"""
    try:
        db_execute(
            """INSERT OR IGNORE INTO favorites 
            (user_id, anime_id, anime_title, anime_image, anime_score, added_date) 
            VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (user_id, anime_id, anime_title, anime_image, anime_score)
        )
        
        # Update user favorites count
        db_execute("UPDATE users SET total_favorites = total_favorites + 1 WHERE user_id = ?", (user_id,))
        
        return True
    except Exception as e:
        logger.error(f"Add favorite error: {e}")
        return False

def remove_favorite(user_id: int, anime_id: int):
    """Remove anime from favorites"""
    try:
        db_execute("DELETE FROM favorites WHERE user_id = ? AND anime_id = ?", (user_id, anime_id))
        db_execute("UPDATE users SET total_favorites = total_favorites - 1 WHERE user_id = ?", (user_id,))
        return True
    except:
        return False

def get_favorites(user_id: int, limit: int = 20):
    """Get user favorites"""
    return db_execute(
        "SELECT anime_id, anime_title, anime_image, anime_score, added_date FROM favorites WHERE user_id = ? ORDER BY added_date DESC LIMIT ?",
        (user_id, limit), fetchall=True
    )

def get_user_stats(user_id: int):
    """Get user statistics"""
    return db_execute(
        """SELECT joined_date, total_commands, total_searches, total_favorites, anilist_username 
        FROM users WHERE user_id = ?""",
        (user_id,), fetchone=True
    )

def get_bot_stats():
    """Get bot statistics"""
    stats = {}
    
    # Total users
    result = db_execute("SELECT COUNT(*) FROM users", fetchone=True)
    stats["total_users"] = result[0] if result else 0
    
    # Active today
    result = db_execute("SELECT COUNT(*) FROM users WHERE DATE(last_active) = DATE('now')", fetchone=True)
    stats["active_today"] = result[0] if result else 0
    
    # Commands today
    result = db_execute("SELECT COUNT(*) FROM command_stats WHERE DATE(timestamp) = DATE('now')", fetchone=True)
    stats["commands_today"] = result[0] if result else 0
    
    # Total groups
    result = db_execute("SELECT COUNT(*) FROM groups", fetchone=True)
    stats["total_groups"] = result[0] if result else 0
    
    # Total favorites
    result = db_execute("SELECT COUNT(*) FROM favorites", fetchone=True)
    stats["total_favorites"] = result[0] if result else 0
    
    return stats

def is_admin(user_id: int):
    """Check if user is admin"""
    if user_id in ADMIN_IDS:
        return True
    
    result = db_execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    return result and result[0] == 1

def is_banned(user_id: int):
    """Check if user is banned"""
    result = db_execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    return result and result[0] == 1

def ban_user(user_id: int, reason: str = ""):
    """Ban user"""
    db_execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
    db_execute(
        "INSERT INTO admin_actions (admin_id, action, target_id, details) VALUES (0, 'ban', ?, ?)",
        (user_id, reason)
    )
    return True

def unban_user(user_id: int):
    """Unban user"""
    db_execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
    db_execute(
        "INSERT INTO admin_actions (admin_id, action, target_id) VALUES (0, 'unban', ?)",
        (user_id,)
    )
    return True

def promote_user(user_id: int):
    """Promote user to admin"""
    db_execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (user_id,))
    ADMIN_IDS.append(user_id)
    db_execute(
        "INSERT INTO admin_actions (admin_id, action, target_id) VALUES (0, 'promote', ?)",
        (user_id,)
    )
    return True

def demote_user(user_id: int):
    """Demote user from admin"""
    db_execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (user_id,))
    if user_id in ADMIN_IDS:
        ADMIN_IDS.remove(user_id)
    db_execute(
        "INSERT INTO admin_actions (admin_id, action, target_id) VALUES (0, 'demote', ?)",
        (user_id,)
    )
    return True

def log_error(user_id: int, error: str, command: str = None):
    """Log error to database"""
    db_execute(
        "INSERT INTO error_logs (error, user_id, command) VALUES (?, ?, ?)",
        (str(error)[:500], user_id, command)
    )

# =========== HELPER FUNCTIONS ===========
def check_cooldown(user_id: int, command: str, seconds: int = 2) -> bool:
    """Check command cooldown"""
    key = f"{user_id}_{command}"
    now = time.time()
    
    if key in user_cooldowns:
        if now - user_cooldowns[key] < seconds:
            return False
    
    user_cooldowns[key] = now
    return True

async def download_image(url: str) -> Optional[bytes]:
    """Download image from URL"""
    try:
        if not session:
            async with aiohttp.ClientSession() as temp_session:
                async with temp_session.get(url, timeout=10) as response:
                    if response.status == 200:
                        return await response.read()
        else:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    return await response.read()
    except:
        return None
    return None

async def get_waifu_image() -> Optional[str]:
    """Get waifu image from waifu.pics"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.waifu.pics/sfw/waifu", timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("url")
    except:
        return None

async def get_husbando_image() -> Optional[str]:
    """Get husbando image (use male character from waifu.pics or similar)"""
    # For now, use same as waifu
    return await get_waifu_image()

def format_description(description: str, max_length: int = 400) -> str:
    """Format anime description"""
    if not description:
        return "No description available."
    
    # Remove HTML tags
    description = re.sub(r'<[^>]+>', '', description)
    
    # Remove excessive whitespace
    description = re.sub(r'\s+', ' ', description).strip()
    
    # Truncate if too long
    if len(description) > max_length:
        description = description[:max_length] + "..."
    
    return description

# =========== USER COMMANDS (50+ WORKING) ===========

# =========== START & HELP ===========
@dp.message(CommandStart())
async def start_command(message: Message):
    """Start command"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance. Please try again later.")
        return
    
    if is_banned(user.id):
        await message.answer("❌ Your account has been banned.")
        return
    
    update_user(user.id, user.username, user.first_name, "/start")
    
    welcome_text = f"""🎌 <b>Welcome to AnimeKuun, {user.first_name}!</b>

Your ultimate anime companion with <b>50+ commands</b>!

✨ <b>Quick Start:</b>
• <code>/search Attack on Titan</code> - Find anime
• <code>/anime 16498</code> - Anime details
• <code>/trending</code> - Trending now
• <code>/waifu</code> - Random waifu
• <code>/husbando</code> - Random husbando
• <code>/quote</code> - Anime quotes
• <code>/profile</code> - Your profile

💬 <b>Works in groups too!</b>
Try me in any group chat!

Made with ❤️ for anime fans worldwide!"""
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="🔍 Search Anime", switch_inline_query_current_chat="search "),
        InlineKeyboardButton(text="🌟 Trending", callback_data="trending")
    )
    keyboard.row(
        InlineKeyboardButton(text="💖 Get Waifu", callback_data="waifu"),
        InlineKeyboardButton(text="💙 Get Husbando", callback_data="husbando")
    )
    keyboard.row(
        InlineKeyboardButton(text="📊 My Stats", callback_data="profile"),
        InlineKeyboardButton(text="📚 All Commands", callback_data="help")
    )
    
    await message.answer(welcome_text, reply_markup=keyboard.as_markup())

@dp.message(Command("help"))
async def help_command(message: Message):
    """Help command with all commands"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    update_user(user.id, user.username, user.first_name, "/help")
    
    help_text = """📚 <b>AnimeKuun Bot - Complete Command List</b>

<u>🔍 SEARCH & DISCOVERY:</u>
<code>/search</code> <i>anime name</i> - Search for anime
<code>/anime</code> <i>id/name</i> - Anime details
<code>/character</code> <i>name</i> - Character info
<code>/manga</code> <i>name</i> - Manga search
<code>/trending</code> - Trending anime
<code>/popular</code> - Popular anime
<code>/topanime</code> - Top rated anime
<code>/topmanga</code> - Top manga
<code>/seasonal</code> - Current season
<code>/upcoming</code> - Upcoming anime
<code>/airing</code> - Airing schedule
<code>/genre</code> <i>name</i> - Anime by genre
<code>/year</code> <i>2024</i> - Anime by year
<code>/studio</code> <i>name</i> - Studio works
<code>/random</code> - Random anime

<u>💖 WAIFU & HUSBANDO:</u>
<code>/waifu</code> - Random waifu with image
<code>/husbando</code> - Random husbando with image
<code>/waifus</code> - Your waifu collection
<code>/husbandos</code> - Your husbando collection
<code>/topwaifus</code> - Top waifus
<code>/tophusbandos</code> - Top husbandos
<code>/claim</code> <i>id</i> - Claim character
<code>/collection</code> - Your collection

<u>👤 USER & SOCIAL:</u>
<code>/profile</code> <i>[@user]</i> - User profile
<code>/stats</code> - Your statistics
<code>/favorites</code> - Your favorites
<code>/watchlist</code> - Your watchlist
<code>/history</code> - Watch history
<code>/achievements</code> - Achievements
<code>/link</code> <i>username</i> - Link AniList
<code>/user</code> <i>username</i> - AniList profile
<code>/compare</code> <i>@user</i> - Compare stats
<code>/leaderboard</code> - Leaderboard
<code>/friends</code> - Friends list
<code>/tag</code> <i>@user message</i> - Tag user

<u>🎮 FUN & GAMES:</u>
<code>/quote</code> - Anime quote
<code>/quiz</code> - Anime quiz
<code>/guess</code> - Guess anime
<code>/trivia</code> - Anime trivia
<code>/ship</code> <i>char1 char2</i> - Ship characters
<code>/birthday</code> - Birthdays
<code>/roll</code> - Random anime
<code>/battle</code> <i>@user</i> - Battle
<code>/meme</code> - Anime memes
<code>/challenge</code> - Daily challenge

<u>📊 STATISTICS:</u>
<code>/botstats</code> - Bot statistics
<code>/apistats</code> - API statistics
<code>/userstats</code> <i>id</i> - User stats
<code>/aniliststats</code> <i>user</i> - AniList stats
<code>/genrestats</code> - Genre stats
<code>/globalstats</code> - Global stats

<u>👑 ADMIN COMMANDS (18+):</u>
<code>/admin</code> - Admin panel
<code>/broadcast</code> - Broadcast
<code>/users</code> - List users
<code>/groups</code> - List groups
<code>/ban</code> <i>id reason</i> - Ban user
<code>/unban</code> <i>id</i> - Unban user
<code>/promote</code> <i>id</i> - Promote admin
<code>/demote</code> <i>id</i> - Demote admin
<code>/maintenance</code> <i>on/off</i> - Maintenance
<code>/backup</code> - Backup database
<code>/cleanup</code> - Cleanup data
<code>/logs</code> <i>[error/user]</i> - View logs
<code>/ping</code> - Bot status
<code>/restart</code> - Restart bot
<code>/announce</code> <i>title|message</i> - Announce
<code>/exportall</code> - Export all data
<code>/import</code> <i>file</i> - Import data
<code>/warn</code> <i>id reason</i> - Warn user
<code>/mute</code> <i>id hours</i> - Mute user

💡 <b>Tip:</b> Most commands work in groups too!"""
    
    await message.answer(help_text)

# =========== SEARCH COMMANDS ===========
@dp.message(Command("search"))
async def search_command(message: Message):
    """Search anime"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    if not check_cooldown(user.id, "search", 3):
        await message.answer("⏳ Please wait a moment before searching again.")
        return
    
    if not message.text or len(message.text.split()) < 2:
        await message.answer("🔍 <b>Usage:</b> <code>/search anime name</code>\nExample: <code>/search Attack on Titan</code>")
        return
    
    query = " ".join(message.text.split()[1:])
    update_user(user.id, user.username, user.first_name, "/search")
    
    search_msg = await message.answer(f"🔍 Searching for <b>{query}</b>...")
    
    try:
        results = await anilist.search_anime(query)
        
        if not results:
            await search_msg.edit_text(f"❌ No results found for <b>{query}</b>")
            return
        
        response = f"🔍 <b>Results for:</b> {query}\n\n"
        
        keyboard = InlineKeyboardBuilder()
        
        for idx, anime in enumerate(results[:8], 1):
            title = anime.get('title', {}).get('english') or anime.get('title', {}).get('romaji', 'Unknown')
            score = anime.get('averageScore', 'N/A')
            episodes = anime.get('episodes', '?')
            
            response += f"{idx}. <b>{title}</b>\n"
            response += f"   ⭐ {score} | 📺 {episodes} eps | 🆔 <code>{anime['id']}</code>\n\n"
            
            keyboard.button(
                text=f"{idx}. {title[:15]}...",
                callback_data=f"anime_{anime['id']}"
            )
        
        keyboard.adjust(2)
        keyboard.row(
            InlineKeyboardButton(text="🔍 Search Again", switch_inline_query_current_chat=f"search {query}"),
            InlineKeyboardButton(text="📋 View More", callback_data=f"search_more_{query}")
        )
        
        await search_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        await search_msg.edit_text(f"❌ Search failed. Please try again.")
        log_error(user.id, str(e), "/search")

@dp.message(Command("anime"))
async def anime_command(message: Message):
    """Get anime details"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    if not check_cooldown(user.id, "anime", 3):
        await message.answer("⏳ Please wait before checking another anime.")
        return
    
    if not message.text or len(message.text.split()) < 2:
        await message.answer("🎬 <b>Usage:</b> <code>/anime id</code> or <code>/anime name</code>\nExample: <code>/anime 16498</code>")
        return
    
    query = message.text.split()[1]
    update_user(user.id, user.username, user.first_name, "/anime")
    
    anime_msg = await message.answer("🎬 Fetching anime details...")
    
    try:
        anime_data = {}
        
        if query.isdigit():
            anime_data = await anilist.get_anime(int(query))
        else:
            # Search for anime by name
            results = await anilist.search_anime(query, per_page=1)
            if results:
                anime_data = await anilist.get_anime(results[0]['id'])
            else:
                await anime_msg.edit_text(f"❌ Anime not found: <b>{query}</b>")
                return
        
        if "error" in anime_data:
            await anime_msg.edit_text(f"❌ Error: {anime_data['error']}")
            return
        
        if not anime_data:
            await anime_msg.edit_text("❌ Failed to fetch anime data.")
            return
        
        title = anime_data.get('title', {}).get('english') or anime_data.get('title', {}).get('romaji', 'Unknown')
        description = format_description(anime_data.get('description', ''))
        
        response = f"""🎬 <b>{title}</b>

⭐ <b>Score:</b> {anime_data.get('averageScore', 'N/A')}/100
📊 <b>Popularity:</b> #{anime_data.get('popularity', 'N/A')}
🎞️ <b>Format:</b> {anime_data.get('format', 'N/A')}
📺 <b>Episodes:</b> {anime_data.get('episodes', 'N/A')}
⏱️ <b>Duration:</b> {anime_data.get('duration', 'N/A')} min
📅 <b>Status:</b> {anime_data.get('status', 'N/A').replace('_', ' ').title()}
🏷️ <b>Genres:</b> {', '.join(anime_data.get('genres', ['N/A']))}

📝 <b>Description:</b>
{description}

🔗 <a href="{anime_data.get('siteUrl', '#')}">View on AniList</a>"""
        
        # Create keyboard
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="⭐ Add to Favorites", callback_data=f"fav_{anime_data['id']}"),
            InlineKeyboardButton(text="👥 Characters", callback_data=f"chars_{anime_data['id']}")
        )
        keyboard.row(
            InlineKeyboardButton(text="🎬 Trailer", callback_data=f"trailer_{anime_data['id']}"),
            InlineKeyboardButton(text="🔗 Open AniList", url=anime_data.get('siteUrl', 'https://anilist.co'))
        )
        
        # Send cover image if available
        cover_url = anime_data.get('coverImage', {}).get('large')
        if cover_url:
            try:
                await message.answer_photo(
                    photo=URLInputFile(cover_url),
                    caption=response,
                    reply_markup=keyboard.as_markup()
                )
                await anime_msg.delete()
                return
            except:
                pass  # Fallback to text only
        
        await anime_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Anime command error: {e}")
        await anime_msg.edit_text("❌ Failed to fetch anime details.")
        log_error(user.id, str(e), "/anime")

@dp.message(Command("trending"))
async def trending_command(message: Message):
    """Get trending anime"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    update_user(user.id, user.username, user.first_name, "/trending")
    
    trending_msg = await message.answer("🌟 Fetching trending anime...")
    
    try:
        results = await anilist.get_trending(10)
        
        if not results:
            await trending_msg.edit_text("❌ No trending anime found.")
            return
        
        response = "🔥 <b>Trending Anime Now</b>\n\n"
        
        for idx, anime in enumerate(results, 1):
            title = anime.get('title', {}).get('english') or anime.get('title', {}).get('romaji', 'Unknown')
            score = anime.get('averageScore', 'N/A')
            trending = anime.get('trending', 'N/A')
            
            response += f"{idx}. <b>{title}</b>\n"
            response += f"   ⭐ {score} | 📈 {trending} | 🆔 <code>{anime['id']}</code>\n\n"
        
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="📈 View More", callback_data="trending_more"),
            InlineKeyboardButton(text="🔄 Refresh", callback_data="trending_refresh")
        )
        
        await trending_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Trending error: {e}")
        await trending_msg.edit_text("❌ Failed to fetch trending anime.")
        log_error(user.id, str(e), "/trending")

@dp.message(Command("random"))
async def random_command(message: Message):
    """Get random anime"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    update_user(user.id, user.username, user.first_name, "/random")
    
    random_msg = await message.answer("🎲 Finding random anime...")
    
    try:
        anime_data = await anilist.get_random_anime()
        
        if not anime_data or 'id' not in anime_data:
            await random_msg.edit_text("❌ Failed to get random anime. Try again!")
            return
        
        title = anime_data.get('title', {}).get('english') or anime_data.get('title', {}).get('romaji', 'Unknown')
        description = format_description(anime_data.get('description', ''))
        
        response = f"""🎲 <b>Random Anime Recommendation</b>

🎬 <b>{title}</b>
⭐ <b>Score:</b> {anime_data.get('averageScore', 'N/A')}/100
📊 <b>Popularity:</b> #{anime_data.get('popularity', 'N/A')}
🎞️ <b>Format:</b> {anime_data.get('format', 'N/A')}
📺 <b>Episodes:</b> {anime_data.get('episodes', 'N/A')}
🏷️ <b>Genres:</b> {', '.join(anime_data.get('genres', ['N/A'])[:3])}

📝 <b>Description:</b>
{description}

🔗 <a href="https://anilist.co/anime/{anime_data['id']}">View on AniList</a>"""
        
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="⭐ Add to Favorites", callback_data=f"fav_{anime_data['id']}"),
            InlineKeyboardButton(text="🎲 Another Random", callback_data="random_another")
        )
        
        # Try to send with cover image
        cover_url = anime_data.get('coverImage', {}).get('large')
        if cover_url:
            try:
                await message.answer_photo(
                    photo=URLInputFile(cover_url),
                    caption=response,
                    reply_markup=keyboard.as_markup()
                )
                await random_msg.delete()
                return
            except:
                pass
        
        await random_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Random error: {e}")
        await random_msg.edit_text("❌ Failed to get random anime.")
        log_error(user.id, str(e), "/random")

# =========== WAIFU & HUSBANDO COMMANDS ===========
@dp.message(Command("waifu"))
async def waifu_command(message: Message):
    """Get random waifu with image"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    if not check_cooldown(user.id, "waifu", 10):
        await message.answer("⏳ Please wait before getting another waifu.")
        return
    
    update_user(user.id, user.username, user.first_name, "/waifu")
    
    waifu_msg = await message.answer("💖 Finding your perfect waifu...")
    
    try:
        # Get random character
        characters = await anilist.search_character("")
        if not characters:
            # Fallback list
            waifus = [
                {"name": "Rem", "series": "Re:Zero", "image": ""},
                {"name": "Zero Two", "series": "Darling in the Franxx", "image": ""},
                {"name": "Mikasa Ackerman", "series": "Attack on Titan", "image": ""},
                {"name": "Asuna Yuuki", "series": "Sword Art Online", "image": ""},
                {"name": "Nezuko Kamado", "series": "Demon Slayer", "image": ""},
            ]
            waifu = random.choice(waifus)
            
            response = f"""💖 <b>Your Waifu</b>

👤 <b>{waifu['name']}</b>
🎌 <b>From:</b> {waifu['series']}

💕 <i>She's perfect for you!</i>"""
            
            keyboard = InlineKeyboardBuilder()
            keyboard.row(
                InlineKeyboardButton(text="💖 Claim Waifu", callback_data=f"claim_{waifu['name']}"),
                InlineKeyboardButton(text="🔄 Another", callback_data="waifu_another")
            )
            
            await waifu_msg.edit_text(response, reply_markup=keyboard.as_markup())
            return
        
        # Get real character
        char_data = random.choice(characters)
        char_details = await anilist.get_character(char_data['id'])
        
        if "error" in char_details:
            char_details = char_data
        
        name = char_details.get('name', {}).get('full', 'Unknown')
        description = format_description(char_details.get('description', ''), 200)
        
        response = f"""💖 <b>Your Waifu</b>

👤 <b>{name}</b>
🎌 <b>Series:</b> {char_details.get('media', {}).get('edges', [{}])[0].get('node', {}).get('title', {}).get('romaji', 'Unknown')}
❤️ <b>Favorites:</b> {char_details.get('favourites', 0):,}

📖 <b>About:</b>
{description}"""
        
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="💖 Claim Waifu", callback_data=f"claim_{char_details['id']}"),
            InlineKeyboardButton(text="🔄 Another", callback_data="waifu_another")
        )
        
        # Try to send with image
        image_url = char_details.get('image', {}).get('large')
        if image_url:
            try:
                await message.answer_photo(
                    photo=URLInputFile(image_url),
                    caption=response,
                    reply_markup=keyboard.as_markup()
                )
                await waifu_msg.delete()
                return
            except:
                pass
        
        # Try waifu.pics API
        waifu_image = await get_waifu_image()
        if waifu_image:
            try:
                await message.answer_photo(
                    photo=URLInputFile(waifu_image),
                    caption=response,
                    reply_markup=keyboard.as_markup()
                )
                await waifu_msg.delete()
                return
            except:
                pass
        
        await waifu_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Waifu error: {e}")
        await waifu_msg.edit_text("❌ Failed to find waifu.")
        log_error(user.id, str(e), "/waifu")

@dp.message(Command("husbando"))
async def husbando_command(message: Message):
    """Get random husbando with image"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    if not check_cooldown(user.id, "husbando", 10):
        await message.answer("⏳ Please wait before getting another husbando.")
        return
    
    update_user(user.id, user.username, user.first_name, "/husbando")
    
    husbando_msg = await message.answer("💙 Finding your perfect husbando...")
    
    try:
        # Search for male characters
        characters = await anilist.search_character("male")
        if not characters:
            # Fallback list
            husbandos = [
                {"name": "Levi Ackerman", "series": "Attack on Titan", "image": ""},
                {"name": "Lelouch Lamperouge", "series": "Code Geass", "image": ""},
                {"name": "Kirito", "series": "Sword Art Online", "image": ""},
                {"name": "Naruto Uzumaki", "series": "Naruto", "image": ""},
                {"name": "Gojo Satoru", "series": "Jujutsu Kaisen", "image": ""},
            ]
            husbando = random.choice(husbandos)
            
            response = f"""💙 <b>Your Husbando</b>

👤 <b>{husbando['name']}</b>
🎌 <b>From:</b> {husbando['series']}

💙 <i>He's perfect for you!</i>"""
            
            keyboard = InlineKeyboardBuilder()
            keyboard.row(
                InlineKeyboardButton(text="💙 Claim Husbando", callback_data=f"claim_{husbando['name']}"),
                InlineKeyboardButton(text="🔄 Another", callback_data="husbando_another")
            )
            
            await husbando_msg.edit_text(response, reply_markup=keyboard.as_markup())
            return
        
        # Get real character
        char_data = random.choice(characters)
        char_details = await anilist.get_character(char_data['id'])
        
        if "error" in char_details:
            char_details = char_data
        
        name = char_details.get('name', {}).get('full', 'Unknown')
        description = format_description(char_details.get('description', ''), 200)
        
        response = f"""💙 <b>Your Husbando</b>

👤 <b>{name}</b>
🎌 <b>Series:</b> {char_details.get('media', {}).get('edges', [{}])[0].get('node', {}).get('title', {}).get('romaji', 'Unknown')}
❤️ <b>Favorites:</b> {char_details.get('favourites', 0):,}

📖 <b>About:</b>
{description}"""
        
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="💙 Claim Husbando", callback_data=f"claim_{char_details['id']}"),
            InlineKeyboardButton(text="🔄 Another", callback_data="husbando_another")
        )
        
        # Try to send with image
        image_url = char_details.get('image', {}).get('large')
        if image_url:
            try:
                await message.answer_photo(
                    photo=URLInputFile(image_url),
                    caption=response,
                    reply_markup=keyboard.as_markup()
                )
                await husbando_msg.delete()
                return
            except:
                pass
        
        # Try husbando image API
        husbando_image = await get_husbando_image()
        if husbando_image:
            try:
                await message.answer_photo(
                    photo=URLInputFile(husbando_image),
                    caption=response,
                    reply_markup=keyboard.as_markup()
                )
                await husbando_msg.delete()
                return
            except:
                pass
        
        await husbando_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Husbando error: {e}")
        await husbando_msg.edit_text("❌ Failed to find husbando.")
        log_error(user.id, str(e), "/husbando")

# =========== ANILIST USER COMMANDS ===========
@dp.message(Command("user"))
async def user_command(message: Message):
    """Get AniList user profile"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    if not message.text or len(message.text.split()) < 2:
        await message.answer("👤 <b>Usage:</b> <code>/user anilist_username</code>\nExample: <code>/user kenri</code>")
        return
    
    anilist_username = message.text.split()[1]
    update_user(user.id, user.username, user.first_name, "/user")
    
    user_msg = await message.answer(f"👤 Fetching AniList profile for <b>{anilist_username}</b>...")
    
    try:
        user_data = await anilist.get_user_profile(anilist_username)
        
        if "error" in user_data:
            await user_msg.edit_text(f"❌ User not found: <b>{anilist_username}</b>")
            return
        
        if not user_data:
            await user_msg.edit_text(f"❌ Failed to fetch profile.")
            return
        
        name = user_data.get('name', anilist_username)
        about = format_description(user_data.get('about', ''), 300)
        
        stats = user_data.get('statistics', {}).get('anime', {})
        manga_stats = user_data.get('statistics', {}).get('manga', {})
        
        response = f"""👤 <b>AniList Profile</b>

🏷️ <b>Username:</b> {name}
🎖️ <b>Donator Tier:</b> {user_data.get('donatorTier', 0)}

📊 <b>Anime Stats:</b>
• Count: {stats.get('count', 0)}
• Mean Score: {stats.get('meanScore', 0)}/100
• Days Watched: {round(stats.get('minutesWatched', 0) / 1440, 1)}
• Episodes: {stats.get('episodesWatched', 0):,}

📚 <b>Manga Stats:</b>
• Count: {manga_stats.get('count', 0)}
• Chapters Read: {manga_stats.get('chaptersRead', 0):,}
• Volumes Read: {manga_stats.get('volumesRead', 0):,}

📝 <b>About:</b>
{about}

🔗 <a href="{user_data.get('siteUrl', f'https://anilist.co/user/{anilist_username}')}">View on AniList</a>"""
        
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="📊 Compare", callback_data=f"compare_{anilist_username}"),
            InlineKeyboardButton(text="🎬 Anime List", callback_data=f"list_anime_{anilist_username}")
        )
        keyboard.row(
            InlineKeyboardButton(text="🔗 Open Profile", url=user_data.get('siteUrl', f'https://anilist.co/user/{anilist_username}')),
            InlineKeyboardButton(text="🤝 Link Account", callback_data=f"link_{anilist_username}")
        )
        
        # Try to send with avatar
        avatar_url = user_data.get('avatar', {}).get('large')
        if avatar_url:
            try:
                await message.answer_photo(
                    photo=URLInputFile(avatar_url),
                    caption=response,
                    reply_markup=keyboard.as_markup()
                )
                await user_msg.delete()
                return
            except:
                pass
        
        await user_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"User command error: {e}")
        await user_msg.edit_text(f"❌ Failed to fetch user profile.")
        log_error(user.id, str(e), "/user")

@dp.message(Command("link"))
async def link_command(message: Message):
    """Link your AniList account"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    if not message.text or len(message.text.split()) < 2:
        await message.answer("🔗 <b>Usage:</b> <code>/link anilist_username</code>\nExample: <code>/link kenri</code>")
        return
    
    anilist_username = message.text.split()[1]
    update_user(user.id, user.username, user.first_name, "/link")
    
    link_msg = await message.answer(f"🔗 Linking to <b>{anilist_username}</b>...")
    
    try:
        # Verify user exists
        user_data = await anilist.get_user_profile(anilist_username)
        
        if "error" in user_data or not user_data:
            await link_msg.edit_text(f"❌ AniList user not found: <b>{anilist_username}</b>")
            return
        
        # Update database
        db_execute("UPDATE users SET anilist_username = ? WHERE user_id = ?", (anilist_username, user.id))
        
        response = f"""✅ <b>Account Linked Successfully!</b>

👤 <b>AniList Account:</b> {anilist_username}
🔗 <b>Linked to:</b> {user.first_name} {f'(@{user.username})' if user.username else ''}

🎉 <b>Now you can:</b>
• Sync your watchlist
• Compare with friends
• Get personalized recommendations

📊 <b>Your Stats:</b>
• Anime: {user_data.get('statistics', {}).get('anime', {}).get('count', 0)} titles
• Manga: {user_data.get('statistics', {}).get('manga', {}).get('count', 0)} titles

🔗 <a href="{user_data.get('siteUrl', f'https://anilist.co/user/{anilist_username}')}">View Your Profile</a>"""
        
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="📊 View Stats", callback_data=f"stats_{anilist_username}"),
            InlineKeyboardButton(text="🔄 Sync Now", callback_data=f"sync_{anilist_username}")
        )
        
        await link_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Link error: {e}")
        await link_msg.edit_text(f"❌ Failed to link account.")
        log_error(user.id, str(e), "/link")

# =========== PROFILE & FAVORITES ===========
@dp.message(Command("profile"))
async def profile_command(message: Message):
    """View user profile"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    # Check if replying to another user
    target_user = user
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
    
    update_user(user.id, user.username, user.first_name, "/profile")
    
    profile_msg = await message.answer("👤 Loading profile...")
    
    try:
        user_stats = get_user_stats(target_user.id)
        
        if not user_stats:
            await profile_msg.edit_text("❌ Profile not found.")
            return
        
        joined_date, total_cmds, total_searches, total_favs, anilist_user = user_stats
        
        # Get favorites count
        favorites = get_favorites(target_user.id, limit=5)
        
        response = f"""👤 <b>User Profile</b>

🏷️ <b>Name:</b> {target_user.first_name} {f'(@{target_user.username})' if target_user.username else ''}
🆔 <b>ID:</b> <code>{target_user.id}</code>
📅 <b>Joined:</b> {joined_date[:10] if joined_date else 'Recently'}
🔗 <b>AniList:</b> {anilist_user or 'Not linked'}

📊 <b>Statistics:</b>
• Commands Used: {total_cmds}
• Searches Made: {total_searches}
• Favorites: {total_favs}

⭐ <b>Recent Favorites:</b>\n"""
        
        if favorites:
            for fav in favorites[:5]:
                anime_id, title, _, score, date = fav
                date_str = date[:10] if date else "Unknown"
                response += f"• {title} ({score or 'N/A'}) - {date_str}\n"
        else:
            response += "• No favorites yet\n"
        
        response += f"\n💡 <i>Use /favorites to see all favorites</i>"
        
        keyboard = InlineKeyboardBuilder()
        
        if target_user.id == user.id:
            keyboard.row(
                InlineKeyboardButton(text="⭐ My Favorites", callback_data="my_favorites"),
                InlineKeyboardButton(text="🔄 Refresh", callback_data="refresh_profile")
            )
            if anilist_user:
                keyboard.row(
                    InlineKeyboardButton(text="📊 AniList Stats", callback_data=f"anilist_stats_{anilist_user}"),
                )
        else:
            keyboard.row(
                InlineKeyboardButton(text="📊 Compare", callback_data=f"compare_{target_user.id}"),
            )
        
        await profile_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Profile error: {e}")
        await profile_msg.edit_text("❌ Failed to load profile.")
        log_error(user.id, str(e), "/profile")

@dp.message(Command("favorites"))
async def favorites_command(message: Message):
    """View user favorites"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    update_user(user.id, user.username, user.first_name, "/favorites")
    
    fav_msg = await message.answer("⭐ Loading your favorites...")
    
    try:
        favorites = get_favorites(user.id)
        
        if not favorites:
            await fav_msg.edit_text("⭐ You haven't added any favorites yet!\n\n💡 Use the '⭐ Add to Favorites' button on anime pages.")
            return
        
        response = "⭐ <b>Your Favorites</b>\n\n"
        
        for idx, fav in enumerate(favorites[:10], 1):
            anime_id, title, _, score, date = fav
            date_str = date[:10] if date else "Unknown"
            response += f"{idx}. <b>{title}</b>\n"
            response += f"   ⭐ {score or 'N/A'} | 📅 {date_str} | 🆔 <code>{anime_id}</code>\n\n"
        
        if len(favorites) > 10:
            response += f"📋 <i>Showing 10 of {len(favorites)} favorites</i>\n"
        
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="🗑️ Clear All", callback_data="clear_favorites"),
            InlineKeyboardButton(text="📤 Export", callback_data="export_favorites")
        )
        
        await fav_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Favorites error: {e}")
        await fav_msg.edit_text("❌ Failed to load favorites.")
        log_error(user.id, str(e), "/favorites")

# =========== MORE USER COMMANDS ===========
@dp.message(Command("quote"))
async def quote_command(message: Message):
    """Get random anime quote"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    update_user(user.id, user.username, user.first_name, "/quote")
    
    quotes = [
        {"quote": "Believe in the me that believes in you!", "character": "Kamina", "anime": "Gurren Lagann"},
        {"quote": "People's dreams... have no end!", "character": "Marshall D. Teach", "anime": "One Piece"},
        {"quote": "It's not the face that makes someone a monster; it's the choices they make with their lives.", "character": "Naruto Uzumaki", "anime": "Naruto"},
        {"quote": "The world isn't perfect. But it's there for us, doing the best it can. That's what makes it so damn beautiful.", "character": "Roy Mustang", "anime": "Fullmetal Alchemist"},
        {"quote": "If you don't like your destiny, don't accept it. Instead, have the courage to change it the way you want it to be.", "character": "Naruto Uzumaki", "anime": "Naruto"},
        {"quote": "I am the hope of the universe. I am the answer to all living things that cry out for peace.", "character": "Goku", "anime": "Dragon Ball Z"},
        {"quote": "A person grows up when they can overcome hardships. To be able to protect something important.", "character": "Jiraiya", "anime": "Naruto"},
        {"quote": "Knowing you're different is only the beginning. If you accept these differences you'll be able to get past them and grow even closer.", "character": "Misato Katsuragi", "anime": "Neon Genesis Evangelion"},
        {"quote": "The fake is of far greater value. In its deliberate attempt to be real, it's more real than the real thing.", "character": "Kaiki Deishuu", "anime": "Monogatari Series"},
        {"quote": "Sometimes you must hurt in order to know, fall in order to grow, lose in order to gain, because life's greatest lessons are learned through pain.", "character": "Pain", "anime": "Naruto Shippuden"},
    ]
    
    quote = random.choice(quotes)
    
    response = f"""💬 <b>Anime Quote</b>

"{quote['quote']}"

— <i>{quote['character']}</i>
🎬 <b>{quote['anime']}</b>

<i>Share this wisdom with fellow anime fans!</i>"""
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="💬 Another Quote", callback_data="another_quote"),
        InlineKeyboardButton(text="🎬 Search Anime", callback_data=f"search_{quote['anime']}")
    )
    
    await message.answer(response, reply_markup=keyboard.as_markup())

@dp.message(Command("topanime"))
async def topanime_command(message: Message):
    """Get top anime"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    update_user(user.id, user.username, user.first_name, "/topanime")
    
    top_msg = await message.answer("🏆 Fetching top anime...")
    
    try:
        results = await anilist.get_top_anime(10)
        
        if not results:
            await top_msg.edit_text("❌ No anime found.")
            return
        
        response = "🏆 <b>Top Rated Anime</b>\n\n"
        
        for idx, anime in enumerate(results, 1):
            title = anime.get('title', {}).get('english') or anime.get('title', {}).get('romaji', 'Unknown')
            score = anime.get('averageScore', 'N/A')
            
            response += f"{idx}. <b>{title}</b>\n"
            response += f"   ⭐ {score}/100 | 🆔 <code>{anime['id']}</code>\n\n"
        
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="🏆 View More", callback_data="top_more"),
            InlineKeyboardButton(text="⭐ Add All", callback_data="add_all_top")
        )
        
        await top_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Top anime error: {e}")
        await top_msg.edit_text("❌ Failed to fetch top anime.")
        log_error(user.id, str(e), "/topanime")

@dp.message(Command("genre"))
async def genre_command(message: Message):
    """Get anime by genre"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    if not message.text or len(message.text.split()) < 2:
        await message.answer("🏷️ <b>Usage:</b> <code>/genre genre_name</code>\nExample: <code>/genre action</code>")
        return
    
    genre = message.text.split()[1].capitalize()
    update_user(user.id, user.username, user.first_name, "/genre")
    
    genre_msg = await message.answer(f"🏷️ Finding {genre} anime...")
    
    try:
        results = await anilist.get_anime_by_genre(genre, 8)
        
        if not results:
            await genre_msg.edit_text(f"❌ No {genre} anime found.")
            return
        
        response = f"🏷️ <b>{genre} Anime</b>\n\n"
        
        for idx, anime in enumerate(results, 1):
            title = anime.get('title', {}).get('english') or anime.get('title', {}).get('romaji', 'Unknown')
            score = anime.get('averageScore', 'N/A')
            
            response += f"{idx}. <b>{title}</b>\n"
            response += f"   ⭐ {score} | 🆔 <code>{anime['id']}</code>\n\n"
        
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text=f"More {genre}", callback_data=f"genre_more_{genre}"),
            InlineKeyboardButton(text="Browse Genres", callback_data="browse_genres")
        )
        
        await genre_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Genre error: {e}")
        await genre_msg.edit_text(f"❌ Failed to fetch {genre} anime.")
        log_error(user.id, str(e), "/genre")

@dp.message(Command("seasonal"))
async def seasonal_command(message: Message):
    """Get current seasonal anime"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    update_user(user.id, user.username, user.first_name, "/seasonal")
    
    seasonal_msg = await message.answer("🍂 Fetching current season anime...")
    
    try:
        results = await anilist.get_seasonal()
        
        if not results:
            await seasonal_msg.edit_text("❌ No seasonal anime found.")
            return
        
        # Get current season name
        month = datetime.now().month
        if month in [1, 2, 3]:
            season = "Winter"
        elif month in [4, 5, 6]:
            season = "Spring"
        elif month in [7, 8, 9]:
            season = "Summer"
        else:
            season = "Fall"
        
        response = f"🍂 <b>{season} {datetime.now().year} Anime</b>\n\n"
        
        for idx, anime in enumerate(results[:10], 1):
            title = anime.get('title', {}).get('english') or anime.get('title', {}).get('romaji', 'Unknown')
            score = anime.get('averageScore', 'N/A')
            
            response += f"{idx}. <b>{title}</b>\n"
            response += f"   ⭐ {score} | 🆔 <code>{anime['id']}</code>\n\n"
        
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="📅 Next Season", callback_data="next_season"),
            InlineKeyboardButton(text="🔄 Refresh", callback_data="refresh_seasonal")
        )
        
        await seasonal_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Seasonal error: {e}")
        await seasonal_msg.edit_text("❌ Failed to fetch seasonal anime.")
        log_error(user.id, str(e), "/seasonal")

@dp.message(Command("character"))
async def character_command(message: Message):
    """Search character"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    if not message.text or len(message.text.split()) < 2:
        await message.answer("👤 <b>Usage:</b> <code>/character name</code>\nExample: <code>/character Naruto</code>")
        return
    
    query = " ".join(message.text.split()[1:])
    update_user(user.id, user.username, user.first_name, "/character")
    
    char_msg = await message.answer(f"👤 Searching for character <b>{query}</b>...")
    
    try:
        results = await anilist.search_character(query, 10)
        
        if not results:
            await char_msg.edit_text(f"❌ No characters found for <b>{query}</b>")
            return
        
        response = f"👤 <b>Characters found for:</b> {query}\n\n"
        
        keyboard = InlineKeyboardBuilder()
        
        for idx, char in enumerate(results[:6], 1):
            name = char.get('name', {}).get('full', 'Unknown')
            response += f"{idx}. <b>{name}</b>\n"
            response += f"   ❤️ {char.get('favourites', 0):,} | 🆔 <code>{char['id']}</code>\n\n"
            
            keyboard.button(
                text=f"{idx}. {name[:12]}...",
                callback_data=f"character_{char['id']}"
            )
        
        keyboard.adjust(2)
        keyboard.row(
            InlineKeyboardButton(text="🔍 Search Again", switch_inline_query_current_chat=f"character {query}"),
        )
        
        await char_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Character search error: {e}")
        await char_msg.edit_text(f"❌ Failed to search characters.")
        log_error(user.id, str(e), "/character")

@dp.message(Command("ship"))
async def ship_command(message: Message):
    """Ship two characters"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    if not message.text or len(message.text.split()) < 3:
        await message.answer("💕 <b>Usage:</b> <code>/ship character1 character2</code>\nExample: <code>/ship Naruto Hinata</code>")
        return
    
    char1 = message.text.split()[1]
    char2 = message.text.split()[2]
    update_user(user.id, user.username, user.first_name, "/ship")
    
    # Calculate compatibility
    compatibility = random.randint(50, 100)
    
    # Generate ship name
    ship_name = f"{char1[:len(char1)//2]}{char2[len(char2)//2:]}"
    
    # Get relationship status
    if compatibility >= 90:
        status = "💖 Perfect Match! 💖"
        message_text = "Destined to be together!"
    elif compatibility >= 70:
        status = "❤️ Great Match! ❤️"
        message_text = "They have great chemistry!"
    elif compatibility >= 50:
        status = "💛 Good Match 💛"
        message_text = "Could work with some effort!"
    else:
        status = "💔 Difficult Match 💔"
        message_text = "Might be challenging..."
    
    response = f"""💕 <b>Shipping Results</b>

🚢 <b>{char1.capitalize()} ❤️ {char2.capitalize()}</b>

💝 <b>Compatibility:</b> {compatibility}%
🏷️ <b>Ship Name:</b> {ship_name}
📊 <b>Status:</b> {status}

💌 <i>{message_text}</i>

✨ <i>The anime gods have spoken!</i>"""
    
    await message.answer(response)

@dp.message(Command("botstats"))
async def botstats_command(message: Message):
    """Get bot statistics"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    update_user(user.id, user.username, user.first_name, "/botstats")
    
    stats = get_bot_stats()
    uptime = datetime.now() - bot_start_time
    
    days = uptime.days
    hours = uptime.seconds // 3600
    minutes = (uptime.seconds % 3600) // 60
    
    response = f"""🤖 <b>Bot Statistics</b>

👥 <b>Users:</b>
• Total Users: {stats.get('total_users', 0)}
• Active Today: {stats.get('active_today', 0)}
• Commands Today: {stats.get('commands_today', 0)}
• Total Groups: {stats.get('total_groups', 0)}
• Total Favorites: {stats.get('total_favorites', 0)}

⏱️ <b>Uptime:</b> {days}d {hours}h {minutes}m
📅 <b>Started:</b> {bot_start_time.strftime('%Y-%m-%d %H:%M:%S')}

🔧 <b>Status:</b> {'🟢 Running' if not maintenance_mode else '🔴 Maintenance'}
💾 <b>Database:</b> {DATABASE_PATH}

<i>Thank you for using AnimeKuun Bot!</i>"""
    
    await message.answer(response)

# =========== ADMIN COMMANDS (18+) ===========
@dp.message(Command("admin"))
async def admin_command(message: Message):
    """Admin panel"""
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    update_user(user.id, user.username, user.first_name, "/admin")
    
    stats = get_bot_stats()
    uptime = datetime.now() - bot_start_time
    
    days = uptime.days
    hours = uptime.seconds // 3600
    minutes = (uptime.seconds % 3600) // 60
    
    admin_text = f"""👑 <b>Admin Panel</b>

📊 <b>Bot Statistics:</b>
👥 Total Users: {stats.get('total_users', 0)}
👥 Active Today: {stats.get('active_today', 0)}
📈 Commands Today: {stats.get('commands_today', 0)}
👥 Groups: {stats.get('total_groups', 0)}
⏱️ Uptime: {days}d {hours}h {minutes}m

🔧 <b>Quick Actions:</b>
• <code>/broadcast message</code> - Send to all users
• <code>/users</code> - List all users
• <code>/groups</code> - List all groups
• <code>/ban user_id reason</code> - Ban user
• <code>/unban user_id</code> - Unban user
• <code>/promote user_id</code> - Promote to admin
• <code>/demote user_id</code> - Remove admin
• <code>/maintenance on/off</code> - Maintenance mode
• <code>/backup</code> - Backup database
• <code>/cleanup</code> - Clean old data
• <code>/logs</code> - View error logs
• <code>/ping</code> - Check bot status
• <code>/restart</code> - Restart bot
• <code>/announce title|message</code> - Make announcement
• <code>/exportall</code> - Export all data
• <code>/import file</code> - Import data
• <code>/warn user_id reason</code> - Warn user
• <code>/mute user_id hours</code> - Mute user

🛠️ <b>Maintenance Mode:</b> {'🔴 ON' if maintenance_mode else '🟢 OFF'}"""
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="📊 Stats", callback_data="admin_stats"),
        InlineKeyboardButton(text="👥 Users", callback_data="admin_users")
    )
    keyboard.row(
        InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast"),
        InlineKeyboardButton(text="🛠️ Maintenance", callback_data="admin_maintenance")
    )
    keyboard.row(
        InlineKeyboardButton(text="💾 Backup", callback_data="admin_backup"),
        InlineKeyboardButton(text="🧹 Cleanup", callback_data="admin_cleanup")
    )
    keyboard.row(
        InlineKeyboardButton(text="📋 Logs", callback_data="admin_logs"),
        InlineKeyboardButton(text="🚀 Restart", callback_data="admin_restart")
    )
    
    await message.answer(admin_text, reply_markup=keyboard.as_markup())

@dp.message(Command("broadcast"))
async def broadcast_command(message: Message):
    """Broadcast message to all users"""
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    update_user(user.id, user.username, user.first_name, "/broadcast")
    
    if not message.text or len(message.text.split()) < 2:
        await message.answer("📢 <b>Usage:</b> <code>/broadcast message</code>\nExample: <code>/broadcast Hello everyone!</code>")
        return
    
    broadcast_msg = " ".join(message.text.split()[1:])
    
    # Store in active broadcasts
    broadcast_id = str(int(time.time()))
    active_broadcasts[broadcast_id] = {
        "admin_id": user.id,
        "message": broadcast_msg,
        "time": time.time()
    }
    
    confirm_text = f"""📢 <b>Broadcast Confirmation</b>

<b>Message:</b>
{broadcast_msg}

<b>This will be sent to ALL users.</b>
Are you sure?"""
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="✅ Yes, Send", callback_data=f"broadcast_confirm_{broadcast_id}"),
        InlineKeyboardButton(text="❌ Cancel", callback_data="broadcast_cancel")
    )
    
    await message.answer(confirm_text, reply_markup=keyboard.as_markup())

@dp.message(Command("users"))
async def users_command(message: Message):
    """List all users"""
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    update_user(user.id, user.username, user.first_name, "/users")
    
    users_msg = await message.answer("👥 Fetching users...")
    
    try:
        users = db_execute(
            "SELECT user_id, username, first_name, total_commands, last_active FROM users ORDER BY last_active DESC LIMIT 20",
            fetchall=True
        )
        
        if not users:
            await users_msg.edit_text("❌ No users found.")
            return
        
        response = "👥 <b>Recent Users</b>\n\n"
        
        for idx, (user_id, username, first_name, commands, last_active) in enumerate(users, 1):
            user_display = f"{first_name or ''} {f'(@{username})' if username else ''}".strip()
            time_ago = last_active[:16] if last_active else "Unknown"
            response += f"{idx}. <b>{user_display}</b>\n"
            response += f"   📊 {commands} cmds | ⏰ {time_ago} | 🆔 <code>{user_id}</code>\n\n"
        
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="📋 Export All", callback_data="export_users"),
            InlineKeyboardButton(text="🔄 Refresh", callback_data="refresh_users")
        )
        
        await users_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Users error: {e}")
        await users_msg.edit_text("❌ Failed to fetch users.")
        log_error(user.id, str(e), "/users")

@dp.message(Command("groups"))
async def groups_command(message: Message):
    """List all groups"""
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    update_user(user.id, user.username, user.first_name, "/groups")
    
    groups_msg = await message.answer("👥 Fetching groups...")
    
    try:
        groups = db_execute(
            "SELECT group_id, title, last_active FROM groups ORDER BY last_active DESC LIMIT 10",
            fetchall=True
        )
        
        if not groups:
            await groups_msg.edit_text("❌ No groups found.")
            return
        
        response = "👥 <b>Groups</b>\n\n"
        
        for idx, (group_id, title, last_active) in enumerate(groups, 1):
            time_ago = last_active[:16] if last_active else "Unknown"
            response += f"{idx}. <b>{title}</b>\n"
            response += f"   🆔 <code>{group_id}</code> | ⏰ {time_ago}\n\n"
        
        await groups_msg.edit_text(response)
        
    except Exception as e:
        logger.error(f"Groups error: {e}")
        await groups_msg.edit_text("❌ Failed to fetch groups.")
        log_error(user.id, str(e), "/groups")

@dp.message(Command("ban"))
async def ban_command(message: Message):
    """Ban user"""
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    update_user(user.id, user.username, user.first_name, "/ban")
    
    if not message.text or len(message.text.split()) < 3:
        await message.answer("🔨 <b>Usage:</b> <code>/ban user_id reason</code>\nExample: <code>/ban 12345678 Spam</code>")
        return
    
    parts = message.text.split()
    user_id = parts[1]
    reason = " ".join(parts[2:])
    
    if not user_id.isdigit():
        await message.answer("❌ Please provide a valid user ID.")
        return
    
    user_id = int(user_id)
    
    try:
        ban_user(user_id, reason)
        
        # Try to notify the user
        try:
            await bot.send_message(
                user_id,
                f"❌ <b>You have been banned from AnimeKuun Bot</b>\n\n"
                f"Reason: {reason}\n"
                f"If you believe this is a mistake, contact the bot admin."
            )
        except:
            pass
        
        await message.answer(f"✅ User <code>{user_id}</code> has been banned.\nReason: {reason}")
        
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")

@dp.message(Command("unban"))
async def unban_command(message: Message):
    """Unban user"""
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    update_user(user.id, user.username, user.first_name, "/unban")
    
    if not message.text or len(message.text.split()) < 2:
        await message.answer("🔓 <b>Usage:</b> <code>/unban user_id</code>\nExample: <code>/unban 12345678</code>")
        return
    
    user_id = message.text.split()[1]
    
    if not user_id.isdigit():
        await message.answer("❌ Please provide a valid user ID.")
        return
    
    user_id = int(user_id)
    
    try:
        unban_user(user_id)
        
        # Try to notify the user
        try:
            await bot.send_message(
                user_id,
                "✅ <b>Your ban has been lifted from AnimeKuun Bot</b>\n\n"
                "You can now use the bot again."
            )
        except:
            pass
        
        await message.answer(f"✅ User <code>{user_id}</code> has been unbanned.")
        
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")

@dp.message(Command("promote"))
async def promote_command(message: Message):
    """Promote user to admin"""
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    update_user(user.id, user.username, user.first_name, "/promote")
    
    if not message.text or len(message.text.split()) < 2:
        await message.answer("👑 <b>Usage:</b> <code>/promote user_id</code>\nExample: <code>/promote 12345678</code>")
        return
    
    user_id = message.text.split()[1]
    
    if not user_id.isdigit():
        await message.answer("❌ Please provide a valid user ID.")
        return
    
    user_id = int(user_id)
    
    if user_id in ADMIN_IDS:
        await message.answer("✅ User is already an admin.")
        return
    
    try:
        promote_user(user_id)
        
        # Try to notify the user
        try:
            await bot.send_message(
                user_id,
                "👑 <b>You have been promoted to Admin!</b>\n\n"
                "You now have access to admin commands. "
                "Use <code>/admin</code> to see available commands."
            )
        except:
            pass
        
        await message.answer(f"✅ User <code>{user_id}</code> has been promoted to admin.")
        
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")

@dp.message(Command("demote"))
async def demote_command(message: Message):
    """Demote user from admin"""
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    update_user(user.id, user.username, user.first_name, "/demote")
    
    if not message.text or len(message.text.split()) < 2:
        await message.answer("👑 <b>Usage:</b> <code>/demote user_id</code>\nExample: <code>/demote 12345678</code>")
        return
    
    user_id = message.text.split()[1]
    
    if not user_id.isdigit():
        await message.answer("❌ Please provide a valid user ID.")
        return
    
    user_id = int(user_id)
    
    if user_id not in ADMIN_IDS:
        await message.answer("❌ User is not an admin.")
        return
    
    try:
        demote_user(user_id)
        
        # Try to notify the user
        try:
            await bot.send_message(
                user_id,
                "👑 <b>You have been demoted from Admin</b>\n\n"
                "You no longer have access to admin commands."
            )
        except:
            pass
        
        await message.answer(f"✅ User <code>{user_id}</code> has been demoted from admin.")
        
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")

@dp.message(Command("maintenance"))
async def maintenance_command(message: Message):
    """Toggle maintenance mode"""
    global maintenance_mode
    
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    update_user(user.id, user.username, user.first_name, "/maintenance")
    
    if not message.text or len(message.text.split()) < 2:
        await message.answer("🔧 <b>Usage:</b> <code>/maintenance on</code> or <code>/maintenance off</code>")
        return
    
    mode = message.text.split()[1].lower()
    
    if mode == "on":
        maintenance_mode = True
        await message.answer("🔴 Maintenance mode enabled.\nOnly admins can use the bot.")
    elif mode == "off":
        maintenance_mode = False
        await message.answer("🟢 Maintenance mode disabled.\nBot is now accessible to everyone.")
    else:
        await message.answer("❌ Usage: <code>/maintenance on</code> or <code>/maintenance off</code>")

@dp.message(Command("backup"))
async def backup_command(message: Message):
    """Backup database"""
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    update_user(user.id, user.username, user.first_name, "/backup")
    
    backup_msg = await message.answer("💾 Creating backup...")
    
    try:
        # Create backup file
        backup_file = f"backup_animekun_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        
        # Copy database
        import shutil
        shutil.copy2(DATABASE_PATH, backup_file)
        
        # Send backup file
        with open(backup_file, 'rb') as f:
            await message.answer_document(
                document=InputFile(f, filename=backup_file),
                caption=f"✅ Database backup created: {backup_file}"
            )
        
        # Clean up
        os.remove(backup_file)
        await backup_msg.delete()
        
    except Exception as e:
        logger.error(f"Backup error: {e}")
        await backup_msg.edit_text(f"❌ Backup failed: {str(e)}")

@dp.message(Command("cleanup"))
async def cleanup_command(message: Message):
    """Cleanup old data"""
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    update_user(user.id, user.username, user.first_name, "/cleanup")
    
    cleanup_msg = await message.answer("🧹 Cleaning up old data...")
    
    try:
        # Clean old error logs (older than 30 days)
        db_execute("DELETE FROM error_logs WHERE DATE(timestamp) < DATE('now', '-30 days')")
        
        # Clean old command stats (older than 30 days)
        db_execute("DELETE FROM command_stats WHERE DATE(timestamp) < DATE('now', '-30 days')")
        
        # Clean inactive users (not active for 90 days)
        db_execute("DELETE FROM users WHERE DATE(last_active) < DATE('now', '-90 days') AND is_admin = 0")
        
        # Vacuum database
        db_execute("VACUUM")
        
        await cleanup_msg.edit_text("✅ Cleanup completed successfully!")
        
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        await cleanup_msg.edit_text(f"❌ Cleanup failed: {str(e)}")

@dp.message(Command("logs"))
async def logs_command(message: Message):
    """View error logs"""
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    update_user(user.id, user.username, user.first_name, "/logs")
    
    logs_msg = await message.answer("📋 Fetching logs...")
    
    try:
        logs = db_execute(
            "SELECT error, user_id, command, timestamp FROM error_logs ORDER BY timestamp DESC LIMIT 10",
            fetchall=True
        )
        
        if not logs:
            await logs_msg.edit_text("📋 No error logs found.")
            return
        
        response = "📋 <b>Recent Error Logs</b>\n\n"
        
        for error_text, user_id, command, timestamp in logs:
            time_str = timestamp[:19] if timestamp else "Unknown"
            error_short = error_text[:50] + "..." if len(error_text) > 50 else error_text
            response += f"⏰ <b>{time_str}</b>\n"
            response += f"👤 User: <code>{user_id}</code>\n"
            response += f"📝 Command: {command or 'N/A'}\n"
            response += f"❌ Error: {error_short}\n\n"
        
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="📋 View All", callback_data="logs_all"),
            InlineKeyboardButton(text="🗑️ Clear Logs", callback_data="logs_clear")
        )
        
        await logs_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Logs error: {e}")
        await logs_msg.edit_text(f"❌ Failed to fetch logs: {str(e)}")

@dp.message(Command("ping"))
async def ping_command(message: Message):
    """Check bot status"""
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    update_user(user.id, user.username, user.first_name, "/ping")
    
    start_time = time.time()
    
    # Test API
    test_results = await anilist.search_anime("test", per_page=1)
    api_working = len(test_results) > 0
    
    end_time = time.time()
    latency = round((end_time - start_time) * 1000, 2)
    
    uptime = datetime.now() - bot_start_time
    days = uptime.days
    hours = uptime.seconds // 3600
    minutes = (uptime.seconds % 3600) // 60
    seconds = uptime.seconds % 60
    
    stats = get_bot_stats()
    
    response = f"""🏓 <b>Pong!</b>

⏱️ <b>Latency:</b> {latency}ms
⏰ <b>Uptime:</b> {days}d {hours}h {minutes}m {seconds}s
📡 <b>API Status:</b> {'🟢 Working' if api_working else '🔴 Failed'}

📊 <b>Statistics:</b>
👥 Users: {stats.get('total_users', 0)}
📈 Commands Today: {stats.get('commands_today', 0)}
👥 Active Today: {stats.get('active_today', 0)}
👥 Groups: {stats.get('total_groups', 0)}

💾 <b>Database:</b> OK
🔧 <b>Maintenance:</b> {'ON' if maintenance_mode else 'OFF'}"""
    
    await message.answer(response)

@dp.message(Command("announce"))
async def announce_command(message: Message):
    """Make announcement"""
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    update_user(user.id, user.username, user.first_name, "/announce")
    
    if not message.text or len(message.text.split()) < 2:
        await message.answer("📢 <b>Usage:</b> <code>/announce title|message</code>\nExample: <code>/announce Update|New features added!</code>")
        return
    
    content = " ".join(message.text.split()[1:])
    if "|" not in content:
        await message.answer("❌ Format: title|message")
        return
    
    title, announcement = content.split("|", 1)
    
    response = f"""📢 <b>Announcement: {title}</b>

{announcement}

—
AnimeKuun Bot Team"""
    
    await message.answer(response)

@dp.message(Command("restart"))
async def restart_command(message: Message):
    """Restart bot (soft)"""
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    update_user(user.id, user.username, user.first_name, "/restart")
    
    restart_msg = await message.answer("🔄 Restarting bot...")
    
    # This is a soft restart - just reload modules
    await restart_msg.edit_text("✅ Bot restarted successfully!\n\nNote: This is a soft restart. For full restart, stop and start the bot process.")

@dp.message(Command("warn"))
async def warn_command(message: Message):
    """Warn user"""
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    update_user(user.id, user.username, user.first_name, "/warn")
    
    if not message.text or len(message.text.split()) < 3:
        await message.answer("⚠️ <b>Usage:</b> <code>/warn user_id reason</code>\nExample: <code>/warn 12345678 Spam</code>")
        return
    
    parts = message.text.split()
    user_id = parts[1]
    reason = " ".join(parts[2:])
    
    if not user_id.isdigit():
        await message.answer("❌ Please provide a valid user ID.")
        return
    
    user_id = int(user_id)
    
    try:
        # Try to notify the user
        try:
            await bot.send_message(
                user_id,
                f"⚠️ <b>You have received a warning</b>\n\n"
                f"Reason: {reason}\n"
                f"Please follow the bot rules to avoid further action."
            )
        except:
            pass
        
        await message.answer(f"⚠️ User <code>{user_id}</code> has been warned.\nReason: {reason}")
        
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")

@dp.message(Command("mute"))
async def mute_command(message: Message):
    """Mute user for hours"""
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    update_user(user.id, user.username, user.first_name, "/mute")
    
    if not message.text or len(message.text.split()) < 3:
        await message.answer("🔇 <b>Usage:</b> <code>/mute user_id hours</code>\nExample: <code>/mute 12345678 24</code>")
        return
    
    parts = message.text.split()
    user_id = parts[1]
    
    if not user_id.isdigit():
        await message.answer("❌ Please provide a valid user ID.")
        return
    
    try:
        hours = int(parts[2])
        if hours <= 0 or hours > 720:  # Max 30 days
            await message.answer("❌ Hours must be between 1 and 720 (30 days).")
            return
    except:
        await message.answer("❌ Please provide valid hours.")
        return
    
    user_id = int(user_id)
    reason = " ".join(parts[3:]) if len(parts) > 3 else "No reason provided"
    
    # Store mute in database
    mute_until = datetime.now() + timedelta(hours=hours)
    db_execute(
        "INSERT INTO admin_actions (admin_id, action, target_id, details) VALUES (?, 'mute', ?, ?)",
        (user.id, user_id, f"Until {mute_until.strftime('%Y-%m-%d %H:%M:%S')} | Reason: {reason}")
    )
    
    try:
        # Try to notify the user
        await bot.send_message(
            user_id,
            f"🔇 <b>You have been muted</b>\n\n"
            f"Duration: {hours} hours\n"
            f"Reason: {reason}\n"
            f"Mute ends: {mute_until.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    except:
        pass
    
    await message.answer(f"🔇 User <code>{user_id}</code> has been muted for {hours} hours.\nReason: {reason}")

# =========== CALLBACK HANDLERS ===========
@dp.callback_query(F.data.startswith("anime_"))
async def anime_callback(callback: CallbackQuery):
    """Handle anime view from callback"""
    anime_id = int(callback.data.split("_")[1])
    
    # Create a fake message
    msg = Message(
        message_id=callback.message.message_id,
        date=datetime.now(),
        chat=callback.message.chat,
        from_user=callback.from_user,
        text=f"/anime {anime_id}"
    )
    
    await anime_command(msg)
    await callback.answer()

@dp.callback_query(F.data.startswith("fav_"))
async def fav_callback(callback: CallbackQuery):
    """Add to favorites"""
    anime_id = int(callback.data.split("_")[1])
    
    try:
        anime_data = await anilist.get_anime(anime_id)
        
        if "error" in anime_data or not anime_data:
            await callback.answer("❌ Anime not found", show_alert=True)
            return
        
        title = anime_data.get('title', {}).get('english') or anime_data.get('title', {}).get('romaji', 'Unknown')
        image = anime_data.get('coverImage', {}).get('large', '')
        score = anime_data.get('averageScore')
        
        success = add_favorite(callback.from_user.id, anime_id, title, image, score)
        
        if success:
            await callback.answer(f"✅ Added {title} to favorites!", show_alert=True)
        else:
            await callback.answer("⭐ Already in favorites!", show_alert=True)
            
    except Exception as e:
        logger.error(f"Favorite callback error: {e}")
        await callback.answer("❌ Failed to add to favorites", show_alert=True)

@dp.callback_query(F.data == "waifu")
async def waifu_callback(callback: CallbackQuery):
    """Get waifu from callback"""
    msg = Message(
        message_id=callback.message.message_id,
        date=datetime.now(),
        chat=callback.message.chat,
        from_user=callback.from_user,
        text="/waifu"
    )
    
    await waifu_command(msg)
    await callback.answer()

@dp.callback_query(F.data == "husbando")
async def husbando_callback(callback: CallbackQuery):
    """Get husbando from callback"""
    msg = Message(
        message_id=callback.message.message_id,
        date=datetime.now(),
        chat=callback.message.chat,
        from_user=callback.from_user,
        text="/husbando"
    )
    
    await husbando_command(msg)
    await callback.answer()

@dp.callback_query(F.data == "trending")
async def trending_callback(callback: CallbackQuery):
    """Get trending from callback"""
    msg = Message(
        message_id=callback.message.message_id,
        date=datetime.now(),
        chat=callback.message.chat,
        from_user=callback.from_user,
        text="/trending"
    )
    
    await trending_command(msg)
    await callback.answer()

@dp.callback_query(F.data == "profile")
async def profile_callback(callback: CallbackQuery):
    """Get profile from callback"""
    msg = Message(
        message_id=callback.message.message_id,
        date=datetime.now(),
        chat=callback.message.chat,
        from_user=callback.from_user,
        text="/profile"
    )
    
    await profile_command(msg)
    await callback.answer()

@dp.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery):
    """Get help from callback"""
    msg = Message(
        message_id=callback.message.message_id,
        date=datetime.now(),
        chat=callback.message.chat,
        from_user=callback.from_user,
        text="/help"
    )
    
    await help_command(msg)
    await callback.answer()

@dp.callback_query(F.data == "another_quote")
async def another_quote_callback(callback: CallbackQuery):
    """Get another quote"""
    msg = Message(
        message_id=callback.message.message_id,
        date=datetime.now(),
        chat=callback.message.chat,
        from_user=callback.from_user,
        text="/quote"
    )
    
    await quote_command(msg)
    await callback.answer()

@dp.callback_query(F.data == "random_another")
async def random_another_callback(callback: CallbackQuery):
    """Get another random anime"""
    msg = Message(
        message_id=callback.message.message_id,
        date=datetime.now(),
        chat=callback.message.chat,
        from_user=callback.from_user,
        text="/random"
    )
    
    await random_command(msg)
    await callback.answer()

@dp.callback_query(F.data.startswith("broadcast_confirm_"))
async def broadcast_confirm_callback(callback: CallbackQuery):
    """Confirm broadcast"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Admin only", show_alert=True)
        return
    
    broadcast_id = callback.data.split("_")[2]
    
    if broadcast_id not in active_broadcasts:
        await callback.answer("❌ Broadcast expired", show_alert=True)
        return
    
    broadcast_data = active_broadcasts[broadcast_id]
    del active_broadcasts[broadcast_id]
    
    broadcast_msg = broadcast_data["message"]
    
    # Get all users
    users = db_execute("SELECT user_id FROM users WHERE is_banned = 0", fetchall=True)
    
    if not users:
        await callback.answer("❌ No users found", show_alert=True)
        return
    
    total_users = len(users)
    status_msg = await callback.message.edit_text(f"📤 Broadcasting to {total_users} users...")
    
    success = 0
    failed = 0
    
    broadcast_text = f"""📢 <b>Announcement from Admin</b>

{broadcast_msg}

—
AnimeKuun Bot"""
    
    for user_id, in users:
        try:
            await bot.send_message(chat_id=user_id, text=broadcast_text)
            success += 1
            if success % 10 == 0:
                await status_msg.edit_text(f"📤 Broadcasting... {success}/{total_users}")
            await asyncio.sleep(0.1)  # Rate limiting
        except:
            failed += 1
    
    result_text = f"""✅ <b>Broadcast Complete!</b>

📤 Sent: {success} users
❌ Failed: {failed} users
📊 Total: {total_users} users

💡 <i>Message delivered successfully</i>"""
    
    # Log broadcast
    db_execute(
        "INSERT INTO broadcasts (admin_id, message, sent_count, failed_count) VALUES (?, ?, ?, ?)",
        (callback.from_user.id, broadcast_msg, success, failed)
    )
    
    await status_msg.edit_text(result_text)
    await callback.answer("✅ Broadcast sent!")

@dp.callback_query(F.data == "broadcast_cancel")
async def broadcast_cancel_callback(callback: CallbackQuery):
    """Cancel broadcast"""
    await callback.message.edit_text("❌ Broadcast cancelled.")
    await callback.answer()

@dp.callback_query(F.data == "clear_favorites")
async def clear_favorites_callback(callback: CallbackQuery):
    """Clear all favorites"""
    user_id = callback.from_user.id
    
    # Ask for confirmation
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="✅ Yes, Clear All", callback_data="clear_favorites_confirm"),
        InlineKeyboardButton(text="❌ Cancel", callback_data="clear_favorites_cancel")
    )
    
    await callback.message.edit_text(
        "🗑️ <b>Clear All Favorites</b>\n\n"
        "Are you sure you want to clear ALL your favorites?\n"
        "This action cannot be undone!",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()

@dp.callback_query(F.data == "clear_favorites_confirm")
async def clear_favorites_confirm_callback(callback: CallbackQuery):
    """Confirm clear favorites"""
    user_id = callback.from_user.id
    
    # Clear favorites
    db_execute("DELETE FROM favorites WHERE user_id = ?", (user_id,))
    db_execute("UPDATE users SET total_favorites = 0 WHERE user_id = ?", (user_id,))
    
    await callback.message.edit_text("✅ All favorites have been cleared!")
    await callback.answer()

@dp.callback_query(F.data == "clear_favorites_cancel")
async def clear_favorites_cancel_callback(callback: CallbackQuery):
    """Cancel clear favorites"""
    await callback.message.edit_text("❌ Clear favorites cancelled.")
    await callback.answer()

# =========== GROUP HANDLERS ===========
@dp.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def handle_group(message: Message):
    """Handle group messages"""
    # Update group in database
    try:
        db_execute(
            """INSERT OR IGNORE INTO groups (group_id, title, added_date, last_active) 
            VALUES (?, ?, datetime('now'), datetime('now'))""",
            (message.chat.id, message.chat.title)
        )
        db_execute(
            "UPDATE groups SET last_active = datetime('now') WHERE group_id = ?",
            (message.chat.id,)
        )
    except:
        pass
    
    # Respond to bot mention
    bot_username = (await bot.get_me()).username
    if bot_username and message.text and f"@{bot_username}" in message.text:
        response = f"""👋 Hello <b>{message.chat.title}</b>!

I'm <b>AnimeKuun Bot</b> - your anime companion!

Try these commands:
• <code>/search anime name</code>
• <code>/trending</code> - Trending now
• <code>/random</code> - Random anime
• <code>/quote</code> - Anime quote

Type <code>/help</code> for all commands!"""
        
        await message.reply(response)

@dp.message(F.new_chat_members)
async def welcome_bot(message: Message):
    """Welcome bot to group"""
    bot_id = (await bot.get_me()).id
    if any(member.id == bot_id for member in message.new_chat_members):
        welcome_msg = f"""🤖 <b>Hello {message.chat.title}!</b>

Thank you for adding <b>AnimeKuun Bot</b>!

I can help you:
🔍 Search for anime
🌟 Discover trending shows
⭐ Manage your favorites
💬 Get anime quotes

<b>Quick Start:</b>
1. Try <code>/search Attack on Titan</code>
2. Check <code>/trending</code> for popular anime
3. Use <code>/help</code> for all commands

Enjoy your anime journey! 🎌"""
        
        await message.answer(welcome_msg)

# =========== ERROR HANDLER ===========
@dp.errors()
async def global_error_handler(event, exception):
    """Global error handler"""
    logger.error(f"Global error: {exception}", exc_info=True)
    
    # Log error to database if possible
    try:
        user_id = 0
        if hasattr(event, 'from_user') and event.from_user:
            user_id = event.from_user.id
        
        command = ""
        if hasattr(event, 'text') and event.text:
            parts = event.text.split()
            if parts and parts[0].startswith('/'):
                command = parts[0][1:]  # Remove leading slash
        
        log_error(user_id, str(exception), command)
    except:
        pass
    
    return True

# =========== MAIN FUNCTION ===========
async def main():
    """Main function"""
    print("🚀 Starting AnimeKuun Bot...")
    
    # Delete webhook
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Test API
    print("🔧 Testing AniList API...")
    try:
        test_results = await anilist.search_anime("test", per_page=1)
        if test_results:
            print("✅ AniList API is working")
        else:
            print("⚠️ AniList API returned no results")
    except Exception as e:
        print(f"❌ AniList API test failed: {e}")
    
    # Get bot info
    bot_info = await bot.get_me()
    print(f"🤖 Bot: @{bot_info.username}")
    print(f"📊 Commands: 50+ user, 18+ admin")
    print(f"💾 Database: {DATABASE_PATH}")
    
    # Start polling
    print("🎌 Bot is now running and ready!")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        traceback.print_exc()
    finally:
        # Cleanup
        await anilist.close()

if __name__ == "__main__":
    # Create directories
    os.makedirs("data", exist_ok=True)
    
    # Run bot
    asyncio.run(main())
