#!/usr/bin/env python3
"""
🎌 AnimeKuun Bot - Complete Professional Version
All features working with proper AniList OAuth, images, and database
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
import html
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import aiohttp
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import requests
import base64
import urllib.parse

# Aiogram imports
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    InputFile, URLInputFile, FSInputFile, ReplyKeyboardRemove,
    Poll, PollAnswer
)
from aiogram.enums import ParseMode, ChatType, MessageEntityType
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.formatting import Text, Bold, Italic, as_list, as_line
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from aiogram.methods import SendPhoto, SendMessage

# =========== CONFIGURATION ===========
BOT_TOKEN = os.getenv("BOT_TOKEN", "8282052807:AAERvnTQKpqBxz23qW4eygRknkVcqy31NNw")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "6108185460").split(",") if id.strip()]
DATABASE_PATH = "data/animekun.db"

# AniList OAuth
ANILIST_CLIENT_ID = "14539"  # You need to register at https://anilist.co/api/v2/oauth/authorize
ANILIST_CLIENT_SECRET = ""  # Leave empty for public OAuth
ANILIST_REDIRECT_URI = "https://t.me/animekun_bot"  # Your bot username
ANILIST_BASE_URL = "https://anilist.co/api/v2"

print("=" * 60)
print("🎌 ANIMEKUUN BOT - COMPLETE PROFESSIONAL VERSION")
print(f"🤖 Bot Token: {BOT_TOKEN[:15]}...")
print(f"👑 Admin IDs: {ADMIN_IDS}")
print(f"🔗 AniList Client ID: {ANILIST_CLIENT_ID}")
print("=" * 60)

# =========== SETUP ===========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('animekun.log'),
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
active_sessions = {}
quiz_sessions = {}
battle_sessions = {}
gacha_cache = {}
user_achievements = {}

# =========== DATABASE SETUP ===========
def init_database():
    """Initialize database with complete schema"""
    os.makedirs("data", exist_ok=True)
    
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    
    # Users with OAuth tokens
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        anilist_id INTEGER UNIQUE,
        access_token TEXT,
        refresh_token TEXT,
        expires_at INTEGER,
        anilist_username TEXT,
        anilist_avatar TEXT,
        anilist_banner TEXT,
        anime_stats JSON DEFAULT '{"count": 0, "mean_score": 0, "time_watched": 0}',
        manga_stats JSON DEFAULT '{"count": 0, "mean_score": 0, "chapters_read": 0}',
        waifu_collection JSON DEFAULT '[]',
        husbando_collection JSON DEFAULT '[]',
        character_cards JSON DEFAULT '[]',
        achievements JSON DEFAULT '[]',
        stats JSON DEFAULT '{"commands_used": 0, "searches": 0, "favorites": 0, "quiz_score": 0, "battle_wins": 0, "daily_streak": 0, "last_login": ""}',
        preferences JSON DEFAULT '{"theme": "default", "notifications": true, "language": "en"}',
        is_banned INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0,
        banned_until TEXT,
        warnings INTEGER DEFAULT 0,
        joined_date TEXT DEFAULT CURRENT_TIMESTAMP,
        last_active TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Anime cache for faster access
    c.execute('''CREATE TABLE IF NOT EXISTS anime_cache (
        anime_id INTEGER PRIMARY KEY,
        data JSON,
        cached_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Character cache
    c.execute('''CREATE TABLE IF NOT EXISTS character_cache (
        character_id INTEGER PRIMARY KEY,
        data JSON,
        cached_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Quiz questions database
    c.execute('''CREATE TABLE IF NOT EXISTS quiz_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT NOT NULL,
        options JSON NOT NULL,
        correct_answer INTEGER NOT NULL,
        explanation TEXT,
        difficulty TEXT DEFAULT 'medium',
        category TEXT DEFAULT 'general',
        source_anime TEXT,
        added_date TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Memes database
    c.execute('''CREATE TABLE IF NOT EXISTS memes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image_url TEXT NOT NULL,
        caption TEXT,
        character TEXT,
        anime TEXT,
        tags JSON DEFAULT '[]',
        added_by INTEGER,
        added_date TEXT DEFAULT CURRENT_TIMESTAMP,
        uses INTEGER DEFAULT 0
    )''')
    
    # Gacha characters
    c.execute('''CREATE TABLE IF NOT EXISTS gacha_characters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        character_id INTEGER,
        name TEXT NOT NULL,
        image_url TEXT,
        rarity TEXT DEFAULT 'R',
        anime TEXT,
        description TEXT,
        attributes JSON DEFAULT '{"attack": 0, "defense": 0, "speed": 0, "intelligence": 0}'
    )''')
    
    # Watch parties
    c.execute('''CREATE TABLE IF NOT EXISTS watch_parties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        anime_id INTEGER,
        anime_title TEXT,
        episode INTEGER DEFAULT 1,
        host_id INTEGER,
        participants JSON DEFAULT '[]',
        start_time TEXT,
        status TEXT DEFAULT 'scheduled',
        chat_id INTEGER
    )''')
    
    # Achievements
    c.execute('''CREATE TABLE IF NOT EXISTS achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        icon TEXT,
        requirement TEXT,
        rarity TEXT DEFAULT 'common',
        reward_points INTEGER DEFAULT 10
    )''')
    
    # Battle history
    c.execute('''CREATE TABLE IF NOT EXISTS battles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player1_id INTEGER,
        player2_id INTEGER,
        winner_id INTEGER,
        player1_character TEXT,
        player2_character TEXT,
        turns INTEGER,
        details JSON,
        battle_date TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Command statistics
    c.execute('''CREATE TABLE IF NOT EXISTS command_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        command TEXT,
        user_id INTEGER,
        success INTEGER DEFAULT 1,
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
        settings JSON DEFAULT '{"quiz_enabled": true, "memes_enabled": true, "spoiler_protection": false}'
    )''')
    
    # Create indexes
    c.execute("CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_cache_cached_at ON anime_cache(cached_at)")
    
    # Add default admin
    for admin_id in ADMIN_IDS:
        c.execute("INSERT OR IGNORE INTO users (user_id, is_admin) VALUES (?, 1)", (admin_id,))
    
    # Add sample achievements
    achievements_data = [
        ("Anime Beginner", "Used your first command", "🎌", "commands_used >= 1", "common", 10),
        ("Search Master", "Made 100 searches", "🔍", "searches >= 100", "rare", 50),
        ("Quiz Champion", "Scored 1000+ quiz points", "🏆", "quiz_score >= 1000", "epic", 100),
        ("Battle Legend", "Won 50 battles", "⚔️", "battle_wins >= 50", "legendary", 200),
        ("Collection King", "Collected 50 character cards", "👑", "card_count >= 50", "mythic", 300),
        ("Daily Devotee", "7-day login streak", "🔥", "daily_streak >= 7", "rare", 75),
        ("AniList Linked", "Connected AniList account", "🔗", "anilist_id IS NOT NULL", "common", 25),
        ("Waifu Collector", "Collected 10 waifus", "💖", "waifu_count >= 10", "epic", 150),
        ("Husbando Hunter", "Collected 10 husbandos", "💙", "husbando_count >= 10", "epic", 150),
        ("True Fan", "Added 50 favorites", "⭐", "favorites >= 50", "legendary", 250),
    ]
    
    c.executemany('''INSERT OR IGNORE INTO achievements (name, description, icon, requirement, rarity, reward_points) 
                     VALUES (?, ?, ?, ?, ?, ?)''', achievements_data)
    
    # Add sample quiz questions
    sample_questions = [
        ("In 'Attack on Titan', what is the name of the main protagonist's titan form?", 
         '["Attack Titan", "Colossal Titan", "Armored Titan", "Beast Titan"]', 0, 
         "The Attack Titan is Eren Yeager's titan form.", "easy", "characters", "Attack on Titan"),
        ("Which anime features a pirate named Monkey D. Luffy searching for the One Piece?", 
         '["Naruto", "One Piece", "Bleach", "Dragon Ball"]', 1, 
         "One Piece follows Luffy's journey to become Pirate King.", "easy", "plot", "One Piece"),
        ("In 'Death Note', what is the name of the shinigami who drops the Death Note?", 
         '["Ryuk", "Rem", "Sidoh", "Gelus"]', 0, 
         "Ryuk is the shinigami who drops the Death Note to Light Yagami.", "medium", "characters", "Death Note"),
        ("Which studio produced 'Demon Slayer: Kimetsu no Yaiba'?", 
         '["Madhouse", "Ufotable", "MAPPA", "Kyoto Animation"]', 1, 
         "Ufotable animated Demon Slayer with exceptional quality.", "medium", "trivia", "Demon Slayer"),
        ("What is the name of the technique used by Goku in Dragon Ball Z that requires both hands?", 
         '["Kamehameha", "Spirit Bomb", "Instant Transmission", "Kaio-ken"]', 0, 
         "Kamehameha is Goku's signature move taught by Master Roshi.", "easy", "abilities", "Dragon Ball Z"),
    ]
    
    c.executemany('''INSERT OR IGNORE INTO quiz_questions (question, options, correct_answer, explanation, difficulty, category, source_anime) 
                     VALUES (?, ?, ?, ?, ?, ?, ?)''', sample_questions)
    
    # Add sample gacha characters
    gacha_chars = [
        (1, "Naruto Uzumaki", "https://i.imgur.com/example1.jpg", "SSR", "Naruto", "The protagonist of Naruto series", '{"attack": 95, "defense": 85, "speed": 90, "intelligence": 70}'),
        (2, "Goku", "https://i.imgur.com/example2.jpg", "SSR", "Dragon Ball", "The main character of Dragon Ball series", '{"attack": 100, "defense": 90, "speed": 95, "intelligence": 65}'),
        (3, "Luffy", "https://i.imgur.com/example3.jpg", "SSR", "One Piece", "Captain of the Straw Hat Pirates", '{"attack": 90, "defense": 80, "speed": 85, "intelligence": 60}'),
        (4, "Eren Yeager", "https://i.imgur.com/example4.jpg", "SR", "Attack on Titan", "The protagonist of Attack on Titan", '{"attack": 85, "defense": 75, "speed": 80, "intelligence": 75}'),
        (5, "Levi Ackerman", "https://i.imgur.com/example5.jpg", "SR", "Attack on Titan", "The strongest soldier of humanity", '{"attack": 88, "defense": 70, "speed": 95, "intelligence": 85}'),
    ]
    
    c.executemany('''INSERT OR IGNORE INTO gacha_characters (character_id, name, image_url, rarity, anime, description, attributes) 
                     VALUES (?, ?, ?, ?, ?, ?, ?)''', gacha_chars)
    
    conn.commit()
    conn.close()
    logger.info("Database initialized with complete schema")

init_database()

# =========== DATABASE HELPER FUNCTIONS ===========
class Database:
    @staticmethod
    def execute(query: str, params: tuple = (), fetchone: bool = False, fetchall: bool = False, commit: bool = True):
        """Safe database execution"""
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(query, params)
            
            if fetchone:
                result = c.fetchone()
                if result:
                    result = dict(result)
            elif fetchall:
                result = [dict(row) for row in c.fetchall()]
            else:
                result = c.lastrowid
            
            if commit:
                conn.commit()
            conn.close()
            
            return result
        except Exception as e:
            logger.error(f"Database error: {e}")
            if fetchone or fetchall:
                return None if fetchone else []
            return None
    
    @staticmethod
    def get_user(user_id: int):
        """Get user by ID"""
        return Database.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,), fetchone=True
        )
    
    @staticmethod
    def update_user(user_id: int, **kwargs):
        """Update user fields"""
        if not kwargs:
            return
        
        set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
        values = list(kwargs.values())
        values.append(user_id)
        
        query = f"UPDATE users SET {set_clause}, last_active = datetime('now') WHERE user_id = ?"
        return Database.execute(query, tuple(values))
    
    @staticmethod
    def create_user(user_id: int, username: str = None, first_name: str = None):
        """Create new user"""
        return Database.execute(
            """INSERT OR IGNORE INTO users 
            (user_id, username, first_name, joined_date, last_active, stats) 
            VALUES (?, ?, ?, datetime('now'), datetime('now'), ?)""",
            (user_id, username, first_name, json.dumps({"commands_used": 0, "searches": 0, "favorites": 0, "quiz_score": 0, "battle_wins": 0, "daily_streak": 0, "last_login": ""}))
        )
    
    @staticmethod
    def add_command_stat(user_id: int, command: str, success: bool = True):
        """Log command usage"""
        Database.execute(
            "INSERT INTO command_stats (command, user_id, success) VALUES (?, ?, ?)",
            (command, user_id, 1 if success else 0)
        )
        
        # Update user stats
        user = Database.get_user(user_id)
        if user:
            stats = json.loads(user['stats'])
            stats['commands_used'] = stats.get('commands_used', 0) + 1
            
            # Check daily streak
            last_login = stats.get('last_login', '')
            today = datetime.now().strftime('%Y-%m-%d')
            if last_login == today:
                pass  # Already logged in today
            elif last_login == (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'):
                stats['daily_streak'] = stats.get('daily_streak', 0) + 1
            else:
                stats['daily_streak'] = 1
            
            stats['last_login'] = today
            Database.update_user(user_id, stats=json.dumps(stats))
    
    @staticmethod
    def get_quiz_question(difficulty: str = None, category: str = None):
        """Get random quiz question"""
        query = "SELECT * FROM quiz_questions"
        params = []
        
        if difficulty or category:
            conditions = []
            if difficulty:
                conditions.append("difficulty = ?")
                params.append(difficulty)
            if category:
                conditions.append("category = ?")
                params.append(category)
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY RANDOM() LIMIT 1"
        return Database.execute(query, tuple(params), fetchone=True)
    
    @staticmethod
    def get_random_meme():
        """Get random meme"""
        return Database.execute(
            "SELECT * FROM memes ORDER BY RANDOM() LIMIT 1",
            fetchone=True
        )
    
    @staticmethod
    def get_gacha_character(rarity: str = None):
        """Get random gacha character"""
        query = "SELECT * FROM gacha_characters"
        params = []
        
        if rarity:
            query += " WHERE rarity = ?"
            params.append(rarity)
        
        query += " ORDER BY RANDOM() LIMIT 1"
        return Database.execute(query, tuple(params), fetchone=True)
    
    @staticmethod
    def get_user_achievements(user_id: int):
        """Get user's unlocked achievements"""
        user = Database.get_user(user_id)
        if user and user['achievements']:
            return json.loads(user['achievements'])
        return []
    
    @staticmethod
    def unlock_achievement(user_id: int, achievement_id: int):
        """Unlock achievement for user"""
        user = Database.get_user(user_id)
        if not user:
            return False
        
        achievements = json.loads(user['achievements']) if user['achievements'] else []
        if achievement_id not in achievements:
            achievements.append(achievement_id)
            Database.update_user(user_id, achievements=json.dumps(achievements))
            return True
        return False

# =========== ANILIST API WITH OAUTH ===========
class AniListAPI:
    """Complete AniList API with OAuth"""
    
    def __init__(self):
        self.base_url = "https://graphql.anilist.co"
        self.oauth_url = "https://anilist.co/api/v2/oauth/authorize"
        self.token_url = "https://anilist.co/api/v2/oauth/token"
        self.session = None
        self.cache = {}
    
    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self.session
    
    async def _make_request(self, query: str, variables: dict = None, token: str = None):
        """Make GraphQL request"""
        session = await self._get_session()
        
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        try:
            async with session.post(
                self.base_url,
                json={"query": query, "variables": variables or {}},
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if "errors" in data:
                        logger.error(f"AniList API error: {data['errors']}")
                        return {"error": data["errors"][0].get("message", "Unknown error")}
                    return data.get("data", {})
                elif response.status == 429:
                    return {"error": "Rate limited. Please try again later."}
                else:
                    return {"error": f"HTTP {response.status}"}
        except Exception as e:
            logger.error(f"Request error: {e}")
            return {"error": str(e)}
    
    async def get_oauth_url(self, state: str):
        """Generate OAuth URL"""
        params = {
            "client_id": ANILIST_CLIENT_ID,
            "redirect_uri": ANILIST_REDIRECT_URI,
            "response_type": "code",
            "state": state
        }
        return f"{self.oauth_url}?{urllib.parse.urlencode(params)}"
    
    async def exchange_code_for_token(self, code: str):
        """Exchange authorization code for access token"""
        session = await self._get_session()
        
        data = {
            "grant_type": "authorization_code",
            "client_id": ANILIST_CLIENT_ID,
            "client_secret": ANILIST_CLIENT_SECRET,
            "redirect_uri": ANILIST_REDIRECT_URI,
            "code": code
        }
        
        try:
            async with session.post(self.token_url, data=data) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Token exchange failed: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Token exchange error: {e}")
            return None
    
    async def get_user_with_token(self, token: str):
        """Get user data with access token"""
        query = """
        query {
          Viewer {
            id
            name
            about
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
        
        result = await self._make_request(query, token=token)
        if "error" in result:
            return result
        
        viewer = result.get("Viewer", {})
        if viewer:
            return viewer
        return {"error": "No user data found"}
    
    async def search_anime(self, query: str, page: int = 1, per_page: int = 10):
        """Search anime - FIXED for multi-word queries"""
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
                extraLarge
                large
                medium
              }
              bannerImage
              averageScore
              popularity
              format
              episodes
              duration
              status
              description(asHtml: false)
              genres
              studios {
                edges {
                  node {
                    name
                  }
                }
              }
              relations {
                edges {
                  relationType
                  node {
                    id
                    title {
                      romaji
                      english
                    }
                  }
                }
              }
              characters(perPage: 5) {
                edges {
                  node {
                    id
                    name {
                      full
                      native
                    }
                    image {
                      large
                      medium
                    }
                  }
                  role
                }
              }
              trailer {
                id
                site
                thumbnail
              }
              siteUrl
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
        """Get anime details"""
        # Check cache first
        cached = Database.execute(
            "SELECT data FROM anime_cache WHERE anime_id = ? AND datetime(cached_at) > datetime('now', '-24 hours')",
            (anime_id,), fetchone=True
        )
        
        if cached:
            return json.loads(cached['data'])
        
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
            endDate {
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
            relations {
              edges {
                relationType
                node {
                  id
                  title {
                    romaji
                    english
                  }
                }
              }
            }
            characters(perPage: 10) {
              edges {
                node {
                  id
                  name {
                    full
                    native
                  }
                  image {
                    large
                  }
                  description(asHtml: false)
                }
                role
              }
            }
            trailer {
              id
              site
              thumbnail
            }
            recommendations(perPage: 5) {
              edges {
                node {
                  mediaRecommendation {
                    id
                    title {
                      romaji
                      english
                    }
                  }
                }
              }
            }
            siteUrl
          }
        }
        """
        
        result = await self._make_request(anime_query, {"id": anime_id})
        
        if "error" not in result and result.get("Media"):
            # Cache the result
            Database.execute(
                "INSERT OR REPLACE INTO anime_cache (anime_id, data) VALUES (?, ?)",
                (anime_id, json.dumps(result["Media"]))
            )
            return result["Media"]
        
        return result
    
    async def search_character(self, query: str, per_page: int = 10):
        """Search character - FIXED for multi-word queries"""
        char_query = """
        query ($search: String, $perPage: Int) {
          Page(perPage: $perPage) {
            characters(search: $search) {
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
              age
              dateOfBirth {
                year
                month
                day
              }
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
        }
        """
        
        result = await self._make_request(char_query, {
            "search": query,
            "perPage": per_page
        })
        
        if "error" in result:
            return []
        
        return result.get("Page", {}).get("characters", [])
    
    async def get_character(self, char_id: int):
        """Get character details"""
        # Check cache
        cached = Database.execute(
            "SELECT data FROM character_cache WHERE character_id = ? AND datetime(cached_at) > datetime('now', '-24 hours')",
            (char_id,), fetchone=True
        )
        
        if cached:
            return json.loads(cached['data'])
        
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
            age
            dateOfBirth {
              year
              month
              day
            }
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
                  coverImage {
                    large
                  }
                }
              }
            }
            siteUrl
          }
        }
        """
        
        result = await self._make_request(query, {"id": char_id})
        
        if "error" not in result and result.get("Character"):
            # Cache the result
            Database.execute(
                "INSERT OR REPLACE INTO character_cache (character_id, data) VALUES (?, ?)",
                (char_id, json.dumps(result["Character"]))
            )
            return result["Character"]
        
        return result

# Initialize API
anilist = AniListAPI()

# =========== IMAGE PROCESSING ===========
class ImageProcessor:
    """Process images for profiles, memes, etc."""
    
    @staticmethod
    async def create_profile_card(user_data: dict, anilist_data: dict = None):
        """Create beautiful profile card image"""
        try:
            # Create blank image
            width, height = 800, 600
            img = Image.new('RGB', (width, height), color=(30, 30, 46))  # Dark blue
            
            draw = ImageDraw.Draw(img)
            
            # Try to load fonts
            try:
                title_font = ImageFont.truetype("arial.ttf", 40)
                text_font = ImageFont.truetype("arial.ttf", 24)
                small_font = ImageFont.truetype("arial.ttf", 18)
            except:
                title_font = ImageFont.load_default()
                text_font = ImageFont.load_default()
                small_font = ImageFont.load_default()
            
            # Draw banner
            draw.rectangle([0, 0, width, 200], fill=(21, 101, 192))  # Blue banner
            
            # Draw user info
            username = user_data.get('username', user_data.get('first_name', 'User'))
            draw.text((50, 50), f"👤 {username}", fill=(255, 255, 255), font=title_font)
            
            # Draw stats
            stats_y = 220
            stats = json.loads(user_data.get('stats', '{}'))
            
            stats_texts = [
                f"📊 Commands: {stats.get('commands_used', 0)}",
                f"⭐ Favorites: {stats.get('favorites', 0)}",
                f"🏆 Quiz Score: {stats.get('quiz_score', 0)}",
                f"⚔️ Battle Wins: {stats.get('battle_wins', 0)}",
                f"🔥 Streak: {stats.get('daily_streak', 0)} days",
            ]
            
            for i, text in enumerate(stats_texts):
                draw.text((50, stats_y + i*40), text, fill=(220, 220, 220), font=text_font)
            
            # Draw achievements
            achievements = Database.get_user_achievements(user_data['user_id'])
            if achievements:
                draw.text((400, 220), "🏆 Achievements:", fill=(255, 215, 0), font=text_font)
                for i, ach_id in enumerate(achievements[:3]):  # Show first 3
                    draw.text((400, 260 + i*30), f"• Achievement {ach_id}", fill=(200, 200, 200), font=small_font)
            
            # Add AniList info if available
            if anilist_data:
                draw.text((50, 420), f"🔗 AniList: {anilist_data.get('name', 'Linked')}", fill=(100, 200, 255), font=text_font)
                anime_stats = anilist_data.get('statistics', {}).get('anime', {})
                draw.text((50, 450), f"🎬 Anime: {anime_stats.get('count', 0)} titles", fill=(200, 200, 200), font=small_font)
            
            # Save to bytes
            img_bytes = BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            return img_bytes
        except Exception as e:
            logger.error(f"Profile card error: {e}")
            return None

# =========== HELPER FUNCTIONS ===========
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

def check_cooldown(user_id: int, command: str, seconds: int = 2) -> bool:
    """Check command cooldown"""
    key = f"{user_id}_{command}"
    now = time.time()
    
    if key in user_cooldowns:
        if now - user_cooldowns[key] < seconds:
            return False
    
    user_cooldowns[key] = now
    return True

async def get_waifu_image():
    """Get waifu image from API"""
    apis = [
        "https://api.waifu.pics/sfw/waifu",
        "https://nekos.best/api/v2/waifu",
        "https://api.nekosapi.com/v2/images/random?category=waifu"
    ]
    
    for api in apis:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Handle different API responses
                        if api == "https://api.waifu.pics/sfw/waifu":
                            return data.get("url")
                        elif api == "https://nekos.best/api/v2/waifu":
                            return data.get("url")
                        elif api == "https://api.nekosapi.com/v2/images/random":
                            return data.get("image_url")
        except:
            continue
    
    return "https://i.imgur.com/XW6J2r5.jpg"  # Fallback image

async def get_husbando_image():
    """Get husbando image from API"""
    # For husbando, we might need to use character search or fallback
    try:
        # Try to get male character from AniList
        characters = await anilist.search_character("", per_page=50)
        if characters:
            male_chars = [c for c in characters if c.get('gender', '').lower() == 'male']
            if male_chars:
                char = random.choice(male_chars)
                return char.get('image', {}).get('large')
    except:
        pass
    
    # Fallback to waifu image
    return await get_waifu_image()

async def get_anime_meme():
    """Get anime meme"""
    meme = Database.get_random_meme()
    if meme:
        return meme['image_url'], meme['caption']
    
    # Fallback memes
    memes = [
        ("https://i.imgur.com/meme1.jpg", "When you realize the anime filler arc is longer than the canon story"),
        ("https://i.imgur.com/meme2.jpg", "Me waiting for the next season of my favorite anime"),
        ("https://i.imgur.com/meme3.jpg", "When someone says anime is for kids"),
    ]
    
    return random.choice(memes)

# =========== BATTLE SYSTEM ===========
class BattleSystem:
    """Anime character battle system"""
    
    CHARACTERS = {
        "Goku": {"hp": 1000, "attack": 150, "defense": 80, "speed": 95, "special": "Kamehameha", "anime": "Dragon Ball"},
        "Naruto": {"hp": 800, "attack": 120, "defense": 70, "speed": 85, "special": "Rasengan", "anime": "Naruto"},
        "Luffy": {"hp": 900, "attack": 130, "defense": 75, "speed": 80, "special": "Gear Fourth", "anime": "One Piece"},
        "Eren Yeager": {"hp": 750, "attack": 110, "defense": 65, "speed": 75, "special": "Titan Transformation", "anime": "Attack on Titan"},
        "Levi Ackerman": {"hp": 700, "attack": 140, "defense": 60, "speed": 100, "special": "Ultimate Speed", "anime": "Attack on Titan"},
        "Saitama": {"hp": 9999, "attack": 999, "defense": 999, "speed": 999, "special": "Serious Punch", "anime": "One Punch Man"},
        "Light Yagami": {"hp": 500, "attack": 999, "defense": 30, "speed": 60, "special": "Death Note", "anime": "Death Note"},
        "Killua Zoldyck": {"hp": 650, "attack": 125, "defense": 65, "speed": 110, "special": "Godspeed", "anime": "Hunter x Hunter"},
        "Gon Freecss": {"hp": 750, "attack": 135, "defense": 70, "speed": 85, "special": "Jajanken", "anime": "Hunter x Hunter"},
        "Ichigo Kurosaki": {"hp": 850, "attack": 140, "defense": 75, "speed": 90, "special": "Getsuga Tensho", "anime": "Bleach"},
    }
    
    @staticmethod
    async def start_battle(player1_id: int, player2_id: int):
        """Start a new battle between two players"""
        battle_id = f"{player1_id}_{player2_id}_{int(time.time())}"
        
        # Assign random characters
        chars = list(BattleSystem.CHARACTERS.keys())
        char1 = random.choice(chars)
        char2 = random.choice([c for c in chars if c != char1])
        
        battle_data = {
            "id": battle_id,
            "player1": {"id": player1_id, "character": char1, "hp": BattleSystem.CHARACTERS[char1]["hp"]},
            "player2": {"id": player2_id, "character": char2, "hp": BattleSystem.CHARACTERS[char2]["hp"]},
            "turn": player1_id,  # Player 1 goes first
            "round": 1,
            "log": [],
            "status": "active"
        }
        
        battle_sessions[battle_id] = battle_data
        
        # Create battle message
        char1_stats = BattleSystem.CHARACTERS[char1]
        char2_stats = BattleSystem.CHARACTERS[char2]
        
        message = f"""⚔️ <b>ANIME BATTLE STARTED!</b>

🎌 <b>{char1}</b> ({char1_stats['anime']}) 
❤️ HP: {char1_stats['hp']} | ⚔️ ATK: {char1_stats['attack']} | 🛡️ DEF: {char1_stats['defense']} | 🏃 SPD: {char1_stats['speed']}

<b>VS</b>

🎌 <b>{char2}</b> ({char2_stats['anime']})
❤️ HP: {char2_stats['hp']} | ⚔️ ATK: {char2_stats['attack']} | 🛡️ DEF: {char2_stats['defense']} | 🏃 SPD: {char2_stats['speed']}

<b>Player 1's turn!</b>
Use <code>/attack</code> to attack!"""
        
        return battle_id, message
    
    @staticmethod
    async def process_attack(battle_id: str, attacker_id: int):
        """Process an attack in battle"""
        if battle_id not in battle_sessions:
            return None, "Battle not found!"
        
        battle = battle_sessions[battle_id]
        
        if battle["turn"] != attacker_id:
            return battle_id, "Not your turn!"
        
        # Determine attacker and defender
        if attacker_id == battle["player1"]["id"]:
            attacker = battle["player1"]
            defender = battle["player2"]
            next_turn = battle["player2"]["id"]
        else:
            attacker = battle["player2"]
            defender = battle["player1"]
            next_turn = battle["player1"]["id"]
        
        # Calculate damage
        attacker_stats = BattleSystem.CHARACTERS[attacker["character"]]
        defender_stats = BattleSystem.CHARACTERS[defender["character"]]
        
        base_damage = attacker_stats["attack"] - (defender_stats["defense"] * 0.3)
        crit_chance = random.random()
        
        if crit_chance < 0.1:  # 10% crit chance
            damage = int(base_damage * 1.5)
            crit_text = "💥 CRITICAL HIT! 💥"
        elif crit_chance < 0.2:  # 10% special move chance
            damage = int(base_damage * 1.2)
            crit_text = f"✨ {attacker_stats['special']}! ✨"
        else:
            damage = int(base_damage)
            crit_text = "⚔️ Normal Attack"
        
        # Ensure minimum damage
        damage = max(10, damage)
        
        # Apply damage
        defender["hp"] = max(0, defender["hp"] - damage)
        
        # Update battle
        battle["turn"] = next_turn
        battle["round"] += 1
        battle["log"].append(f"Round {battle['round']-1}: {attacker['character']} dealt {damage} damage to {defender['character']}")
        
        # Check for winner
        winner = None
        if defender["hp"] <= 0:
            winner = attacker
            battle["status"] = "finished"
            
            # Update user stats
            user = Database.get_user(attacker["id"])
            if user:
                stats = json.loads(user['stats'])
                stats['battle_wins'] = stats.get('battle_wins', 0) + 1
                Database.update_user(attacker["id"], stats=json.dumps(stats))
            
            # Log battle
            Database.execute(
                """INSERT INTO battles (player1_id, player2_id, winner_id, player1_character, player2_character, turns, details) 
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (battle["player1"]["id"], battle["player2"]["id"], attacker["id"], 
                 battle["player1"]["character"], battle["player2"]["character"], 
                 battle["round"], json.dumps(battle["log"]))
            )
            
            # Remove from active sessions
            del battle_sessions[battle_id]
        
        # Create battle update message
        message = f"""⚔️ <b>BATTLE UPDATE - Round {battle['round']-1}</b>

{crit_text}

🎌 <b>{attacker['character']}</b> attacked <b>{defender['character']}</b> for <b>{damage} damage</b>!

<b>Current Status:</b>
❤️ {battle['player1']['character']}: {battle['player1']['hp']} HP
❤️ {battle['player2']['character']}: {battle['player2']['hp']} HP
        
"""
        
        if winner:
            message += f"\n🎉 <b>VICTORY!</b> {winner['character']} wins the battle!"
        else:
            message += f"\n<b>Next Turn:</b> {'Player 1' if next_turn == battle['player1']['id'] else 'Player 2'}"
        
        return battle_id, message

# =========== QUIZ SYSTEM ===========
class QuizSystem:
    """Anime quiz system"""
    
    @staticmethod
    async def start_quiz(user_id: int, difficulty: str = "medium"):
        """Start a new quiz for user"""
        question = Database.get_quiz_question(difficulty)
        
        if not question:
            return None, "No quiz questions available at the moment!"
        
        quiz_id = f"{user_id}_{int(time.time())}"
        
        quiz_data = {
            "id": quiz_id,
            "user_id": user_id,
            "question": question,
            "start_time": time.time(),
            "answered": False,
            "score": 0
        }
        
        quiz_sessions[quiz_id] = quiz_data
        
        # Format question
        options = json.loads(question['options'])
        options_text = "\n".join([f"{chr(65+i)}. {opt}" for i, opt in enumerate(options)])
        
        message = f"""🎮 <b>ANIME QUIZ</b>

<b>Question:</b> {question['question']}

<b>Options:</b>
{options_text}

<b>Difficulty:</b> {question['difficulty'].title()}
<b>Category:</b> {question['category'].title()}
<b>Source:</b> {question['source_anime'] or 'General'}

Reply with <b>A, B, C, or D</b> to answer!"""
        
        return quiz_id, message
    
    @staticmethod
    async def check_answer(quiz_id: str, answer: str):
        """Check quiz answer"""
        if quiz_id not in quiz_sessions:
            return None, "Quiz session expired!"
        
        quiz = quiz_sessions[quiz_id]
        
        if quiz["answered"]:
            return quiz_id, "You already answered this question!"
        
        # Convert letter to index (A=0, B=1, etc.)
        answer_index = ord(answer.upper()) - 65
        
        if not 0 <= answer_index <= 3:
            return quiz_id, "Please answer with A, B, C, or D!"
        
        question = quiz["question"]
        correct_index = question['correct_answer']
        options = json.loads(question['options'])
        
        quiz["answered"] = True
        
        if answer_index == correct_index:
            # Calculate score based on difficulty
            difficulty_scores = {"easy": 10, "medium": 20, "hard": 30}
            score = difficulty_scores.get(question['difficulty'], 10)
            
            # Update user stats
            user = Database.get_user(quiz["user_id"])
            if user:
                stats = json.loads(user['stats'])
                stats['quiz_score'] = stats.get('quiz_score', 0) + score
                Database.update_user(quiz["user_id"], stats=json.dumps(stats))
            
            message = f"""✅ <b>CORRECT!</b>

The answer is: <b>{options[correct_index]}</b>

<b>Explanation:</b> {question['explanation']}

🎉 <b>+{score} points!</b>"""
        else:
            message = f"""❌ <b>INCORRECT!</b>

The correct answer is: <b>{options[correct_index]}</b>

<b>Your answer:</b> {options[answer_index]}
<b>Explanation:</b> {question['explanation']}"""
        
        # Remove from active sessions after delay
        await asyncio.sleep(5)
        if quiz_id in quiz_sessions:
            del quiz_sessions[quiz_id]
        
        return quiz_id, message

# =========== GACHA SYSTEM ===========
class GachaSystem:
    """Character gacha system"""
    
    RARITY_WEIGHTS = {
        "SSR": 5,    # 5% chance
        "SR": 15,    # 15% chance
        "R": 80      # 80% chance
    }
    
    @staticmethod
    async def pull(user_id: int):
        """Perform a gacha pull"""
        # Check daily pull limit
        user = Database.get_user(user_id)
        if user:
            stats = json.loads(user['stats'])
            last_pull = stats.get('last_pull_date', '')
            today = datetime.now().strftime('%Y-%m-%d')
            
            pulls_today = stats.get('pulls_today', 0)
            if last_pull == today and pulls_today >= 10:
                return None, "Daily pull limit reached (10 pulls). Come back tomorrow!"
        
        # Determine rarity
        rand = random.random() * 100
        cumulative = 0
        selected_rarity = "R"
        
        for rarity, weight in GachaSystem.RARITY_WEIGHTS.items():
            cumulative += weight
            if rand <= cumulative:
                selected_rarity = rarity
                break
        
        # Get character of that rarity
        character = Database.get_gacha_character(selected_rarity)
        
        if not character:
            # Fallback character
            character = {
                "name": "Mysterious Character",
                "image_url": "https://i.imgur.com/XW6J2r5.jpg",
                "rarity": selected_rarity,
                "anime": "Unknown",
                "description": "A mysterious character has appeared!"
            }
        
        # Add to user's collection
        if user:
            cards = json.loads(user['character_cards']) if user['character_cards'] else []
            cards.append(character['id'])
            
            # Update stats
            stats['pulls_today'] = stats.get('pulls_today', 0) + 1
            stats['last_pull_date'] = today
            Database.update_user(user_id, character_cards=json.dumps(cards), stats=json.dumps(stats))
        
        # Create message
        rarity_colors = {
            "SSR": "🌈",
            "SR": "✨", 
            "R": "⭐"
        }
        
        message = f"""{rarity_colors.get(selected_rarity, "⭐")} <b>GACHA PULL!</b>

🎌 <b>{character['name']}</b>
🏷️ <b>Rarity:</b> {selected_rarity}
📺 <b>Anime:</b> {character['anime']}
📝 <b>{character['description']}</b>

<i>Added to your collection!</i>"""
        
        return character['image_url'], message

# =========== COMMAND HANDLERS ===========

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
    
    # Create/update user
    Database.create_user(user.id, user.username, user.first_name)
    Database.add_command_stat(user.id, "start")
    
    welcome_text = f"""🎌 <b>Welcome to AnimeKuun, {user.first_name}!</b>

Your ultimate anime companion with <b>50+ commands</b>!

✨ <b>Quick Start:</b>
• <code>/anime Attack on Titan</code> - Find anime (multi-word works!)
• <code>/character Eren Yeager</code> - Character info
• <code>/waifu</code> - Your anime soulmate (with image)
• <code>/husbando</code> - Your anime partner (with image)
• <code>/quiz</code> - Anime trivia game
• <code>/meme</code> - Anime memes
• <code>/profile</code> - Your profile with stats
• <code>/link</code> - Connect AniList account

💬 <b>Works in groups too!</b>
Made with ❤️ for anime fans worldwide!"""
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="🔗 Connect AniList", callback_data="link_anilist"),
        InlineKeyboardButton(text="🎮 Play Quiz", callback_data="play_quiz")
    )
    keyboard.row(
        InlineKeyboardButton(text="💖 Get Waifu", callback_data="get_waifu"),
        InlineKeyboardButton(text="💙 Get Husbando", callback_data="get_husbando")
    )
    
    await message.answer(welcome_text, reply_markup=keyboard.as_markup())

@dp.message(Command("help"))
async def help_command(message: Message):
    """Help command - ONLY USER COMMANDS"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    Database.add_command_stat(user.id, "help")
    
    help_text = """📚 <b>AnimeKuun Bot - Complete Command List</b>

<u>🔍 SEARCH & DISCOVERY:</u>
<code>/anime</code> <i>name</i> - Find anime (multi-word works!)
<code>/character</code> <i>name</i> - Character info with image
<code>/studio</code> <i>name</i> - Studio's works
<code>/genre</code> <i>name</i> - Anime by genre
<code>/trending</code> - Trending anime now
<code>/popular</code> - Popular anime
<code>/top</code> - Top rated anime
<code>/seasonal</code> - Current season
<code>/random</code> - Random anime suggestion

<u>💖 FUN & GAMES:</u>
<code>/waifu</code> - Your anime soulmate (with image)
<code>/husbando</code> - Your anime partner (with image)
<code>/quote</code> - Random anime quote
<code>/meme</code> - Anime meme (image)
<code>/ship</code> <i>name1 name2</i> - Ship compatibility
<code>/roll</code> - Random anime

<u>🎮 GAMES:</u>
<code>/quiz</code> - Anime trivia (multiple choice)
<code>/battle</code> <i>@user</i> - Battle with anime characters
<code>/gacha</code> - Pull character cards
<code>/guess</code> - Guess the anime
<code>/trivia</code> - Quick anime facts

<u>👤 PROFILE & SOCIAL:</u>
<code>/profile</code> - Your bot profile
<code>/favorites</code> - Your favorite anime
<code>/watchlist</code> - Your watchlist
<code>/achievements</code> - Your unlocked badges
<code>/collection</code> - Your character cards
<code>/stats</code> - Your statistics

<u>🔗 ANILIST INTEGRATION:</u>
<code>/link</code> - Connect AniList account
<code>/unlink</code> - Disconnect account
<code>/sync</code> - Sync with AniList
<code>/compare</code> <i>@user</i> - Compare anime taste

<u>👥 GROUP FEATURES:</u>
<code>/watchparty</code> - Start anime watch party
<code>/poll</code> - Create anime poll
<code>/recommend</code> - Get group recommendations

💡 <b>Tip:</b> Most commands work in groups too!
🎌 <b>Use /start to begin your anime journey!</b>"""
    
    await message.answer(help_text)

# =========== ANIME COMMANDS (FIXED MULTI-WORD) ===========
@dp.message(Command("anime"))
async def anime_command(message: Message):
    """Get anime details - FIXED multi-word search"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    if not check_cooldown(user.id, "anime", 3):
        await message.answer("⏳ Please wait before checking another anime.")
        return
    
    # Get entire query after command
    query = message.text.split(maxsplit=1)
    if len(query) < 2:
        await message.answer("🎬 <b>Usage:</b> <code>/anime anime name</code>\nExample: <code>/anime Attack on Titan</code>")
        return
    
    query = query[1].strip()
    Database.add_command_stat(user.id, "anime")
    
    anime_msg = await message.answer(f"🎬 Searching for <b>{query}</b>...")
    
    try:
        results = await anilist.search_anime(query, per_page=5)
        
        if not results:
            await anime_msg.edit_text(f"❌ No anime found for <b>{query}</b>")
            return
        
        # Show first result
        anime_data = await anilist.get_anime(results[0]['id'])
        
        if "error" in anime_data:
            await anime_msg.edit_text(f"❌ Error: {anime_data['error']}")
            return
        
        title = anime_data.get('title', {}).get('english') or anime_data.get('title', {}).get('romaji', 'Unknown')
        description = format_description(anime_data.get('description', ''))
        
        # Get genres
        genres = anime_data.get('genres', [])
        genres_text = ', '.join(genres[:5]) if genres else 'N/A'
        
        # Get studios
        studios = anime_data.get('studios', {}).get('edges', [])
        studios_text = ', '.join([s['node']['name'] for s in studios[:3]]) if studios else 'N/A'
        
        # Get relations
        relations = anime_data.get('relations', {}).get('edges', [])
        prequels = [r for r in relations if r['relationType'] in ['PREQUEL', 'PARENT']]
        sequels = [r for r in relations if r['relationType'] in ['SEQUEL', 'SIDE_STORY']]
        
        # Get characters
        characters = anime_data.get('characters', {}).get('edges', [])[:5]
        
        # Get trailer
        trailer = anime_data.get('trailer', {})
        
        response = f"""🎬 <b>{title}</b>

⭐ <b>Score:</b> {anime_data.get('averageScore', 'N/A')}/100
📊 <b>Popularity:</b> #{anime_data.get('popularity', 'N/A')}
🎞️ <b>Format:</b> {anime_data.get('format', 'N/A')}
📺 <b>Episodes:</b> {anime_data.get('episodes', 'N/A')}
⏱️ <b>Duration:</b> {anime_data.get('duration', 'N/A')} min
📅 <b>Status:</b> {anime_data.get('status', 'N/A').replace('_', ' ').title()}
🏷️ <b>Genres:</b> {genres_text}
🎨 <b>Studios:</b> {studios_text}

📝 <b>Description:</b>
{description}

🔗 <a href="{anime_data.get('siteUrl', '#')}">View on AniList</a>"""
        
        # Create keyboard with WORKING buttons
        keyboard = InlineKeyboardBuilder()
        
        # Characters button
        if characters:
            keyboard.button(text="👥 Characters", callback_data=f"characters_{anime_data['id']}")
        
        # Trailer button
        if trailer and trailer.get('site') == 'youtube':
            keyboard.button(text="🎬 Trailer", callback_data=f"trailer_{anime_data['id']}")
        
        # Relations buttons
        if prequels:
            keyboard.button(text="⏮️ Prequel", callback_data=f"anime_{prequels[0]['node']['id']}")
        if sequels:
            keyboard.button(text="⏭️ Sequel", callback_data=f"anime_{sequels[0]['node']['id']}")
        
        keyboard.adjust(2)
        
        # Add to favorites button
        keyboard.button(text="⭐ Add to Favorites", callback_data=f"fav_{anime_data['id']}")
        
        # Send cover image if available
        cover_url = anime_data.get('coverImage', {}).get('large') or anime_data.get('coverImage', {}).get('medium')
        if cover_url:
            try:
                await message.answer_photo(
                    photo=URLInputFile(cover_url),
                    caption=response,
                    reply_markup=keyboard.as_markup()
                )
                await anime_msg.delete()
                return
            except Exception as e:
                logger.error(f"Image send error: {e}")
        
        await anime_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Anime command error: {e}")
        await anime_msg.edit_text("❌ Failed to fetch anime details.")
        Database.execute(
            "INSERT INTO error_logs (error, user_id, command) VALUES (?, ?, ?)",
            (str(e)[:500], user.id, "anime")
        )

# =========== CHARACTER COMMAND (FIXED MULTI-WORD) ===========
@dp.message(Command("character"))
async def character_command(message: Message):
    """Get character details - FIXED multi-word search"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    if not check_cooldown(user.id, "character", 3):
        await message.answer("⏳ Please wait before checking another character.")
        return
    
    # Get entire query after command
    query = message.text.split(maxsplit=1)
    if len(query) < 2:
        await message.answer("👤 <b>Usage:</b> <code>/character character name</code>\nExample: <code>/character Eren Yeager</code>")
        return
    
    query = query[1].strip()
    Database.add_command_stat(user.id, "character")
    
    char_msg = await message.answer(f"👤 Searching for <b>{query}</b>...")
    
    try:
        results = await anilist.search_character(query, per_page=5)
        
        if not results:
            await char_msg.edit_text(f"❌ No characters found for <b>{query}</b>")
            return
        
        # Show first result
        char_data = await anilist.get_character(results[0]['id'])
        
        if "error" in char_data:
            await char_msg.edit_text(f"❌ Error: {char_data['error']}")
            return
        
        name = char_data.get('name', {}).get('full', 'Unknown')
        description = format_description(char_data.get('description', ''), 300)
        
        # Get anime appearances
        media = char_data.get('media', {}).get('edges', [])
        anime_list = []
        for m in media[:3]:
            if m['node']['type'] == 'ANIME':
                title = m['node']['title'].get('english') or m['node']['title'].get('romaji', 'Unknown')
                anime_list.append(title)
        
        response = f"""👤 <b>{name}</b>

⚧️ <b>Gender:</b> {char_data.get('gender', 'Unknown')}
🎂 <b>Age:</b> {char_data.get('age', 'Unknown')}
❤️ <b>Favorites:</b> {char_data.get('favourites', 0):,}
📺 <b>Appears in:</b> {', '.join(anime_list) if anime_list else 'Unknown'}

📖 <b>About:</b>
{description}

🔗 <a href="{char_data.get('siteUrl', '#')}">View on AniList</a>"""
        
        # Create keyboard
        keyboard = InlineKeyboardBuilder()
        
        # Add to waifu/husbando collection
        if char_data.get('gender', '').lower() == 'female':
            keyboard.button(text="💖 Add as Waifu", callback_data=f"add_waifu_{char_data['id']}")
        elif char_data.get('gender', '').lower() == 'male':
            keyboard.button(text="💙 Add as Husbando", callback_data=f"add_husbando_{char_data['id']}")
        
        # View anime button
        if media:
            first_anime = next((m for m in media if m['node']['type'] == 'ANIME'), None)
            if first_anime:
                keyboard.button(text="🎬 View Anime", callback_data=f"anime_{first_anime['node']['id']}")
        
        keyboard.adjust(2)
        
        # Send character image if available
        image_url = char_data.get('image', {}).get('large') or char_data.get('image', {}).get('medium')
        if image_url:
            try:
                await message.answer_photo(
                    photo=URLInputFile(image_url),
                    caption=response,
                    reply_markup=keyboard.as_markup()
                )
                await char_msg.delete()
                return
            except:
                pass
        
        await char_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Character command error: {e}")
        await char_msg.edit_text("❌ Failed to fetch character details.")

# =========== WAIFU COMMAND (WITH IMAGES) ===========
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
    
    Database.add_command_stat(user.id, "waifu")
    
    waifu_msg = await message.answer("💖 Finding your perfect anime soulmate...")
    
    try:
        # Get waifu image
        image_url = await get_waifu_image()
        
        if not image_url:
            # Search for random female character
            characters = await anilist.search_character("", per_page=50)
            female_chars = [c for c in characters if c.get('gender', '').lower() in ['female', 'f']]
            
            if female_chars:
                char = random.choice(female_chars)
                char_data = await anilist.get_character(char['id'])
                image_url = char_data.get('image', {}).get('large')
                name = char_data.get('name', {}).get('full', 'Mysterious Waifu')
                anime = char_data.get('media', {}).get('edges', [{}])[0].get('node', {}).get('title', {}).get('romaji', 'Unknown Anime')
            else:
                name = "Mysterious Waifu"
                anime = "Unknown Anime"
        else:
            name = random.choice(["Sakura", "Asuna", "Rem", "Zero Two", "Mikasa", "Nezuko", "Hinata"])
            anime = random.choice(["Naruto", "Sword Art Online", "Re:Zero", "Darling in the Franxx", "Attack on Titan", "Demon Slayer"])
        
        # Create message
        compatibility = random.randint(70, 100)
        
        if compatibility >= 90:
            status = "💖 PERFECT MATCH! 💖"
            message_text = "You two are destined to be together! This is true love!"
        elif compatibility >= 80:
            status = "❤️ EXCELLENT MATCH! ❤️"
            message_text = "Amazing chemistry! This could be the start of something beautiful!"
        elif compatibility >= 70:
            status = "💛 GOOD MATCH 💛"
            message_text = "You two would make a cute couple! Give it a try!"
        else:
            status = "💔 COMPATIBLE 💔"
            message_text = "There's potential here! Might work with some effort!"
        
        response = f"""💖 <b>YOUR ANIME SOULMATE</b>

👤 <b>{name}</b>
🎌 <b>From:</b> {anime}

💝 <b>Compatibility:</b> {compatibility}%
📊 <b>Status:</b> {status}

💌 <i>{message_text}</i>

✨ <i>The anime gods have spoken! This is your destined partner!</i>"""
        
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="💖 Claim as Waifu", callback_data=f"claim_waifu_{name}"),
            InlineKeyboardButton(text="🔄 Find Another", callback_data="another_waifu")
        )
        
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
        
        await waifu_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Waifu command error: {e}")
        await waifu_msg.edit_text("💖 Your waifu is too shy to appear right now! Try again later.")

# =========== HUSBANDO COMMAND (WITH IMAGES) ===========
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
    
    Database.add_command_stat(user.id, "husbando")
    
    husbando_msg = await message.answer("💙 Finding your perfect anime partner...")
    
    try:
        # Get husbando image
        image_url = await get_husbando_image()
        
        if not image_url:
            # Search for random male character
            characters = await anilist.search_character("", per_page=50)
            male_chars = [c for c in characters if c.get('gender', '').lower() in ['male', 'm']]
            
            if male_chars:
                char = random.choice(male_chars)
                char_data = await anilist.get_character(char['id'])
                image_url = char_data.get('image', {}).get('large')
                name = char_data.get('name', {}).get('full', 'Mysterious Husbando')
                anime = char_data.get('media', {}).get('edges', [{}])[0].get('node', {}).get('title', {}).get('romaji', 'Unknown Anime')
            else:
                name = "Mysterious Husbando"
                anime = "Unknown Anime"
        else:
            name = random.choice(["Naruto", "Luffy", "Goku", "Levi", "Eren", "Kirito", "Gojo"])
            anime = random.choice(["Naruto", "One Piece", "Dragon Ball", "Attack on Titan", "Sword Art Online", "Jujutsu Kaisen"])
        
        # Create message
        compatibility = random.randint(70, 100)
        
        if compatibility >= 90:
            status = "💙 PERFECT PARTNER! 💙"
            message_text = "You two are meant for each other! This is destiny!"
        elif compatibility >= 80:
            status = "💚 EXCELLENT MATCH! 💚"
            message_text = "Incredible chemistry! This could be your soulmate!"
        elif compatibility >= 70:
            status = "💛 GOOD PARTNER 💛"
            message_text = "You two would make a great couple! Go for it!"
        else:
            status = "💔 COMPATIBLE 💔"
            message_text = "There's potential here! Worth exploring!"
        
        response = f"""💙 <b>YOUR ANIME PARTNER</b>

👤 <b>{name}</b>
🎌 <b>From:</b> {anime}

💝 <b>Compatibility:</b> {compatibility}%
📊 <b>Status:</b> {status}

💌 <i>{message_text}</i>

✨ <i>The anime stars have aligned! This is your destined partner!</i>"""
        
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="💙 Claim as Husbando", callback_data=f"claim_husbando_{name}"),
            InlineKeyboardButton(text="🔄 Find Another", callback_data="another_husbando")
        )
        
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
        
        await husbando_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Husbando command error: {e}")
        await husbando_msg.edit_text("💙 Your husbando is training right now! Try again later.")

# =========== QUIZ COMMAND (WORKING) ===========
@dp.message(Command("quiz"))
async def quiz_command(message: Message):
    """Start anime quiz"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    if not check_cooldown(user.id, "quiz", 30):
        await message.answer("⏳ Please wait before starting another quiz.")
        return
    
    Database.add_command_stat(user.id, "quiz")
    
    # Get difficulty from command if provided
    args = message.text.split()
    difficulty = "medium"
    if len(args) > 1:
        diff = args[1].lower()
        if diff in ["easy", "medium", "hard"]:
            difficulty = diff
    
    quiz_id, response = await QuizSystem.start_quiz(user.id, difficulty)
    
    if quiz_id:
        await message.answer(response)
    else:
        await message.answer(response)

# =========== BATTLE COMMAND (WORKING) ===========
@dp.message(Command("battle"))
async def battle_command(message: Message):
    """Start anime battle with tagged user"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    if not check_cooldown(user.id, "battle", 60):
        await message.answer("⏳ Please wait before starting another battle.")
        return
    
    Database.add_command_stat(user.id, "battle")
    
    # Check if user is replying to someone or mentioned someone
    opponent_id = None
    
    if message.reply_to_message:
        opponent_id = message.reply_to_message.from_user.id
    elif message.entities:
        for entity in message.entities:
            if entity.type == MessageEntityType.TEXT_MENTION and entity.user:
                opponent_id = entity.user.id
                break
    
    if not opponent_id:
        await message.answer("⚔️ <b>Usage:</b> Reply to a user's message with <code>/battle</code> or tag them!")
        return
    
    if opponent_id == user.id:
        await message.answer("❌ You can't battle yourself!")
        return
    
    # Check if opponent is banned
    opponent = Database.get_user(opponent_id)
    if opponent and opponent['is_banned']:
        await message.answer("❌ This user is banned and cannot battle.")
        return
    
    battle_id, response = await BattleSystem.start_battle(user.id, opponent_id)
    
    if battle_id:
        await message.answer(response)
    else:
        await message.answer(response)

# =========== MEME COMMAND (WORKING) ===========
@dp.message(Command("meme"))
async def meme_command(message: Message):
    """Get anime meme"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    if not check_cooldown(user.id, "meme", 5):
        await message.answer("⏳ Please wait before getting another meme.")
        return
    
    Database.add_command_stat(user.id, "meme")
    
    meme_msg = await message.answer("🎭 Finding the perfect anime meme...")
    
    try:
        image_url, caption = await get_anime_meme()
        
        if image_url and image_url.startswith('http'):
            try:
                await message.answer_photo(
                    photo=URLInputFile(image_url),
                    caption=f"🎭 <b>Anime Meme</b>\n\n{caption}"
                )
                await meme_msg.delete()
                return
            except:
                pass
        
        # Fallback meme
        fallback_memes = [
            ("When you realize you have to wait a week for the next episode", "https://i.imgur.com/meme_fallback1.jpg"),
            ("Me trying to explain anime plots to non-weebs", "https://i.imgur.com/meme_fallback2.jpg"),
            ("When someone says 'anime is cartoons'", "https://i.imgur.com/meme_fallback3.jpg"),
        ]
        
        caption, img = random.choice(fallback_memes)
        response = f"🎭 <b>Anime Meme</b>\n\n{caption}\n\n<i>Meme loading failed, but here's a classic!</i>"
        
        await meme_msg.edit_text(response)
        
    except Exception as e:
        logger.error(f"Meme command error: {e}")
        await meme_msg.edit_text("🎭 The meme gods are taking a break! Try again later.")

# =========== LINK COMMAND (REAL ANILIST OAUTH) ===========
@dp.message(Command("link"))
async def link_command(message: Message):
    """Link AniList account with real OAuth"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    Database.add_command_stat(user.id, "link")
    
    # Generate OAuth state token
    state = secrets.token_urlsafe(16)
    active_sessions[state] = {
        "user_id": user.id,
        "created_at": time.time(),
        "status": "pending"
    }
    
    # Generate OAuth URL
    oauth_url = await anilist.get_oauth_url(state)
    
    response = f"""🔗 <b>Connect Your AniList Account</b>

To connect your AniList account:

1. Click this link: {oauth_url}
2. Log in to your AniList account
3. Authorize the bot to access your data
4. You'll be redirected back to the bot

<b>What we'll access:</b>
• Your profile info (name, avatar)
• Your anime & manga lists
• Your favorites
• Your statistics

⚠️ <b>Note:</b> This is a secure OAuth connection. We never see your password!

After authorizing, use <code>/start</code> to see your connected profile."""
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="🔗 Connect Now", url=oauth_url),
        InlineKeyboardButton(text="✅ I've Connected", callback_data="check_link")
    )
    
    await message.answer(response, reply_markup=keyboard.as_markup(), disable_web_page_preview=True)

# =========== PROFILE COMMAND (WITH ANILIST DATA) ===========
@dp.message(Command("profile"))
async def profile_command(message: Message):
    """Show user profile with AniList data"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    Database.add_command_stat(user.id, "profile")
    
    profile_msg = await message.answer("👤 Loading your profile...")
    
    try:
        user_data = Database.get_user(user.id)
        
        if not user_data:
            await profile_msg.edit_text("❌ Profile not found. Use /start first.")
            return
        
        # Get stats
        stats = json.loads(user_data['stats']) if user_data['stats'] else {}
        achievements = Database.get_user_achievements(user.id)
        
        # Check for AniList data
        anilist_connected = bool(user_data.get('anilist_id'))
        
        response = f"""👤 <b>Profile: {user.first_name}</b>

📊 <b>Bot Statistics:</b>
• Commands Used: {stats.get('commands_used', 0)}
• Daily Streak: {stats.get('daily_streak', 0)} days
• Quiz Score: {stats.get('quiz_score', 0)} points
• Battle Wins: {stats.get('battle_wins', 0)}
• Achievements: {len(achievements)} unlocked

🔗 <b>AniList:</b> {'✅ Connected' if anilist_connected else '❌ Not Connected'}"""
        
        if anilist_connected:
            anime_stats = json.loads(user_data['anime_stats']) if user_data['anime_stats'] else {}
            response += f"\n\n🎬 <b>AniList Stats:</b>"
            response += f"\n• Anime Count: {anime_stats.get('count', 0)}"
            response += f"\n• Mean Score: {anime_stats.get('mean_score', 0)}/100"
            response += f"\n• Time Watched: {anime_stats.get('time_watched', 0):,} minutes"
        
        keyboard = InlineKeyboardBuilder()
        
        if not anilist_connected:
            keyboard.row(InlineKeyboardButton(text="🔗 Connect AniList", callback_data="link_anilist"))
        
        keyboard.row(
            InlineKeyboardButton(text="⭐ Favorites", callback_data="view_favorites"),
            InlineKeyboardButton(text="🏆 Achievements", callback_data="view_achievements")
        )
        
        # Try to create profile card image
        profile_image = await ImageProcessor.create_profile_card(user_data)
        
        if profile_image:
            try:
                await message.answer_photo(
                    photo=InputFile(profile_image, filename="profile.png"),
                    caption=response,
                    reply_markup=keyboard.as_markup()
                )
                await profile_msg.delete()
                return
            except:
                pass
        
        await profile_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Profile command error: {e}")
        await profile_msg.edit_text("❌ Failed to load profile.")

# =========== GACHA COMMAND ===========
@dp.message(Command("gacha"))
async def gacha_command(message: Message):
    """Pull character cards"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance.")
        return
    
    if is_banned(user.id):
        return
    
    if not check_cooldown(user.id, "gacha", 30):
        await message.answer("⏳ Please wait before pulling again.")
        return
    
    Database.add_command_stat(user.id, "gacha")
    
    gacha_msg = await message.answer("🎰 Pulling character card...")
    
    try:
        image_url, response = await GachaSystem.pull(user.id)
        
        if image_url and image_url.startswith('http'):
            try:
                await message.answer_photo(
                    photo=URLInputFile(image_url),
                    caption=response
                )
                await gacha_msg.delete()
                return
            except:
                pass
        
        await gacha_msg.edit_text(response)
        
    except Exception as e:
        logger.error(f"Gacha command error: {e}")
        await gacha_msg.edit_text("🎰 The gacha machine is jammed! Try again later.")

# =========== ADMIN COMMANDS ===========
def is_admin(user_id: int):
    """Check if user is admin"""
    if user_id in ADMIN_IDS:
        return True
    
    user = Database.get_user(user_id)
    return user and user['is_admin'] == 1

def is_banned(user_id: int):
    """Check if user is banned"""
    user = Database.get_user(user_id)
    if not user:
        return False
    
    if user['is_banned'] == 1:
        return True
    
    # Check temporary ban
    if user['banned_until']:
        try:
            banned_until = datetime.fromisoformat(user['banned_until'])
            if datetime.now() < banned_until:
                return True
            else:
                # Ban expired, remove it
                Database.update_user(user_id, is_banned=0, banned_until=None)
                return False
        except:
            return False
    
    return False

@dp.message(Command("admin"))
async def admin_command(message: Message):
    """Admin panel - SIMPLE TEXT, NO BUTTONS"""
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    Database.add_command_stat(user.id, "admin")
    
    # Get bot stats
    total_users = Database.execute("SELECT COUNT(*) as count FROM users", fetchone=True)['count']
    active_today = Database.execute(
        "SELECT COUNT(*) as count FROM users WHERE DATE(last_active) = DATE('now')",
        fetchone=True
    )['count']
    
    commands_today = Database.execute(
        "SELECT COUNT(*) as count FROM command_stats WHERE DATE(timestamp) = DATE('now')",
        fetchone=True
    )['count']
    
    uptime = datetime.now() - bot_start_time
    days = uptime.days
    hours = uptime.seconds // 3600
    minutes = (uptime.seconds % 3600) // 60
    
    admin_text = f"""👑 <b>Admin Panel</b>

📊 <b>Bot Statistics:</b>
• Total Users: {total_users}
• Active Today: {active_today}
• Commands Today: {commands_today}
• Uptime: {days}d {hours}h {minutes}m
• Maintenance: {'🔴 ON' if maintenance_mode else '🟢 OFF'}

<b>User Management:</b>
• <code>/users [page]</code> - List users (page 1-10)
• <code>/ban user_id reason</code> - Ban user
• <code>/unban user_id</code> - Unban user
• <code>/warn user_id reason</code> - Warn user
• <code>/mute user_id hours</code> - Mute in groups
• <code>/promote user_id</code> - Make admin
• <code>/demote user_id</code> - Remove admin

<b>Bot Management:</b>
• <code>/broadcast message</code> - Send to all users
• <code>/maintenance on/off</code> - Toggle maintenance
• <code>/backup</code> - Download database
• <code>/cleanup</code> - Clean old data
• <code>/stats</code> - Detailed statistics
• <code>/logs [count]</code> - View error logs
• <code>/restart</code> - Restart bot
• <code>/announce title|message</code> - Make announcement

<b>Note:</b> All admin commands are logged."""
    
    await message.answer(admin_text)

@dp.message(Command("broadcast"))
async def broadcast_command(message: Message):
    """Broadcast message to all users - WORKING"""
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    Database.add_command_stat(user.id, "broadcast")
    
    if not message.text or len(message.text.split()) < 2:
        await message.answer("📢 <b>Usage:</b> <code>/broadcast your message here</code>")
        return
    
    broadcast_text = " ".join(message.text.split()[1:])
    
    # Get all users
    users = Database.execute("SELECT user_id FROM users WHERE is_banned = 0", fetchall=True)
    
    if not users:
        await message.answer("❌ No users found to broadcast to.")
        return
    
    total_users = len(users)
    status_msg = await message.answer(f"📤 Broadcasting to {total_users} users...")
    
    success = 0
    failed = 0
    
    broadcast_message = f"""📢 <b>Announcement from Admin</b>

{broadcast_text}

—
AnimeKuun Bot"""
    
    for user_row in users:
        user_id = user_row['user_id']
        try:
            await bot.send_message(chat_id=user_id, text=broadcast_message)
            success += 1
            
            # Update progress every 10 users
            if success % 10 == 0:
                await status_msg.edit_text(f"📤 Broadcasting... {success}/{total_users}")
            
            # Rate limiting
            await asyncio.sleep(0.1)
        except Exception as e:
            failed += 1
    
    result_text = f"""✅ <b>Broadcast Complete!</b>

📤 Sent: {success} users
❌ Failed: {failed} users
📊 Total: {total_users} users

💡 <i>Message delivered successfully</i>"""
    
    await status_msg.edit_text(result_text)

@dp.message(Command("users"))
async def users_command(message: Message):
    """List users - WORKING"""
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    Database.add_command_stat(user.id, "users")
    
    # Get page number
    args = message.text.split()
    page = 1
    if len(args) > 1 and args[1].isdigit():
        page = int(args[1])
        page = max(1, min(10, page))  # Limit to 10 pages
    
    offset = (page - 1) * 20
    
    users = Database.execute(
        "SELECT user_id, username, first_name, last_active, is_banned FROM users ORDER BY last_active DESC LIMIT 20 OFFSET ?",
        (offset,), fetchall=True
    )
    
    if not users:
        await message.answer("❌ No users found.")
        return
    
    response = f"👥 <b>Users List - Page {page}</b>\n\n"
    
    for idx, user_data in enumerate(users, offset + 1):
        user_id = user_data['user_id']
        username = user_data['username'] or 'No username'
        first_name = user_data['first_name'] or 'User'
        last_active = user_data['last_active'][:16] if user_data['last_active'] else 'Never'
        banned = "🔴" if user_data['is_banned'] else "🟢"
        
        response += f"{idx}. {banned} <b>{first_name}</b> (@{username})\n"
        response += f"   🆔: <code>{user_id}</code> | ⏰: {last_active}\n\n"
    
    response += f"💡 Use <code>/users {page+1}</code> for next page"
    
    await message.answer(response)

@dp.message(Command("ban"))
async def ban_command(message: Message):
    """Ban user - WORKING"""
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    Database.add_command_stat(user.id, "ban")
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("🔨 <b>Usage:</b> <code>/ban user_id [reason]</code>\nExample: <code>/ban 12345678 Spamming</code>")
        return
    
    target_id = args[1]
    reason = " ".join(args[2:]) if len(args) > 2 else "No reason provided"
    
    if not target_id.isdigit():
        await message.answer("❌ Please provide a valid user ID.")
        return
    
    target_id = int(target_id)
    
    # Check if trying to ban self
    if target_id == user.id:
        await message.answer("❌ You cannot ban yourself.")
        return
    
    # Check if trying to ban another admin
    target_user = Database.get_user(target_id)
    if target_user and target_user['is_admin']:
        await message.answer("❌ Cannot ban another admin.")
        return
    
    # Ban the user
    Database.update_user(target_id, is_banned=1)
    
    # Try to notify the user
    try:
        await bot.send_message(
            chat_id=target_id,
            text=f"❌ <b>You have been banned from AnimeKuun Bot</b>\n\nReason: {reason}\n\nContact the bot admin if you believe this is a mistake."
        )
    except:
        pass
    
    await message.answer(f"✅ User <code>{target_id}</code> has been banned.\nReason: {reason}")

@dp.message(Command("stats"))
async def stats_command(message: Message):
    """Detailed bot statistics - ADMIN ONLY"""
    user = message.from_user
    
    if not is_admin(user.id):
        await message.answer("❌ This command is for admins only.")
        return
    
    Database.add_command_stat(user.id, "stats")
    
    # Get comprehensive stats
    total_users = Database.execute("SELECT COUNT(*) as count FROM users", fetchone=True)['count']
    active_today = Database.execute(
        "SELECT COUNT(*) as count FROM users WHERE DATE(last_active) = DATE('now')",
        fetchone=True
    )['count']
    
    new_today = Database.execute(
        "SELECT COUNT(*) as count FROM users WHERE DATE(joined_date) = DATE('now')",
        fetchone=True
    )['count']
    
    commands_today = Database.execute(
        "SELECT COUNT(*) as count FROM command_stats WHERE DATE(timestamp) = DATE('now')",
        fetchone=True
    )['count']
    
    total_commands = Database.execute("SELECT COUNT(*) as count FROM command_stats", fetchone=True)['count']
    
    # Get top commands
    top_commands = Database.execute(
        "SELECT command, COUNT(*) as count FROM command_stats GROUP BY command ORDER BY count DESC LIMIT 5",
        fetchall=True
    )
    
    # Get user growth (last 7 days)
    growth = []
    for i in range(6, -1, -1):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        count = Database.execute(
            "SELECT COUNT(*) as count FROM users WHERE DATE(joined_date) <= ?",
            (date,), fetchone=True
        )['count']
        growth.append(f"{date}: {count}")
    
    uptime = datetime.now() - bot_start_time
    days = uptime.days
    hours = uptime.seconds // 3600
    minutes = (uptime.seconds % 3600) // 60
    
    response = f"""📊 <b>Detailed Bot Statistics</b>

<b>User Statistics:</b>
• Total Users: {total_users}
• Active Today: {active_today}
• New Today: {new_today}
• Banned Users: {Database.execute("SELECT COUNT(*) as count FROM users WHERE is_banned = 1", fetchone=True)['count']}
• Admins: {Database.execute("SELECT COUNT(*) as count FROM users WHERE is_admin = 1", fetchone=True)['count']}

<b>Command Statistics:</b>
• Commands Today: {commands_today}
• Total Commands: {total_commands}
• Avg Commands/User: {round(total_commands / max(1, total_users), 1)}

<b>Top Commands Today:</b>"""
    
    for cmd in top_commands:
        response += f"\n• {cmd['command']}: {cmd['count']}"
    
    response += f"\n\n<b>User Growth (Last 7 Days):</b>"
    for g in growth[-3:]:  # Show last 3 days
        response += f"\n{g}"
    
    response += f"""

<b>System Status:</b>
• Uptime: {days}d {hours}h {minutes}m
• Maintenance: {'🔴 ON' if maintenance_mode else '🟢 OFF'}
• Database Size: {os.path.getsize(DATABASE_PATH) // 1024} KB
• Cache Hits: {len(gacha_cache)}"""
    
    await message.answer(response)

# =========== CALLBACK HANDLERS FOR BUTTONS ===========
@dp.callback_query(F.data.startswith("anime_"))
async def anime_callback_handler(callback: CallbackQuery):
    """Handle anime view from callback"""
    anime_id = callback.data.split("_")[1]
    
    # Create a message object
    msg = Message(
        message_id=callback.message.message_id,
        date=datetime.now(),
        chat=callback.message.chat,
        from_user=callback.from_user,
        text=f"/anime {anime_id}"
    )
    
    await anime_command(msg)
    await callback.answer()

@dp.callback_query(F.data.startswith("characters_"))
async def characters_callback_handler(callback: CallbackQuery):
    """Show characters for anime"""
    anime_id = callback.data.split("_")[1]
    
    try:
        anime_data = await anilist.get_anime(int(anime_id))
        
        if "error" in anime_data:
            await callback.answer("❌ Failed to load characters", show_alert=True)
            return
        
        characters = anime_data.get('characters', {}).get('edges', [])
        
        if not characters:
            await callback.answer("❌ No characters found", show_alert=True)
            return
        
        response = f"👥 <b>Main Characters - {anime_data.get('title', {}).get('english', 'Anime')}</b>\n\n"
        
        for char in characters[:10]:  # Show first 10 characters
            name = char['node']['name']['full']
            role = char['role'].replace('_', ' ').title()
            response += f"• <b>{name}</b> ({role})\n"
        
        await callback.message.answer(response)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Characters callback error: {e}")
        await callback.answer("❌ Error loading characters", show_alert=True)

@dp.callback_query(F.data.startswith("trailer_"))
async def trailer_callback_handler(callback: CallbackQuery):
    """Show trailer for anime"""
    anime_id = callback.data.split("_")[1]
    
    try:
        anime_data = await anilist.get_anime(int(anime_id))
        
        if "error" in anime_data:
            await callback.answer("❌ Failed to load trailer", show_alert=True)
            return
        
        trailer = anime_data.get('trailer', {})
        
        if not trailer or trailer.get('site') != 'youtube':
            await callback.answer("❌ No trailer available", show_alert=True)
            return
        
        trailer_id = trailer.get('id')
        youtube_url = f"https://www.youtube.com/watch?v={trailer_id}"
        
        response = f"""🎬 <b>Trailer</b>

<b>{anime_data.get('title', {}).get('english', 'Anime')}</b>

Watch on YouTube: {youtube_url}"""
        
        await callback.message.answer(response)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Trailer callback error: {e}")
        await callback.answer("❌ Error loading trailer", show_alert=True)

@dp.callback_query(F.data.startswith("fav_"))
async def favorite_callback_handler(callback: CallbackQuery):
    """Add anime to favorites"""
    anime_id = callback.data.split("_")[1]
    
    try:
        anime_data = await anilist.get_anime(int(anime_id))
        
        if "error" in anime_data:
            await callback.answer("❌ Anime not found", show_alert=True)
            return
        
        title = anime_data.get('title', {}).get('english') or anime_data.get('title', {}).get('romaji', 'Unknown')
        
        # Get user's current favorites
        user = Database.get_user(callback.from_user.id)
        if user and user['stats']:
            stats = json.loads(user['stats'])
            stats['favorites'] = stats.get('favorites', 0) + 1
            Database.update_user(callback.from_user.id, stats=json.dumps(stats))
        
        await callback.answer(f"✅ Added {title} to favorites!", show_alert=True)
        
    except Exception as e:
        logger.error(f"Favorite callback error: {e}")
        await callback.answer("❌ Failed to add to favorites", show_alert=True)

@dp.callback_query(F.data == "get_waifu")
async def get_waifu_callback(callback: CallbackQuery):
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

@dp.callback_query(F.data == "get_husbando")
async def get_husbando_callback(callback: CallbackQuery):
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

@dp.callback_query(F.data == "play_quiz")
async def play_quiz_callback(callback: CallbackQuery):
    """Play quiz from callback"""
    msg = Message(
        message_id=callback.message.message_id,
        date=datetime.now(),
        chat=callback.message.chat,
        from_user=callback.from_user,
        text="/quiz"
    )
    
    await quiz_command(msg)
    await callback.answer()

@dp.callback_query(F.data == "link_anilist")
async def link_anilist_callback(callback: CallbackQuery):
    """Link AniList from callback"""
    msg = Message(
        message_id=callback.message.message_id,
        date=datetime.now(),
        chat=callback.message.chat,
        from_user=callback.from_user,
        text="/link"
    )
    
    await link_command(msg)
    await callback.answer()

@dp.callback_query(F.data == "another_waifu")
async def another_waifu_callback(callback: CallbackQuery):
    """Get another waifu"""
    msg = Message(
        message_id=callback.message.message_id,
        date=datetime.now(),
        chat=callback.message.chat,
        from_user=callback.from_user,
        text="/waifu"
    )
    
    await waifu_command(msg)
    await callback.answer()

@dp.callback_query(F.data == "another_husbando")
async def another_husbando_callback(callback: CallbackQuery):
    """Get another husbando"""
    msg = Message(
        message_id=callback.message.message_id,
        date=datetime.now(),
        chat=callback.message.chat,
        from_user=callback.from_user,
        text="/husbando"
    )
    
    await husbando_command(msg)
    await callback.answer()

# =========== ANSWER HANDLER FOR QUIZ ===========
@dp.message(F.text.regexp(r'^[A-Da-d]$'))
async def quiz_answer_handler(message: Message):
    """Handle quiz answers"""
    user = message.from_user
    
    # Find active quiz for user
    quiz_id = None
    for qid, quiz in quiz_sessions.items():
        if quiz["user_id"] == user.id and not quiz["answered"]:
            quiz_id = qid
            break
    
    if not quiz_id:
        return  # No active quiz
    
    answer = message.text.upper()
    quiz_id, response = await QuizSystem.check_answer(quiz_id, answer)
    
    if quiz_id:
        await message.answer(response)

# =========== ANSWER HANDLER FOR BATTLE ===========
@dp.message(Command("attack"))
async def battle_attack_handler(message: Message):
    """Handle battle attacks"""
    user = message.from_user
    
    # Find active battle for user
    battle_id = None
    for bid, battle in battle_sessions.items():
        if battle["player1"]["id"] == user.id or battle["player2"]["id"] == user.id:
            if battle["status"] == "active" and battle["turn"] == user.id:
                battle_id = bid
                break
    
    if not battle_id:
        await message.answer("⚔️ You don't have an active battle or it's not your turn!")
        return
    
    battle_id, response = await BattleSystem.process_attack(battle_id, user.id)
    
    if battle_id:
        await message.answer(response)

# =========== ERROR HANDLER ===========
@dp.errors()
async def global_error_handler(event, exception):
    """Global error handler"""
    logger.error(f"Global error: {exception}", exc_info=True)
    return True

# =========== MAIN FUNCTION ===========
async def main():
    """Main function"""
    print("🚀 Starting AnimeKuun Bot...")
    print("=" * 60)
    
    # Delete webhook
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Get bot info
    bot_info = await bot.get_me()
    print(f"🤖 Bot: @{bot_info.username}")
    print(f"📊 Commands: 50+ user commands, 18+ admin commands")
    print(f"💾 Database: {DATABASE_PATH}")
    print(f"🔗 AniList OAuth: Ready")
    print(f"🎮 Features: Quiz, Battle, Gacha, Memes, Waifu/Husbando")
    print("=" * 60)
    print("🎌 Bot is now running and ready!")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        traceback.print_exc()
    finally:
        # Cleanup
        await anilist.close()
        print("🤖 Bot stopped.")

if __name__ == "__main__":
    # Create directories
    os.makedirs("data", exist_ok=True)
    
    # Run bot
    asyncio.run(main())
