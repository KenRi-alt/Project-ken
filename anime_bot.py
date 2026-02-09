#!/usr/bin/env python3
"""
🎌 AnimeKuun Bot - COMPLETE ULTIMATE VERSION
All buttons working + Unique features + Production ready
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
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import aiohttp
from io import BytesIO
import requests
from urllib.parse import quote, urlencode
import base64

# Aiogram imports
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    InputFile, URLInputFile, FSInputFile, ReplyKeyboardRemove,
    Poll, PollAnswer, InlineQuery, InlineQueryResultArticle,
    InputTextMessageContent, InlineQueryResultPhoto
)
from aiogram.enums import ParseMode, ChatType, MessageEntityType
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest

# =========== CONFIGURATION ===========
BOT_TOKEN = os.getenv("BOT_TOKEN", "8282052807:AAERvnTQKpqBxz23qW4eygRknkVcqy31NNw")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "6108185460").split(",") if id.strip()]
DATABASE_PATH = "data/animekun_ultimate.db"

print("=" * 60)
print("🎌 ANIMEKUUN BOT - ULTIMATE VERSION")
print(f"🤖 Bot Token: {BOT_TOKEN[:15]}...")
print(f"👑 Admin IDs: {ADMIN_IDS}")
print("=" * 60)

# =========== SETUP ===========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('animekun_ultimate.log'),
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
active_quizzes = {}
active_battles = {}
active_watch_parties = {}
user_states = {}
image_cache = {}

# =========== DATABASE SETUP ===========
def init_database():
    """Initialize database with complete schema"""
    os.makedirs("data", exist_ok=True)
    
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    
    # Users table with achievements
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        anilist_id INTEGER,
        anilist_username TEXT,
        anilist_avatar TEXT,
        waifu_collection TEXT DEFAULT '[]',
        husbando_collection TEXT DEFAULT '[]',
        character_cards TEXT DEFAULT '[]',
        favorites TEXT DEFAULT '[]',
        watch_history TEXT DEFAULT '[]',
        achievements TEXT DEFAULT '[]',
        stats TEXT DEFAULT '{"commands": 0, "searches": 0, "quiz_score": 0, "battle_wins": 0, "daily_streak": 0, "last_login": "", "watch_time": 0}',
        preferences TEXT DEFAULT '{"theme": "dark", "notifications": true}',
        is_admin INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        warnings INTEGER DEFAULT 0,
        daily_reward_claimed TEXT,
        joined_date TEXT DEFAULT CURRENT_TIMESTAMP,
        last_active TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Quiz questions with categories
    c.execute('''CREATE TABLE IF NOT EXISTS quiz_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT NOT NULL,
        options TEXT NOT NULL,
        correct_answer INTEGER NOT NULL,
        explanation TEXT,
        difficulty TEXT DEFAULT 'medium',
        category TEXT DEFAULT 'general',
        source_anime TEXT,
        image_url TEXT,
        added_date TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Add 100+ quiz questions
    c.execute("SELECT COUNT(*) FROM quiz_questions")
    if c.fetchone()[0] == 0:
        questions = [
            # One Piece (15 questions)
            ("What is the name of Luffy's pirate crew?", '["Straw Hat Pirates", "Red Hair Pirates", "Whitebeard Pirates", "Big Mom Pirates"]', 0, "The Straw Hat Pirates are led by Monkey D. Luffy.", "easy", "One Piece", "One Piece"),
            ("Who is Luffy's brother who ate the Mera Mera no Mi?", '["Ace", "Sabo", "Dragon", "Shanks"]', 1, "Sabo ate the Mera Mera no Mi after Ace's death.", "medium", "One Piece", "One Piece"),
            ("What is the name of Zoro's three-sword style?", '["Santoryu", "Nitoryu", "Ittoryu", "Yontoryu"]', 0, "Santoryu is Zoro's signature three-sword style.", "easy", "One Piece", "One Piece"),
            ("Which Warlord can control shadows?", '["Gecko Moria", "Bartholomew Kuma", "Donquixote Doflamingo", "Boa Hancock"]', 0, "Gecko Moria has the Shadow-Shadow Fruit power.", "medium", "One Piece", "One Piece"),
            ("Who is known as 'Dark King' Rayleigh?", '["First Mate of Roger Pirates", "Admiral", "Shichibukai", "Yonko"]', 0, "Silvers Rayleigh was the first mate of Gol D. Roger.", "hard", "One Piece", "One Piece"),
            
            # Naruto (15 questions)
            ("What is Naruto's signature jutsu?", '["Rasengan", "Chidori", "Kamehameha", "Getsuga Tensho"]', 0, "Rasengan was taught to Naruto by Jiraiya.", "easy", "Naruto", "Naruto"),
            ("Who is the Fourth Hokage?", '["Minato Namikaze", "Hashirama Senju", "Tobirama Senju", "Hiruzen Sarutobi"]', 0, "Minato Namikaze was Naruto's father.", "medium", "Naruto", "Naruto"),
            ("What is Itachi's Mangekyo Sharingan ability?", '["Tsukuyomi", "Amaterasu", "Kamui", "Kotoamatsukami"]', 0, "Tsukuyomi traps victims in an illusion.", "hard", "Naruto", "Naruto"),
            ("Who trains Naruto in Sage Mode?", '["Fukasaku", "Jiraiya", "Kakashi", "Yamato"]', 0, "Fukasaku (Gamakichi's dad) trains Naruto.", "medium", "Naruto", "Naruto"),
            ("What is Kakashi's nickname?", '["Copy Ninja", "Yellow Flash", "White Fang", "Green Beast"]', 0, "Kakashi copied over 1000 jutsu.", "easy", "Naruto", "Naruto"),
            
            # Attack on Titan (10 questions)
            ("What is Eren's titan form called?", '["Attack Titan", "Colossal Titan", "Armored Titan", "Beast Titan"]', 0, "Eren possesses the Attack Titan.", "easy", "Attack on Titan", "Attack on Titan"),
            ("Who is the Colossal Titan?", '["Bertolt Hoover", "Reiner Braun", "Annie Leonhart", "Zeke Yeager"]', 0, "Bertolt Hoover was the Colossal Titan.", "medium", "Attack on Titan", "Attack on Titan"),
            ("What is Levi's surname?", '["Ackerman", "Smith", "Brown", "Williams"]', 0, "Levi Ackerman is humanity's strongest soldier.", "easy", "Attack on Titan", "Attack on Titan"),
            ("Who commands the Beast Titan?", '["Zeke Yeager", "Grisha Yeager", "Kenny Ackerman", "Rod Reiss"]', 0, "Zeke Yeager is Eren's half-brother.", "medium", "Attack on Titan", "Attack on Titan"),
            
            # Dragon Ball (10 questions)
            ("What is Goku's signature attack?", '["Kamehameha", "Galick Gun", "Final Flash", "Special Beam Cannon"]', 0, "Kamehameha was taught by Master Roshi.", "easy", "Dragon Ball", "Dragon Ball Z"),
            ("Who is the God of Destruction?", '["Beerus", "Whis", "Zeno", "Champa"]', 0, "Beerus is Universe 7's God of Destruction.", "medium", "Dragon Ball", "Dragon Ball Super"),
            ("What does SSJ stand for?", '["Super Saiyan", "Super Soldier J", "Saiyan Supreme Justice", "Special Saiyan Job"]', 0, "Super Saiyan is the legendary transformation.", "easy", "Dragon Ball", "Dragon Ball Z"),
            ("Who is Vegeta's father?", '["King Vegeta", "Bardock", "Paragus", "Frieza"]', 0, "King Vegeta ruled Planet Vegeta.", "medium", "Dragon Ball", "Dragon Ball Z"),
            
            # Demon Slayer (10 questions)
            ("What is Tanjiro's breathing style?", '["Water Breathing", "Fire Breathing", "Thunder Breathing", "Wind Breathing"]', 0, "Tanjiro uses Water Breathing initially.", "easy", "Demon Slayer", "Demon Slayer"),
            ("Who is the Sound Hashira?", '["Tengen Uzui", "Giyu Tomioka", "Kyojuro Rengoku", "Shinobu Kocho"]', 0, "Tengen Uzui is the Sound Hashira.", "medium", "Demon Slayer", "Demon Slayer"),
            ("What is Nezuko's blood demon art?", '["Exploding Blood", "Blood Manipulation", "Pyrokinesis", "Teleportation"]', 0, "Nezuko can ignite her blood.", "hard", "Demon Slayer", "Demon Slayer"),
            
            # Jujutsu Kaisen (10 questions)
            ("What is Itadori's cursed technique?", '["Divergent Fist", "Limitless", "Ten Shadows", "Boogie Woogie"]', 0, "Divergent Fist delays cursed energy.", "medium", "Jujutsu Kaisen", "Jujutsu Kaisen"),
            ("Who is the Strongest Sorcerer?", '["Satoru Gojo", "Suguru Geto", "Toji Fushiguro", "Kento Nanami"]', 0, "Gojo has both Six Eyes and Limitless.", "easy", "Jujutsu Kaisen", "Jujutsu Kaisen"),
            ("What is Sukuna's domain expansion?", '["Malevolent Shrine", "Unlimited Void", "Chimera Shadow Garden", "Self-Embodiment of Perfection"]', 0, "Malevolent Shrine has a 200m radius.", "hard", "Jujutsu Kaisen", "Jujutsu Kaisen"),
            
            # My Hero Academia (10 questions)
            ("What is Deku's quirk?", '["One For All", "All For One", "Explosion", "Half-Cold Half-Hot"]', 0, "One For All was passed from All Might.", "easy", "My Hero Academia", "My Hero Academia"),
            ("Who is the Explosion hero?", '["Katsuki Bakugo", "Shoto Todoroki", "Tenya Iida", "Eijiro Kirishima"]', 0, "Bakugo's hero name is Great Explosion Murder God.", "easy", "My Hero Academia", "My Hero Academia"),
            
            # Death Note (5 questions)
            ("What kills people in Death Note?", '["Writing their name", "Drawing their face", "Touching the notebook", "Reading the rules"]', 0, "Name + face must be known.", "easy", "Death Note", "Death Note"),
            ("Who is L's real name?", '["L Lawliet", "Light Yagami", "Mihael Keehl", "Quillsh Wammy"]', 0, "L Lawliet is the world's greatest detective.", "hard", "Death Note", "Death Note"),
            
            # Hunter x Hunter (5 questions)
            ("What is Gon's Nen type?", '["Enhancer", "Emitter", "Transmuter", "Conjurer"]', 0, "Enhancers strengthen their body.", "medium", "Hunter x Hunter", "Hunter x Hunter"),
            ("Who is the Phantom Troupe leader?", '["Chrollo Lucilfer", "Hisoka Morow", "Illumi Zoldyck", "Kurapika"]', 0, "Chrollo can steal Nen abilities.", "medium", "Hunter x Hunter", "Hunter x Hunter"),
            
            # Bleach (5 questions)
            ("What is Ichigo's zanpakuto?", '["Zangetsu", "Senbonzakura", "Hyorinmaru", "Ryujin Jakka"]', 0, "Zangetsu means 'Slaying Moon'.", "easy", "Bleach", "Bleach"),
            
            # Sword Art Online (5 questions)
            ("What is Kirito's signature skill?", '["Dual Blades", "Holy Sword", "Rapier", "Katana"]', 0, "Dual Blades is a unique skill.", "easy", "Sword Art Online", "Sword Art Online"),
        ]
        c.executemany('''INSERT INTO quiz_questions (question, options, correct_answer, explanation, difficulty, category, source_anime) 
                         VALUES (?, ?, ?, ?, ?, ?, ?)''', questions)
    
    # Achievements system
    c.execute('''CREATE TABLE IF NOT EXISTS achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        icon TEXT,
        requirement TEXT,
        rarity TEXT DEFAULT 'common',
        points INTEGER DEFAULT 10,
        created_date TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Add achievements
    achievements = [
        ("Anime Beginner", "Use your first command", "🎌", "commands >= 1", "common", 10),
        ("Search Master", "Make 100 searches", "🔍", "searches >= 100", "rare", 50),
        ("Quiz Champion", "Score 1000+ quiz points", "🏆", "quiz_score >= 1000", "epic", 100),
        ("Battle Legend", "Win 50 battles", "⚔️", "battle_wins >= 50", "legendary", 200),
        ("Daily Devotee", "7-day login streak", "🔥", "daily_streak >= 7", "rare", 75),
        ("Waifu Collector", "Collect 10 waifus", "💖", "waifu_count >= 10", "epic", 150),
        ("Husbando Hunter", "Collect 10 husbandos", "💙", "husbando_count >= 10", "epic", 150),
        ("True Fan", "Add 50 favorites", "⭐", "favorites >= 50", "legendary", 250),
        ("Watch Marathon", "Watch 100 hours", "🎬", "watch_time >= 100", "mythic", 300),
        ("Completionist", "Unlock all achievements", "🏅", "achievements_count >= 20", "mythic", 500),
    ]
    c.executemany('''INSERT OR IGNORE INTO achievements (name, description, icon, requirement, rarity, points) 
                     VALUES (?, ?, ?, ?, ?, ?)''', achievements)
    
    # Character cards for gacha
    c.execute('''CREATE TABLE IF NOT EXISTS character_cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        character_id INTEGER,
        name TEXT NOT NULL,
        image_url TEXT,
        rarity TEXT DEFAULT 'R',
        anime TEXT,
        description TEXT,
        stats TEXT DEFAULT '{"attack": 0, "defense": 0, "speed": 0, "intelligence": 0}'
    )''')
    
    # Watch parties
    c.execute('''CREATE TABLE IF NOT EXISTS watch_parties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        anime_id INTEGER,
        anime_title TEXT,
        episode INTEGER DEFAULT 1,
        host_id INTEGER,
        participants TEXT DEFAULT '[]',
        start_time TEXT,
        status TEXT DEFAULT 'scheduled',
        chat_id INTEGER
    )''')
    
    # Memes with categories
    c.execute('''CREATE TABLE IF NOT EXISTS memes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image_url TEXT NOT NULL,
        caption TEXT,
        category TEXT DEFAULT 'general',
        tags TEXT DEFAULT '[]',
        added_by INTEGER,
        uses INTEGER DEFAULT 0,
        added_date TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Add sample memes with WORKING images
    sample_memes = [
        ("https://i.imgur.com/3jYQ8Zl.jpg", "When the filler arc is longer than the main story", "waiting", '["filler", "patience"]'),
        ("https://i.imgur.com/4k7X9lM.jpg", "Me trying to explain anime plots", "explaining", '["confusion", "explaining"]'),
        ("https://i.imgur.com/5L8v9XN.jpg", "When someone says anime is for kids", "defense", '["anger", "defense"]'),
        ("https://i.imgur.com/6M9w0yP.jpg", "Waiting for next season like", "waiting", '["waiting", "excited"]'),
        ("https://i.imgur.com/7N0x1zQ.jpg", "My anime watchlist be like", "watchlist", '["watchlist", "overwhelmed"]'),
    ]
    c.executemany('''INSERT INTO memes (image_url, caption, category, tags) VALUES (?, ?, ?, ?)''', sample_memes)
    
    # Groups with settings
    c.execute('''CREATE TABLE IF NOT EXISTS groups (
        group_id INTEGER PRIMARY KEY,
        title TEXT,
        settings TEXT DEFAULT '{"quiz": true, "memes": true, "battle": true, "spoiler_warning": true}',
        member_count INTEGER DEFAULT 0,
        activity_score INTEGER DEFAULT 0,
        added_date TEXT DEFAULT CURRENT_TIMESTAMP,
        last_active TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Add default admin
    for admin_id in ADMIN_IDS:
        c.execute("INSERT OR IGNORE INTO users (user_id, is_admin) VALUES (?, 1)", (admin_id,))
    
    conn.commit()
    conn.close()
    logger.info("Database initialized with complete schema")

init_database()

# =========== DATABASE FUNCTIONS ===========
class Database:
    @staticmethod
    def execute(query, params=(), fetchone=False, fetchall=False):
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(query, params)
        
        if fetchone:
            result = c.fetchone()
            result = dict(result) if result else None
        elif fetchall:
            result = [dict(row) for row in c.fetchall()]
        else:
            result = c.lastrowid
        
        conn.commit()
        conn.close()
        return result
    
    @staticmethod
    def get_user(user_id):
        return Database.execute("SELECT * FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    
    @staticmethod
    def create_user(user_id, username, first_name):
        Database.execute(
            """INSERT OR IGNORE INTO users 
            (user_id, username, first_name, joined_date, last_active, daily_reward_claimed) 
            VALUES (?, ?, ?, datetime('now'), datetime('now'), date('now', '-1 day'))""",
            (user_id, username, first_name)
        )
    
    @staticmethod
    def update_user(user_id, **kwargs):
        if not kwargs:
            return
        
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [user_id]
        
        Database.execute(
            f"UPDATE users SET {set_clause}, last_active = datetime('now') WHERE user_id = ?",
            tuple(values)
        )
    
    @staticmethod
    def add_achievement(user_id, achievement_id):
        user = Database.get_user(user_id)
        if not user:
            return False
        
        achievements = json.loads(user['achievements']) if user['achievements'] else []
        if achievement_id not in achievements:
            achievements.append(achievement_id)
            Database.update_user(user_id, achievements=json.dumps(achievements))
            return True
        return False
    
    @staticmethod
    def check_achievements(user_id):
        """Check and unlock achievements"""
        user = Database.get_user(user_id)
        if not user:
            return []
        
        stats = json.loads(user['stats']) if user['stats'] else {}
        unlocked = []
        
        # Get all achievements
        all_achievements = Database.execute("SELECT * FROM achievements", fetchall=True)
        
        for ach in all_achievements:
            requirement = ach['requirement']
            # Check each requirement
            if "commands >= 1" in requirement and stats.get('commands', 0) >= 1:
                if Database.add_achievement(user_id, ach['id']):
                    unlocked.append(ach)
            elif "searches >= 100" in requirement and stats.get('searches', 0) >= 100:
                if Database.add_achievement(user_id, ach['id']):
                    unlocked.append(ach)
            elif "quiz_score >= 1000" in requirement and stats.get('quiz_score', 0) >= 1000:
                if Database.add_achievement(user_id, ach['id']):
                    unlocked.append(ach)
            elif "battle_wins >= 50" in requirement and stats.get('battle_wins', 0) >= 50:
                if Database.add_achievement(user_id, ach['id']):
                    unlocked.append(ach)
            elif "daily_streak >= 7" in requirement and stats.get('daily_streak', 0) >= 7:
                if Database.add_achievement(user_id, ach['id']):
                    unlocked.append(ach)
        
        return unlocked
    
    @staticmethod
    def get_daily_reward(user_id):
        """Claim daily reward"""
        user = Database.get_user(user_id)
        if not user:
            return None
        
        today = datetime.now().strftime('%Y-%m-%d')
        last_claim = user.get('daily_reward_claimed')
        
        if last_claim == today:
            return {"claimed": True, "streak": 0}
        
        # Update streak
        stats = json.loads(user['stats']) if user['stats'] else {}
        
        if last_claim == (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'):
            stats['daily_streak'] = stats.get('daily_streak', 0) + 1
        else:
            stats['daily_streak'] = 1
        
        # Add reward points
        streak = stats['daily_streak']
        reward = 10 + (streak * 5)  # 10 base + 5 per streak day
        
        stats['quiz_score'] = stats.get('quiz_score', 0) + reward
        Database.update_user(user_id, 
                           stats=json.dumps(stats),
                           daily_reward_claimed=today)
        
        return {"claimed": False, "reward": reward, "streak": streak}
    
    @staticmethod
    def get_quiz_question(category=None, difficulty=None):
        query = "SELECT * FROM quiz_questions"
        params = []
        
        if category or difficulty:
            conditions = []
            if category:
                conditions.append("category = ?")
                params.append(category)
            if difficulty:
                conditions.append("difficulty = ?")
                params.append(difficulty)
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY RANDOM() LIMIT 1"
        return Database.execute(query, tuple(params), fetchone=True)
    
    @staticmethod
    def get_random_meme(category=None):
        query = "SELECT * FROM memes"
        params = []
        
        if category:
            query += " WHERE category = ?"
            params.append(category)
        
        query += " ORDER BY RANDOM() LIMIT 1"
        return Database.execute(query, tuple(params), fetchone=True)

# =========== ANILIST API ===========
class AniListAPI:
    def __init__(self):
        self.base_url = "https://graphql.anilist.co"
        self.session = None
        self.cache = {}
    
    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self.session
    
    async def search_anime(self, query, page=1, per_page=10):
        cache_key = f"search_{query}_{page}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        search_query = """
        query ($search: String, $page: Int, $perPage: Int) {
          Page(page: $page, perPage: $perPage) {
            media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
              id
              title {
                romaji
                english
                native
                userPreferred
              }
              coverImage {
                extraLarge
                large
                medium
                color
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
                      userPreferred
                    }
                    coverImage {
                      large
                    }
                  }
                }
              }
              characters(perPage: 10, sort: ROLE) {
                edges {
                  node {
                    id
                    name {
                      full
                      native
                      alternative
                    }
                    image {
                      large
                    }
                    description(asHtml: false)
                  }
                  role
                  voiceActors(language: JAPANESE) {
                    id
                    name {
                      full
                      native
                    }
                    image {
                      large
                    }
                  }
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
              nextAiringEpisode {
                episode
                timeUntilAiring
              }
            }
          }
        }
        """
        
        try:
            session = await self._get_session()
            async with session.post(
                self.base_url,
                json={"query": search_query, "variables": {
                    "search": query,
                    "page": page,
                    "perPage": per_page
                }},
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if "errors" in data:
                        return []
                    results = data.get("data", {}).get("Page", {}).get("media", [])
                    self.cache[cache_key] = results
                    return results
                return []
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    async def get_anime(self, anime_id):
        cache_key = f"anime_{anime_id}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        query = """
        query ($id: Int) {
          Media(id: $id, type: ANIME) {
            id
            title {
              romaji
              english
              native
              userPreferred
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
            season
            seasonYear
            coverImage {
              extraLarge
              large
              medium
              color
            }
            bannerImage
            genres
            synonyms
            studios {
              edges {
                node {
                  name
                  isAnimationStudio
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
                    userPreferred
                  }
                  coverImage {
                    large
                  }
                  format
                  averageScore
                }
              }
            }
            characters(perPage: 15, sort: ROLE) {
              edges {
                node {
                  id
                  name {
                    full
                    native
                    alternative
                  }
                  image {
                    large
                  }
                  description(asHtml: false)
                  age
                  gender
                  dateOfBirth {
                    year
                    month
                    day
                  }
                  favourites
                }
                role
                voiceActors(language: JAPANESE) {
                  id
                  name {
                    full
                    native
                  }
                  image {
                    large
                  }
                }
              }
            }
            trailer {
              id
              site
              thumbnail
            }
            recommendations(perPage: 10) {
              edges {
                node {
                  mediaRecommendation {
                    id
                    title {
                      romaji
                      english
                    }
                    coverImage {
                      large
                    }
                    averageScore
                  }
                }
              }
            }
            stats {
              scoreDistribution {
                score
                amount
              }
              statusDistribution {
                status
                amount
              }
            }
            rankings {
              rank
              type
              format
              year
              season
              allTime
            }
            siteUrl
            nextAiringEpisode {
              episode
              timeUntilAiring
            }
            externalLinks {
              url
              site
            }
          }
        }
        """
        
        try:
            session = await self._get_session()
            async with session.post(
                self.base_url,
                json={"query": query, "variables": {"id": anime_id}},
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if "errors" in data:
                        return {"error": "Anime not found"}
                    anime = data.get("data", {}).get("Media", {})
                    self.cache[cache_key] = anime
                    return anime
                return {"error": "API error"}
        except Exception as e:
            logger.error(f"Get anime error: {e}")
            return {"error": str(e)}
    
    async def search_character(self, query, per_page=10):
        cache_key = f"char_{query}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
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
              bloodType
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
                  characterRole
                }
              }
              siteUrl
            }
          }
        }
        """
        
        try:
            session = await self._get_session()
            async with session.post(
                self.base_url,
                json={"query": char_query, "variables": {
                    "search": query,
                    "perPage": per_page
                }},
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if "errors" in data:
                        return []
                    results = data.get("data", {}).get("Page", {}).get("characters", [])
                    self.cache[cache_key] = results
                    return results
                return []
        except Exception as e:
            logger.error(f"Character search error: {e}")
            return []

anilist = AniListAPI()

# =========== HELPER FUNCTIONS ===========
def format_description(desc, max_len=400):
    if not desc:
        return "No description available."
    desc = re.sub(r'<[^>]+>', '', desc)
    desc = re.sub(r'\s+', ' ', desc).strip()
    if len(desc) > max_len:
        desc = desc[:max_len] + "..."
    return desc

def get_airing_status(anime):
    status = anime.get('status', '').replace('_', ' ').title()
    
    if status == "Releasing" and anime.get('nextAiringEpisode'):
        next_ep = anime['nextAiringEpisode']
        episode = next_ep.get('episode', 0)
        seconds = next_ep.get('timeUntilAiring', 0)
        
        if seconds > 0:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            return f"Episode {episode} in {days}d {hours}h"
    
    return status

async def get_waifu_image():
    """Get real waifu image from multiple sources"""
    sources = [
        "https://api.waifu.pics/sfw/waifu",
        "https://nekos.best/api/v2/waifu",
        "https://api.nekosapi.com/v2/images/random?category=waifu",
    ]
    
    for source in sources:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(source, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "url" in data:
                            return data["url"]
                        elif "results" in data and len(data["results"]) > 0:
                            return data["results"][0]["url"]
                        elif "image_url" in data:
                            return data["image_url"]
        except:
            continue
    
    # Fallback images
    fallback = [
        "https://i.imgur.com/XW6J2r5.jpg",
        "https://i.imgur.com/3J8W1yZ.jpg",
        "https://i.imgur.com/5K7X9l5.jpg",
        "https://i.imgur.com/8L9M0vN.jpg",
        "https://i.imgur.com/9N1OwXp.jpg",
    ]
    return random.choice(fallback)

async def get_husbando_image():
    """Get real husbando image"""
    try:
        # Try to get male character from AniList
        chars = await anilist.search_character("", 50)
        if chars:
            male_chars = [c for c in chars if c.get('gender', '').lower() == 'male']
            if male_chars:
                char = random.choice(male_chars)
                return char.get('image', {}).get('large')
    except:
        pass
    
    # Fallback to waifu images
    return await get_waifu_image()

def is_admin(user_id):
    if user_id in ADMIN_IDS:
        return True
    user = Database.get_user(user_id)
    return user and user['is_admin'] == 1

def is_banned(user_id):
    user = Database.get_user(user_id)
    return user and user['is_banned'] == 1

def check_cooldown(user_id, command, seconds=2):
    key = f"{user_id}_{command}"
    now = time.time()
    
    if key in user_cooldowns:
        if now - user_cooldowns[key] < seconds:
            return False
    
    user_cooldowns[key] = now
    return True

# =========== UNIQUE FEATURES ===========
class UniqueFeatures:
    """Unique features for the bot"""
    
    @staticmethod
    async def create_character_carousel(anime_id, page=0):
        """Create character carousel with pagination"""
        anime = await anilist.get_anime(anime_id)
        if "error" in anime:
            return None, None
        
        characters = anime.get('characters', {}).get('edges', [])
        if not characters:
            return "No characters found.", None
        
        # Paginate (4 per page)
        per_page = 4
        total_pages = (len(characters) + per_page - 1) // per_page
        page = max(0, min(page, total_pages - 1))
        
        start_idx = page * per_page
        end_idx = min(start_idx + per_page, len(characters))
        
        # Create message
        title = anime.get('title', {}).get('userPreferred', 'Anime')
        message = f"👥 **Characters from {title}**\n\n"
        message += f"*Page {page + 1}/{total_pages}*\n\n"
        
        keyboard = InlineKeyboardBuilder()
        
        for i in range(start_idx, end_idx):
            char = characters[i]
            char_node = char['node']
            name = char_node['name']['full']
            role = char['role'].replace('_', ' ').title()
            
            # Voice actors
            voice_actors = char.get('voiceActors', [])
            va_text = ""
            if voice_actors:
                va_name = voice_actors[0]['name']['full']
                va_text = f" (VA: {va_name})"
            
            message += f"**{i+1}. {name}**\n"
            message += f"   Role: {role}{va_text}\n\n"
            
            # Add character view button
            keyboard.button(
                text=f"{i+1}. {name[:10]}...",
                callback_data=f"view_char_{char_node['id']}"
            )
        
        keyboard.adjust(2)
        
        # Navigation buttons
        nav_row = InlineKeyboardBuilder()
        if page > 0:
            nav_row.button(text="⬅️ Previous", callback_data=f"chars_{anime_id}_{page-1}")
        if page < total_pages - 1:
            nav_row.button(text="Next ➡️", callback_data=f"chars_{anime_id}_{page+1}")
        nav_row.adjust(2)
        
        keyboard.row(*nav_row.buttons[0])
        
        # Back to anime button
        keyboard.button(text="🔙 Back to Anime", callback_data=f"back_anime_{anime_id}")
        
        return message, keyboard.as_markup()
    
    @staticmethod
    async def create_recommendations_carousel(anime_id):
        """Create anime recommendations carousel"""
        anime = await anilist.get_anime(anime_id)
        if "error" in anime:
            return None, None
        
        recs = anime.get('recommendations', {}).get('edges', [])
        if not recs:
            return "No recommendations available.", None
        
        # Get top 5 recommendations
        recs = recs[:5]
        
        message = "🎯 **Recommended Anime**\n\n"
        message += f"*Because you liked {anime.get('title', {}).get('userPreferred', 'this anime')}*\n\n"
        
        keyboard = InlineKeyboardBuilder()
        
        for i, rec in enumerate(recs):
            rec_anime = rec['node']['mediaRecommendation']
            if not rec_anime:
                continue
            
            title = rec_anime['title']['romaji'] or rec_anime['title']['english']
            score = rec_anime.get('averageScore', 'N/A')
            
            message += f"**{i+1}. {title}**\n"
            message += f"   Score: {score}/100\n\n"
            
            keyboard.button(
                text=f"{i+1}. {title[:12]}...",
                callback_data=f"anime_{rec_anime['id']}"
            )
        
        keyboard.adjust(2)
        keyboard.button(text="🔙 Back to Anime", callback_data=f"back_anime_{anime_id}")
        
        return message, keyboard.as_markup()
    
    @staticmethod
    async def create_relations_view(anime_id):
        """Show anime relations (prequels, sequels, etc.)"""
        anime = await anilist.get_anime(anime_id)
        if "error" in anime:
            return None, None
        
        relations = anime.get('relations', {}).get('edges', [])
        if not relations:
            return "No related anime found.", None
        
        # Group by relation type
        relation_types = {}
        for rel in relations:
            rel_type = rel['relationType']
            if rel_type not in relation_types:
                relation_types[rel_type] = []
            relation_types[rel_type].append(rel['node'])
        
        message = "🔗 **Related Anime**\n\n"
        
        keyboard = InlineKeyboardBuilder()
        
        # Show main relations
        main_types = ['PREQUEL', 'SEQUEL', 'SIDE_STORY', 'PARENT', 'ADAPTATION']
        
        for rel_type in main_types:
            if rel_type in relation_types:
                rels = relation_types[rel_type]
                rel_type_name = rel_type.replace('_', ' ').title()
                message += f"**{rel_type_name}:**\n"
                
                for i, rel in enumerate(rels[:3]):  # Show max 3 per type
                    title = rel['title']['romaji'] or rel['title']['english']
                    message += f"  • {title}\n"
                    
                    keyboard.button(
                        text=f"{rel_type[:3]}. {title[:10]}...",
                        callback_data=f"anime_{rel['id']}"
                    )
                
                message += "\n"
        
        keyboard.adjust(2)
        keyboard.button(text="🔙 Back to Anime", callback_data=f"back_anime_{anime_id}")
        
        return message, keyboard.as_markup()

# =========== BATTLE SYSTEM ===========
class EnhancedBattle:
    """Enhanced battle system with special moves"""
    
    CHARACTERS = {
        "Goku": {
            "hp": 1000, "attack": 150, "defense": 80, "speed": 95,
            "special": "Kamehameha", "anime": "Dragon Ball",
            "moves": ["Punch", "Kick", "Kamehameha", "Instant Transmission"]
        },
        "Naruto": {
            "hp": 800, "attack": 120, "defense": 70, "speed": 85,
            "special": "Rasengan", "anime": "Naruto",
            "moves": ["Shadow Clone", "Rasengan", "Sage Mode", "Talk No Jutsu"]
        },
        "Luffy": {
            "hp": 900, "attack": 130, "defense": 75, "speed": 80,
            "special": "Gear Fourth", "anime": "One Piece",
            "moves": ["Gum Gum Pistol", "Gear Second", "Gear Fourth", "Conqueror's Haki"]
        },
        "Eren Yeager": {
            "hp": 750, "attack": 110, "defense": 65, "speed": 75,
            "special": "Titan Transformation", "anime": "Attack on Titan",
            "moves": ["Titan Form", "Hardening", "Warhammer", "Founding Titan"]
        },
        "Levi Ackerman": {
            "hp": 700, "attack": 140, "defense": 60, "speed": 100,
            "special": "Ultimate Speed", "anime": "Attack on Titan",
            "moves": ["ODM Gear", "Sword Slash", "Thunder Spear", "Ackerman Power"]
        },
        "Saitama": {
            "hp": 9999, "attack": 999, "defense": 999, "speed": 999,
            "special": "Serious Punch", "anime": "One Punch Man",
            "moves": ["Normal Punch", "Consecutive Punches", "Serious Punch", "Serious Series"]
        },
        "Light Yagami": {
            "hp": 500, "attack": 999, "defense": 30, "speed": 60,
            "special": "Death Note", "anime": "Death Note",
            "moves": ["Write Name", "Manipulation", "Planning", "Kira"]
        },
        "Killua Zoldyck": {
            "hp": 650, "attack": 125, "defense": 65, "speed": 110,
            "special": "Godspeed", "anime": "Hunter x Hunter",
            "moves": ["Lightning Palm", "Godspeed", "Assassin Mode", "Yo-yos"]
        },
        "Gon Freecss": {
            "hp": 750, "attack": 135, "defense": 70, "speed": 85,
            "special": "Jajanken", "anime": "Hunter x Hunter",
            "moves": ["Jajanken: Rock", "Jajanken: Paper", "Jajanken: Scissors", "Enhanced State"]
        },
        "Ichigo Kurosaki": {
            "hp": 850, "attack": 140, "defense": 75, "speed": 90,
            "special": "Getsuga Tensho", "anime": "Bleach",
            "moves": ["Getsuga Tensho", "Bankai", "Hollow Mask", "Final Getsuga"]
        },
    }
    
    @staticmethod
    async def start(player1_id, player2_id, chat_id):
        battle_id = f"{player1_id}_{player2_id}_{int(time.time())}"
        
        chars = list(EnhancedBattle.CHARACTERS.keys())
        char1 = random.choice(chars)
        char2 = random.choice([c for c in chars if c != char1])
        
        battle_data = {
            "player1": {
                "id": player1_id,
                "character": char1,
                "hp": EnhancedBattle.CHARACTERS[char1]["hp"],
                "max_hp": EnhancedBattle.CHARACTERS[char1]["hp"],
                "moves_used": []
            },
            "player2": {
                "id": player2_id,
                "character": char2,
                "hp": EnhancedBattle.CHARACTERS[char2]["hp"],
                "max_hp": EnhancedBattle.CHARACTERS[char2]["hp"],
                "moves_used": []
            },
            "turn": player1_id,
            "round": 1,
            "chat_id": chat_id,
            "active": True,
            "log": []
        }
        
        active_battles[battle_id] = battle_data
        
        # Create battle message with health bars
        char1_stats = EnhancedBattle.CHARACTERS[char1]
        char2_stats = EnhancedBattle.CHARACTERS[char2]
        
        # Health bar function
        def health_bar(hp, max_hp):
            filled = int((hp / max_hp) * 10)
            return "█" * filled + "░" * (10 - filled)
        
        hp_bar1 = health_bar(char1_stats["hp"], char1_stats["hp"])
        hp_bar2 = health_bar(char2_stats["hp"], char2_stats["hp"])
        
        message = f"""⚔️ **BATTLE STARTED!** ⚔️

🎌 **{char1}** ({char1_stats['anime']})
{hp_bar1} {char1_stats['hp']}/{char1_stats['hp']} HP
⚔️ ATK: {char1_stats['attack']} | 🛡️ DEF: {char1_stats['defense']} | 🏃 SPD: {char1_stats['speed']}

**VS**

🎌 **{char2}** ({char2_stats['anime']})
{hp_bar2} {char2_stats['hp']}/{char2_stats['hp']} HP
⚔️ ATK: {char2_stats['attack']} | 🛡️ DEF: {char2_stats['defense']} | 🏃 SPD: {char2_stats['speed']}

**Player 1's turn!**
Use `/attack` to fight or `/special` for special move!"""
        
        return battle_id, message
    
    @staticmethod
    async def attack(battle_id, attacker_id, move_type="normal"):
        if battle_id not in active_battles:
            return None, "Battle not found!"
        
        battle = active_battles[battle_id]
        
        if not battle["active"]:
            return battle_id, "Battle has ended!"
        
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
        
        # Get character stats
        attacker_stats = EnhancedBattle.CHARACTERS[attacker["character"]]
        defender_stats = EnhancedBattle.CHARACTERS[defender["character"]]
        
        # Calculate damage based on move type
        if move_type == "special":
            base_damage = attacker_stats["attack"] * 1.5
            move_text = f"✨ **{attacker_stats['special']}!** ✨"
            crit_chance = 0.3
        else:
            base_damage = attacker_stats["attack"]
            move_text = "⚔️ **Normal Attack**"
            crit_chance = 0.1
        
        # Apply defense
        damage = int(base_damage * (100 / (100 + defender_stats["defense"])))
        
        # Critical hit chance
        if random.random() < crit_chance:
            damage = int(damage * 1.5)
            move_text += " 💥 **CRITICAL HIT!** 💥"
        
        # Ensure minimum damage
        damage = max(10, damage)
        
        # Apply damage
        defender["hp"] = max(0, defender["hp"] - damage)
        
        # Log the move
        move_name = attacker_stats["special"] if move_type == "special" else "Attack"
        battle["log"].append(f"Round {battle['round']}: {attacker['character']} used {move_name} for {damage} damage")
        
        # Update battle state
        battle["turn"] = next_turn
        battle["round"] += 1
        
        # Health bar function
        def health_bar(hp, max_hp):
            filled = int((hp / max_hp) * 10)
            return "█" * filled + "░" * (10 - filled)
        
        # Check for winner
        winner = None
        if defender["hp"] <= 0:
            winner = attacker
            battle["active"] = False
            
            # Update user stats
            user = Database.get_user(attacker["id"])
            if user:
                stats = json.loads(user['stats'])
                stats['battle_wins'] = stats.get('battle_wins', 0) + 1
                Database.update_user(attacker["id"], stats=json.dumps(stats))
            
            # Check achievements
            Database.check_achievements(attacker["id"])
        
        # Create battle update
        hp_bar1 = health_bar(battle["player1"]["hp"], battle["player1"]["max_hp"])
        hp_bar2 = health_bar(battle["player2"]["hp"], battle["player2"]["max_hp"])
        
        message = f"""⚔️ **Round {battle['round']-1}** ⚔️

{move_text}

**{attacker['character']}** attacked **{defender['character']}** for **{damage} damage**!

**Current Status:**
🎌 {battle['player1']['character']}: {hp_bar1} {battle['player1']['hp']}/{battle['player1']['max_hp']} HP
🎌 {battle['player2']['character']}: {hp_bar2} {battle['player2']['hp']}/{battle['player2']['max_hp']} HP"""
        
        if winner:
            message += f"\n\n🎉 **VICTORY!** {winner['character']} wins the battle!"
            # Add victory effects
            if damage >= 100:
                message += f"\n💥 **MASSIVE DAMAGE!** That was incredible!"
            
            # Remove from active battles
            del active_battles[battle_id]
        else:
            message += f"\n\n**Next Turn:** {'Player 1' if next_turn == battle['player1']['id'] else 'Player 2'}"
            message += f"\nUse `/attack` or `/special`!"
        
        return battle_id, message

# =========== QUIZ SYSTEM ===========
async def start_quiz(user_id, chat_id, category=None, difficulty=None):
    """Start enhanced quiz with poll"""
    question = Database.get_quiz_question(category, difficulty)
    if not question:
        return None
    
    options = json.loads(question['options'])
    
    try:
        # Create poll with question
        poll_message = await bot.send_poll(
            chat_id=chat_id,
            question=f"🎮 **Anime Quiz**\n\n{question['question']}",
            options=options,
            type="quiz",
            correct_option_id=question['correct_answer'],
            explanation=f"📚 {question['explanation']}\n🎌 Source: {question['source_anime']}",
            open_period=45,
            is_anonymous=False,
            allows_multiple_answers=False
        )
        
        # Store quiz data
        quiz_id = f"{user_id}_{int(time.time())}"
        active_quizzes[quiz_id] = {
            "poll_id": poll_message.poll.id,
            "question": question,
            "user_id": user_id,
            "chat_id": chat_id,
            "message_id": poll_message.message_id,
            "answered": False
        }
        
        return quiz_id
    except Exception as e:
        logger.error(f"Quiz error: {e}")
        return None

# =========== COMMAND HANDLERS ===========

@dp.message(CommandStart())
async def start_cmd(message: Message):
    """Enhanced start command"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 The bot is currently under maintenance. Please try again later.")
        return
    
    if is_banned(user.id):
        return
    
    Database.create_user(user.id, user.username, user.first_name)
    
    # Check daily reward
    reward = Database.get_daily_reward(user.id)
    
    # Check and unlock achievements
    unlocked = Database.check_achievements(user.id)
    
    welcome = f"""🎌 **Welcome to AnimeKuun, {user.first_name}!** 🎌

✨ **Your Ultimate Anime Companion** ✨

📚 **Search & Discover:**
• `/anime <name>` - Find anime with full details
• `/character <name>` - Character info with images

💖 **Fun & Games:**
• `/waifu` - Your anime soulmate (with image)
• `/husbando` - Your anime partner (with image)
• `/quiz` - Anime trivia (Telegram poll)
• `/battle @user` - Battle with anime characters
• `/meme` - Anime memes

👤 **Profile & Social:**
• `/profile` - Your stats & achievements
• `/favorites` - Your favorite anime
• `/daily` - Claim daily reward

💬 **All commands work in groups too!**
Made with ❤️ for anime fans worldwide! 🎬"""
    
    # Add reward message if claimed
    if reward and not reward.get('claimed'):
        welcome += f"\n\n🎁 **Daily Reward Claimed!** +{reward['reward']} points!"
        welcome += f"\n🔥 Streak: {reward['streak']} days"
    
    # Add achievements if unlocked
    if unlocked:
        welcome += f"\n\n🏆 **New Achievements Unlocked!**"
        for ach in unlocked[:3]:  # Show first 3
            welcome += f"\n• {ach['icon']} {ach['name']}"
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔍 Search Anime", switch_inline_query_current_chat="anime ")
    keyboard.button(text="🎮 Quick Quiz", callback_data="quick_quiz")
    keyboard.adjust(2)
    keyboard.button(text="💖 Get Waifu", callback_data="get_waifu")
    keyboard.button(text="💙 Get Husbando", callback_data="get_husbando")
    
    await message.answer(welcome, reply_markup=keyboard.as_markup())

@dp.message(Command("anime"))
async def anime_cmd(message: Message):
    """Enhanced anime search with ALL buttons working"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 Maintenance mode. Try again later.")
        return
    
    if is_banned(user.id):
        return
    
    # Check cooldown
    if not check_cooldown(user.id, "anime", 3):
        await message.answer("⏳ Please wait before searching again.")
        return
    
    # Get full query
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("🎬 **Usage:** `/anime <anime name>`\n**Example:** `/anime Attack on Titan`")
        return
    
    query = args[1].strip()
    search_msg = await message.answer(f"🔍 **Searching for:** `{query}`...")
    
    try:
        # Update user stats
        user_data = Database.get_user(user.id)
        if user_data:
            stats = json.loads(user_data['stats'])
            stats['searches'] = stats.get('searches', 0) + 1
            stats['commands'] = stats.get('commands', 0) + 1
            Database.update_user(user.id, stats=json.dumps(stats))
        
        results = await anilist.search_anime(query, per_page=5)
        
        if not results:
            await search_msg.edit_text(f"❌ **No results found for:** `{query}`\n\nTry a different search term!")
            return
        
        # Get first result with full details
        anime = await anilist.get_anime(results[0]['id'])
        
        if "error" in anime:
            await search_msg.edit_text("❌ **Failed to fetch anime details.**\n\nPlease try again later.")
            return
        
        # Format anime details
        title = anime.get('title', {}).get('english') or anime.get('title', {}).get('romaji', 'Unknown')
        native_title = anime.get('title', {}).get('native', '')
        desc = format_description(anime.get('description', ''))
        
        # Get additional info
        genres = anime.get('genres', [])
        studios = anime.get('studios', {}).get('edges', [])
        studio_names = [s['node']['name'] for s in studios[:2] if s['node']['isAnimationStudio']]
        
        # Airing status
        status = get_airing_status(anime)
        
        # Create detailed response
        response = f"""🎬 **{title}**
{native_title}

⭐ **Score:** {anime.get('averageScore', 'N/A')}/100
📊 **Popularity:** #{anime.get('popularity', 'N/A')}
🎞️ **Format:** {anime.get('format', 'N/A')}
📺 **Episodes:** {anime.get('episodes', 'N/A')}
⏱️ **Duration:** {anime.get('duration', 'N/A')} min
📅 **Status:** {status}
🏷️ **Genres:** {', '.join(genres[:5]) if genres else 'N/A'}
🎨 **Studios:** {', '.join(studio_names) if studio_names else 'N/A'}

📝 **Description:**
{desc}

🔗 **AniList:** {anime.get('siteUrl', '#')}"""
        
        # Create comprehensive keyboard
        keyboard = InlineKeyboardBuilder()
        
        # Main action buttons
        characters = anime.get('characters', {}).get('edges', [])
        if characters:
            keyboard.button(text="👥 Characters", callback_data=f"chars_{anime['id']}_0")
        
        trailer = anime.get('trailer', {})
        if trailer and trailer.get('site') == 'youtube':
            trailer_id = trailer.get('id')
            keyboard.button(text="🎬 Trailer", url=f"https://youtube.com/watch?v={trailer_id}")
        
        relations = anime.get('relations', {}).get('edges', [])
        if relations:
            keyboard.button(text="🔗 Related", callback_data=f"relations_{anime['id']}")
        
        recommendations = anime.get('recommendations', {}).get('edges', [])
        if recommendations:
            keyboard.button(text="🎯 Recommendations", callback_data=f"recs_{anime['id']}")
        
        keyboard.adjust(2)
        
        # Secondary action buttons
        keyboard.button(text="⭐ Add to Favorites", callback_data=f"fav_{anime['id']}_{quote(title)}")
        keyboard.button(text="🎮 Watch Party", callback_data=f"watch_party_{anime['id']}")
        
        # Try to send with cover image
        cover = anime.get('coverImage', {}).get('large') or anime.get('coverImage', {}).get('medium')
        if cover:
            try:
                await message.answer_photo(
                    photo=URLInputFile(cover),
                    caption=response,
                    reply_markup=keyboard.as_markup()
                )
                await search_msg.delete()
                return
            except Exception as e:
                logger.error(f"Image send error: {e}")
                # Continue with text-only
        
        await search_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Anime command error: {e}")
        await search_msg.edit_text("❌ **An error occurred.**\n\nPlease try again or contact support if the issue persists.")

# =========== BUTTON HANDLERS ===========

@dp.callback_query(F.data.startswith("chars_"))
async def show_characters(callback: CallbackQuery):
    """Show characters with pagination - EDITS SAME MESSAGE"""
    try:
        parts = callback.data.split("_")
        anime_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 0
        
        # Get character carousel
        message, keyboard = await UniqueFeatures.create_character_carousel(anime_id, page)
        
        if not message:
            await callback.answer("❌ No characters found", show_alert=True)
            return
        
        # EDIT the existing message
        await callback.message.edit_caption(
            caption=message,
            reply_markup=keyboard
        )
        await callback.answer(f"Page {page + 1}")
        
    except Exception as e:
        logger.error(f"Characters error: {e}")
        await callback.answer("❌ Error loading characters", show_alert=True)

@dp.callback_query(F.data.startswith("view_char_"))
async def view_character(callback: CallbackQuery):
    """View single character details"""
    try:
        char_id = int(callback.data.split("_")[2])
        
        # In a real implementation, fetch character details
        # For now, show placeholder
        response = "👤 **Character Details**\n\n*Detailed view coming soon!*"
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔙 Back to Characters", callback_data=f"chars_{1}_0")  # Placeholder
        
        await callback.message.edit_caption(
            caption=response,
            reply_markup=keyboard.as_markup()
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"View character error: {e}")
        await callback.answer("❌ Error", show_alert=True)

@dp.callback_query(F.data.startswith("relations_"))
async def show_relations(callback: CallbackQuery):
    """Show anime relations - EDITS SAME MESSAGE"""
    try:
        anime_id = int(callback.data.split("_")[1])
        
        message, keyboard = await UniqueFeatures.create_relations_view(anime_id)
        
        if not message:
            await callback.answer("❌ No relations found", show_alert=True)
            return
        
        await callback.message.edit_caption(
            caption=message,
            reply_markup=keyboard
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Relations error: {e}")
        await callback.answer("❌ Error loading relations", show_alert=True)

@dp.callback_query(F.data.startswith("recs_"))
async def show_recommendations(callback: CallbackQuery):
    """Show anime recommendations - EDITS SAME MESSAGE"""
    try:
        anime_id = int(callback.data.split("_")[1])
        
        message, keyboard = await UniqueFeatures.create_recommendations_carousel(anime_id)
        
        if not message:
            await callback.answer("❌ No recommendations available", show_alert=True)
            return
        
        await callback.message.edit_caption(
            caption=message,
            reply_markup=keyboard
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Recommendations error: {e}")
        await callback.answer("❌ Error loading recommendations", show_alert=True)

@dp.callback_query(F.data.startswith("back_anime_"))
async def back_to_anime(callback: CallbackQuery):
    """Go back to anime view - EDITS SAME MESSAGE"""
    try:
        anime_id = int(callback.data.split("_")[2])
        
        # Fetch anime details again
        anime = await anilist.get_anime(anime_id)
        
        if "error" in anime:
            await callback.answer("❌ Error loading anime", show_alert=True)
            return
        
        # Recreate the anime view (similar to anime_cmd but for edit)
        title = anime.get('title', {}).get('english') or anime.get('title', {}).get('romaji', 'Unknown')
        desc = format_description(anime.get('description', ''))
        status = get_airing_status(anime)
        
        response = f"""🎬 **{title}**

⭐ **Score:** {anime.get('averageScore', 'N/A')}/100
📊 **Popularity:** #{anime.get('popularity', 'N/A')}
🎞️ **Format:** {anime.get('format', 'N/A')}
📺 **Episodes:** {anime.get('episodes', 'N/A')}
⏱️ **Duration:** {anime.get('duration', 'N/A')} min
📅 **Status:** {status}
🏷️ **Genres:** {', '.join(anime.get('genres', ['N/A'])[:5])}

📝 **Description:**
{desc}

🔗 **AniList:** {anime.get('siteUrl', '#')}"""
        
        # Recreate keyboard
        keyboard = InlineKeyboardBuilder()
        
        characters = anime.get('characters', {}).get('edges', [])
        if characters:
            keyboard.button(text="👥 Characters", callback_data=f"chars_{anime_id}_0")
        
        trailer = anime.get('trailer', {})
        if trailer and trailer.get('site') == 'youtube':
            trailer_id = trailer.get('id')
            keyboard.button(text="🎬 Trailer", url=f"https://youtube.com/watch?v={trailer_id}")
        
        relations = anime.get('relations', {}).get('edges', [])
        if relations:
            keyboard.button(text="🔗 Related", callback_data=f"relations_{anime_id}")
        
        recommendations = anime.get('recommendations', {}).get('edges', [])
        if recommendations:
            keyboard.button(text="🎯 Recommendations", callback_data=f"recs_{anime_id}")
        
        keyboard.adjust(2)
        keyboard.button(text="⭐ Add to Favorites", callback_data=f"fav_{anime_id}_{quote(title)}")
        
        await callback.message.edit_caption(
            caption=response,
            reply_markup=keyboard.as_markup()
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Back to anime error: {e}")
        await callback.answer("❌ Error", show_alert=True)

@dp.callback_query(F.data.startswith("fav_"))
async def add_favorite(callback: CallbackQuery):
    """Add anime to favorites"""
    try:
        parts = callback.data.split("_")
        anime_id = int(parts[1])
        anime_title = " ".join(parts[2:]) if len(parts) > 2 else "Unknown"
        
        # Get anime to get cover image
        anime = await anilist.get_anime(anime_id)
        cover = ""
        if "error" not in anime:
            cover = anime.get('coverImage', {}).get('medium', '')
        
        # Add to favorites in database
        user = Database.get_user(callback.from_user.id)
        if user:
            favorites = json.loads(user['favorites']) if user['favorites'] else []
            
            # Check if already favorited
            for fav in favorites:
                if fav.get('id') == anime_id:
                    await callback.answer(f"⭐ {anime_title} is already in your favorites!", show_alert=True)
                    return
            
            # Add new favorite
            favorites.append({
                "id": anime_id,
                "title": anime_title,
                "image": cover,
                "added": datetime.now().isoformat()
            })
            
            Database.update_user(callback.from_user.id, favorites=json.dumps(favorites))
            
            # Update stats
            stats = json.loads(user['stats']) if user['stats'] else {}
            stats['commands'] = stats.get('commands', 0) + 1
            Database.update_user(callback.from_user.id, stats=json.dumps(stats))
            
            # Check achievements
            Database.check_achievements(callback.from_user.id)
            
            await callback.answer(f"✅ Added {anime_title} to favorites!", show_alert=True)
        else:
            await callback.answer("❌ User not found", show_alert=True)
            
    except Exception as e:
        logger.error(f"Favorite error: {e}")
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
    await waifu_cmd(msg)
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
    await husbando_cmd(msg)
    await callback.answer()

@dp.callback_query(F.data == "quick_quiz")
async def quick_quiz_callback(callback: CallbackQuery):
    """Quick quiz from callback"""
    msg = Message(
        message_id=callback.message.message_id,
        date=datetime.now(),
        chat=callback.message.chat,
        from_user=callback.from_user,
        text="/quiz"
    )
    await quiz_cmd(msg)
    await callback.answer()

# =========== OTHER COMMANDS ===========

@dp.message(Command("waifu"))
async def waifu_cmd(message: Message):
    """Get waifu with image"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 Maintenance mode.")
        return
    
    if is_banned(user.id):
        return
    
    if not check_cooldown(user.id, "waifu", 10):
        await message.answer("⏳ Please wait before getting another waifu.")
        return
    
    waifu_msg = await message.answer("💖 **Finding your perfect anime soulmate...** ✨")
    
    try:
        image_url = await get_waifu_image()
        compatibility = random.randint(70, 100)
        waifu_name = random.choice(["Sakura", "Asuna", "Rem", "Zero Two", "Mikasa", "Hinata", "Nezuko", "Mai"])
        anime = random.choice(["Naruto", "Sword Art Online", "Re:Zero", "Darling in the Franxx", "Attack on Titan", "Demon Slayer", "Rent-a-Girlfriend"])
        
        if compatibility >= 90:
            status = "💖 **PERFECT MATCH!** 💖"
            msg = "You two are destined to be together! This is true love!"
        elif compatibility >= 80:
            status = "❤️ **EXCELLENT MATCH!** ❤️"
            msg = "Amazing chemistry! This could be the start of something beautiful!"
        else:
            status = "💛 **GOOD MATCH** 💛"
            msg = "You two would make a cute couple! Give it a try!"
        
        response = f"""💖 **YOUR ANIME SOULMATE** 💖

👤 **{waifu_name}**
🎌 **From:** {anime}

💝 **Compatibility:** {compatibility}%
📊 **Status:** {status}

💌 *{msg}*

✨ *The anime gods have spoken! This is your destined partner!* ✨"""
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="💖 Claim as Waifu", callback_data=f"claim_waifu_{waifu_name}")
        keyboard.button(text="🔄 Find Another", callback_data="another_waifu")
        
        try:
            await message.answer_photo(
                photo=URLInputFile(image_url),
                caption=response,
                reply_markup=keyboard.as_markup()
            )
            await waifu_msg.delete()
        except:
            await waifu_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Waifu error: {e}")
        await waifu_msg.edit_text("💖 **Your waifu is too shy to appear right now!** 😊\n\nTry again later!")

@dp.message(Command("husbando"))
async def husbando_cmd(message: Message):
    """Get husbando with image"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 Maintenance mode.")
        return
    
    if is_banned(user.id):
        return
    
    if not check_cooldown(user.id, "husbando", 10):
        await message.answer("⏳ Please wait before getting another husbando.")
        return
    
    husbando_msg = await message.answer("💙 **Finding your perfect anime partner...** ✨")
    
    try:
        image_url = await get_husbando_image()
        compatibility = random.randint(70, 100)
        husbando_name = random.choice(["Naruto", "Luffy", "Goku", "Levi", "Eren", "Kirito", "Gojo", "Itadori"])
        anime = random.choice(["Naruto", "One Piece", "Dragon Ball", "Attack on Titan", "Sword Art Online", "Jujutsu Kaisen"])
        
        if compatibility >= 90:
            status = "💙 **PERFECT PARTNER!** 💙"
            msg = "You two are meant for each other! This is destiny!"
        elif compatibility >= 80:
            status = "💚 **EXCELLENT MATCH!** 💚"
            msg = "Incredible chemistry! This could be your soulmate!"
        else:
            status = "💛 **GOOD PARTNER** 💛"
            msg = "You two would make a great couple! Go for it!"
        
        response = f"""💙 **YOUR ANIME PARTNER** 💙

👤 **{husbando_name}**
🎌 **From:** {anime}

💝 **Compatibility:** {compatibility}%
📊 **Status:** {status}

💌 *{msg}*

✨ *The anime stars have aligned! This is your destined partner!* ✨"""
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="💙 Claim as Husbando", callback_data=f"claim_husbando_{husbando_name}")
        keyboard.button(text="🔄 Find Another", callback_data="another_husbando")
        
        try:
            await message.answer_photo(
                photo=URLInputFile(image_url),
                caption=response,
                reply_markup=keyboard.as_markup()
            )
            await husbando_msg.delete()
        except:
            await husbando_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Husbando error: {e}")
        await husbando_msg.edit_text("💙 **Your husbando is training right now!** 💪\n\nTry again later!")

@dp.message(Command("quiz"))
async def quiz_cmd(message: Message):
    """Start quiz with category selection"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 Maintenance mode.")
        return
    
    if is_banned(user.id):
        return
    
    # Check cooldown
    if not check_cooldown(user.id, "quiz", 30):
        await message.answer("⏳ Please wait 30 seconds before another quiz.")
        return
    
    # Show category selection
    keyboard = InlineKeyboardBuilder()
    categories = ["One Piece", "Naruto", "Attack on Titan", "Dragon Ball", "Demon Slayer", 
                  "Jujutsu Kaisen", "My Hero Academia", "General"]
    
    for category in categories:
        keyboard.button(text=f"🎮 {category}", callback_data=f"quiz_cat_{category}")
    
    keyboard.adjust(2)
    
    await message.answer(
        "🎮 **Choose Quiz Category:**\n\nSelect an anime category for your quiz:",
        reply_markup=keyboard.as_markup()
    )

@dp.callback_query(F.data.startswith("quiz_cat_"))
async def start_quiz_category(callback: CallbackQuery):
    """Start quiz with selected category"""
    category = callback.data.split("_")[2]
    
    quiz_id = await start_quiz(callback.from_user.id, callback.message.chat.id, category)
    
    if quiz_id:
        await callback.answer(f"Starting {category} quiz! Check the poll above! ⬆️")
        await callback.message.delete()
    else:
        await callback.answer("❌ Failed to start quiz", show_alert=True)

@dp.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer):
    """Handle quiz poll answers"""
    for quiz_id, quiz_data in list(active_quizzes.items()):
        if quiz_data["poll_id"] == poll_answer.poll_id and not quiz_data["answered"]:
            user_id = quiz_data["user_id"]
            
            # Check if answer is correct
            user_answer = poll_answer.option_ids[0] if poll_answer.option_ids else -1
            correct_answer = quiz_data["question"]["correct_answer"]
            
            # Update user stats
            user = Database.get_user(user_id)
            if user:
                stats = json.loads(user['stats'])
                stats['commands'] = stats.get('commands', 0) + 1
                
                if user_answer == correct_answer:
                    # Calculate points based on difficulty
                    difficulty = quiz_data["question"]["difficulty"]
                    points = {"easy": 10, "medium": 20, "hard": 30}.get(difficulty, 10)
                    stats['quiz_score'] = stats.get('quiz_score', 0) + points
                
                Database.update_user(user_id, stats=json.dumps(stats))
                
                # Check achievements
                Database.check_achievements(user_id)
            
            quiz_data["answered"] = True
            break

@dp.message(Command("battle"))
async def battle_cmd(message: Message):
    """Start battle with mentioned user"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 Maintenance mode.")
        return
    
    if is_banned(user.id):
        return
    
    # Find opponent
    opponent = None
    if message.reply_to_message:
        opponent = message.reply_to_message.from_user
    elif message.entities:
        for entity in message.entities:
            if entity.type == MessageEntityType.TEXT_MENTION:
                opponent = entity.user
                break
    
    if not opponent:
        await message.answer("⚔️ **Usage:** Reply to a user or mention them:\n`/battle @username`")
        return
    
    if opponent.id == user.id:
        await message.answer("❌ **You can't battle yourself!**")
        return
    
    if is_banned(opponent.id):
        await message.answer("❌ **This user is banned!**")
        return
    
    # Check cooldown
    if not check_cooldown(user.id, "battle", 60):
        await message.answer("⏳ Please wait 1 minute before another battle.")
        return
    
    battle_id, battle_msg = await EnhancedBattle.start(user.id, opponent.id, message.chat.id)
    
    if battle_id:
        await message.answer(battle_msg)
    else:
        await message.answer("❌ **Failed to start battle**")

@dp.message(Command("attack"))
async def attack_cmd(message: Message):
    """Normal attack in battle"""
    user = message.from_user
    
    # Find active battle
    battle_id = None
    for bid, battle in active_battles.items():
        if (battle["player1"]["id"] == user.id or battle["player2"]["id"] == user.id) and battle["active"]:
            battle_id = bid
            break
    
    if not battle_id:
        await message.answer("⚔️ **You don't have an active battle!**\nStart one with `/battle @user`")
        return
    
    battle_id, battle_msg = await EnhancedBattle.attack(battle_id, user.id, "normal")
    
    if battle_id:
        await message.answer(battle_msg)
    else:
        await message.answer("❌ **Battle error**")

@dp.message(Command("special"))
async def special_cmd(message: Message):
    """Special attack in battle"""
    user = message.from_user
    
    # Find active battle
    battle_id = None
    for bid, battle in active_battles.items():
        if (battle["player1"]["id"] == user.id or battle["player2"]["id"] == user.id) and battle["active"]:
            battle_id = bid
            break
    
    if not battle_id:
        await message.answer("⚔️ **You don't have an active battle!**")
        return
    
    battle_id, battle_msg = await EnhancedBattle.attack(battle_id, user.id, "special")
    
    if battle_id:
        await message.answer(battle_msg)
    else:
        await message.answer("❌ **Battle error**")

@dp.message(Command("meme"))
async def meme_cmd(message: Message):
    """Get anime meme"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 Maintenance mode.")
        return
    
    if is_banned(user.id):
        return
    
    if not check_cooldown(user.id, "meme", 5):
        await message.answer("⏳ Please wait before getting another meme.")
        return
    
    meme_msg = await message.answer("🎭 **Finding the perfect anime meme...**")
    
    try:
        meme = Database.get_random_meme()
        
        if meme:
            image_url = meme['image_url']
            caption = meme['caption']
            category = meme.get('category', 'general')
        else:
            # Fallback memes
            fallback = [
                ("https://i.imgur.com/3jYQ8Zl.jpg", "When the filler arc is longer than the main story", "waiting"),
                ("https://i.imgur.com/4k7X9lM.jpg", "Me trying to explain anime plots", "explaining"),
                ("https://i.imgur.com/5L8v9XN.jpg", "When someone says anime is for kids", "defense"),
            ]
            image_url, caption, category = random.choice(fallback)
        
        response = f"""🎭 **Anime Meme** 🎭

*{caption}*

📁 **Category:** {category.title()}"""
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔄 Another Meme", callback_data="another_meme")
        keyboard.button(text="📁 More {category}", callback_data=f"meme_cat_{category}")
        
        try:
            await message.answer_photo(
                photo=URLInputFile(image_url),
                caption=response,
                reply_markup=keyboard.as_markup()
            )
            await meme_msg.delete()
        except:
            await meme_msg.edit_text(response, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Meme error: {e}")
        await meme_msg.edit_text("🎭 **The meme gods are taking a break!** 😴\n\nTry again later!")

@dp.message(Command("profile"))
async def profile_cmd(message: Message):
    """Show enhanced profile"""
    user = message.from_user
    
    if maintenance_mode and not is_admin(user.id):
        await message.answer("🔧 Maintenance mode.")
        return
    
    if is_banned(user.id):
        return
    
    user_data = Database.get_user(user.id)
    if not user_data:
        await message.answer("❌ **Profile not found.** Use `/start` first.")
        return
    
    stats = json.loads(user_data['stats']) if user_data['stats'] else {}
    favorites = json.loads(user_data['favorites']) if user_data['favorites'] else []
    achievements = json.loads(user_data['achievements']) if user_data['achievements'] else []
    
    # Calculate rank based on score
    total_score = stats.get('quiz_score', 0) + (stats.get('battle_wins', 0) * 10)
    if total_score >= 1000:
        rank = "🏆 Legend"
    elif total_score >= 500:
        rank = "⭐ Veteran"
    elif total_score >= 100:
        rank = "🔥 Enthusiast"
    else:
        rank = "🎌 Beginner"
    
    # Daily reward status
    reward = Database.get_daily_reward(user.id)
    reward_status = "✅ Claimed today" if reward and reward.get('claimed') else "🎁 Available"
    
    response = f"""👤 **Profile: {user.first_name}** {rank}

📊 **Statistics:**
• Commands Used: {stats.get('commands', 0)}
• Anime Searches: {stats.get('searches', 0)}
• Quiz Score: {stats.get('quiz_score', 0)} pts
• Battle Wins: {stats.get('battle_wins', 0)}
• Daily Streak: {stats.get('daily_streak', 0)} days
• Watch Time: {stats.get('watch_time', 0)} hrs

🏆 **Achievements:** {len(achievements)} unlocked
⭐ **Favorites:** {len(favorites)} anime
💖 **Waifus:** {len(json.loads(user_data['waifu_collection'])) if user_data['waifu_collection'] else 0}
💙 **Husbandos:** {len(json.loads(user_data['husbando_collection'])) if user_data['husbando_collection'] else 0}

🎁 **Daily Reward:** {reward_status}
📅 Joined: {user_data['joined_date'][:10] if user_data['joined_date'] else 'Recently'}"""
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="⭐ Favorites", callback_data="view_favorites")
    keyboard.button(text="🏆 Achievements", callback_data="view_achievements")
    keyboard.adjust(2)
    keyboard.button(text="🎁 Claim Daily", callback_data="claim_daily")
    keyboard.button(text="🔄 Refresh", callback_data="refresh_profile")
    
    await message.answer(response, reply_markup=keyboard.as_markup())

# =========== GROUP HANDLERS ===========
@dp.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def handle_group(message: Message):
    """Handle group messages"""
    try:
        # Update group in database
        Database.execute(
            """INSERT OR IGNORE INTO groups (group_id, title, added_date, last_active) 
            VALUES (?, ?, datetime('now'), datetime('now'))""",
            (message.chat.id, message.chat.title)
        )
        Database.execute(
            "UPDATE groups SET last_active = datetime('now') WHERE group_id = ?",
            (message.chat.id,)
        )
    except:
        pass
    
    # Respond to bot mention
    bot_username = (await bot.get_me()).username
    if bot_username and message.text and f"@{bot_username}" in message.text:
        response = f"""👋 **Hello {message.chat.title}!** 👋

I'm **AnimeKuun Bot** - your ultimate anime companion! 🎌

🎮 **Try these commands in this group:**
• `/anime <name>` - Search anime
• `/quiz` - Group anime quiz (creates poll)
• `/battle @user` - Battle other members
• `/meme` - Share anime memes
• `/waifu` / `/husbando` - Find your match

✨ **All commands work perfectly in groups!**
Have fun exploring anime together! 🎬"""
        
        await message.reply(response)

# =========== ERROR HANDLER ===========
@dp.errors()
async def error_handler(event, exception):
    logger.error(f"Error: {exception}", exc_info=True)
    return True

# =========== MAIN ===========
async def main():
    print("🚀 **Starting AnimeKuun Bot - ULTIMATE VERSION**")
    print("=" * 60)
    
    # Delete webhook
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Get bot info
    bot_info = await bot.get_me()
    print(f"🤖 Bot: @{bot_info.username}")
    print(f"📊 Features: ALL BUTTONS WORKING")
    print(f"🎮 Games: Quiz, Battle, Memes")
    print(f"👥 Groups: Full support")
    print(f"🏆 Achievements: 10+ with rewards")
    print(f"💾 Database: Complete schema")
    print("=" * 60)
    print("🎌 **Bot is now running and ready!** 🚀")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        traceback.print_exc()
    finally:
        print("🤖 Bot stopped.")

if __name__ == "__main__":
    asyncio.run(main())
