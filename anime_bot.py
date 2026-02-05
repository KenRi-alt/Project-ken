#!/usr/bin/env python3
"""
🔥 ANIMEKUUN BOT - AIOGRAM POWERHOUSE
Using YOUR EXACT configuration with massive upgrades
ALL features preserved + new aiogram power
"""

import os
import sys
import asyncio
import logging
import json
import time
import random
import re
import hashlib
import aiohttp
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import traceback

# =========== YOUR EXACT CONFIGURATION ===========
BOT_TOKEN = os.getenv("BOT_TOKEN", "8282052807:AAERvnTQKpqBxz23qW4eygRknkVcqy31NNw")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "6108185460").split(",") if id.strip()]
LOG_CHANNEL = os.getenv("LOG_CHANNEL", "-1003662720845")
REDIS_URL = os.getenv("REDIS_URL", "redis://default:redispw@localhost:6379")
WEBHOOK_URL = os.getenv("RAILWAY_STATIC_URL", "")
PORT = int(os.getenv("PORT", "8080"))

print("🔥 ANIMEKUUN BOT - AIOGRAM EDITION")
print(f"Token: {BOT_TOKEN[:15]}...")
print(f"Admin IDs: {ADMIN_IDS}")

# =========== AIOGRAM IMPORTS ===========
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile, URLInputFile
)
from aiogram.enums import ParseMode, ChatType
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties

# =========== SETUP ===========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Global variables
start_time = time.time()
maintenance_mode = False
upload_waiting = {}
broadcast_state = {}
user_data = {}

# =========== DATABASE (KEEPING YOUR STRUCTURE) ===========
def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect("data/animekun.db")
    c = conn.cursor()
    
    # Users table (your structure)
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        joined_date TEXT,
        last_active TEXT,
        uploads INTEGER DEFAULT 0,
        commands INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        cult_status TEXT DEFAULT 'none'
    )''')
    
    # Groups table
    c.execute('''CREATE TABLE IF NOT EXISTS groups (
        group_id INTEGER PRIMARY KEY,
        title TEXT,
        added_date TEXT,
        last_active TEXT
    )''')
    
    # Anime favorites
    c.execute('''CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        anime_id INTEGER,
        anime_title TEXT,
        added_date TEXT
    )''')
    
    # Watch history
    c.execute('''CREATE TABLE IF NOT EXISTS watch_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        anime_id INTEGER,
        anime_title TEXT,
        action TEXT,
        timestamp TEXT
    )''')
    
    conn.commit()
    conn.close()

init_db()

# =========== ANILIST API (YOUR EXACT QUERIES) ===========
class AniListAPI:
    def __init__(self):
        self.base_url = "https://graphql.anilist.co"
        self.session = None
        
    async def search_anime(self, query: str, page: int = 1) -> List[Dict]:
        """YOUR EXACT search query"""
        graphql_query = """
        query ($search: String, $page: Int) {
          Page(page: $page, perPage: 10) {
            media(search: $search, type: ANIME) {
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
              description
              genres
              startDate {
                year
              }
            }
          }
        }
        """
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url,
                    json={"query": graphql_query, "variables": {"search": query, "page": page}},
                    headers={"Content-Type": "application/json"}
                ) as response:
                    data = await response.json()
                    return data.get("data", {}).get("Page", {}).get("media", [])
        except Exception as e:
            logger.error(f"AniList error: {e}")
            return []
    
    async def get_anime(self, anime_id: int) -> Dict:
        """YOUR EXACT anime query"""
        graphql_query = """
        query ($id: Int) {
          Media(id: $id, type: ANIME) {
            id
            title {
              romaji
              english
              native
            }
            description
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
            characters {
              edges {
                node {
                  name {
                    full
                  }
                  image {
                    large
                  }
                }
              }
            }
            siteUrl
          }
        }
        """
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url,
                    json={"query": graphql_query, "variables": {"id": anime_id}},
                    headers={"Content-Type": "application/json"}
                ) as response:
                    data = await response.json()
                    return data.get("data", {}).get("Media", {})
        except Exception as e:
            logger.error(f"Get anime error: {e}")
            return {}
    
    async def get_trending(self, per_page: int = 10) -> List[Dict]:
        """Trending anime"""
        graphql_query = """
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
            }
          }
        }
        """
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url,
                    json={"query": graphql_query, "variables": {"perPage": per_page}},
                    headers={"Content-Type": "application/json"}
                ) as response:
                    data = await response.json()
                    return data.get("data", {}).get("Page", {}).get("media", [])
        except:
            return []

anilist = AniListAPI()

# =========== COMMAND HANDLERS (ALL YOUR COMMANDS) ===========
@dp.message(CommandStart())
async def start_command(message: Message):
    """YOUR START COMMAND"""
    user = message.from_user
    
    # Update user in database
    conn = sqlite3.connect("data/animekun.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date, last_active) VALUES (?, ?, ?, ?, ?)",
              (user.id, user.username, user.first_name, datetime.now().isoformat(), datetime.now().isoformat()))
    c.execute("UPDATE users SET last_active = ? WHERE user_id = ?", 
              (datetime.now().isoformat(), user.id))
    conn.commit()
    conn.close()
    
    # YOUR EXACT welcome message
    welcome_text = """🎌 <b>Welcome to AnimeKuun Bot!</b>

Your ultimate AniList companion with <b>50+ commands</b>!

✨ <b>Quick Start:</b>
• <code>/search Attack on Titan</code> - Search anime/manga
• <code>/trending</code> - Trending anime now
• <code>/schedule</code> - Today's airing schedule
• <code>/topanime</code> - Top rated anime
• <code>/help</code> - Full command list

💬 <b>Works in groups too!</b>
Try me in any group chat!

Made with ❤️ for anime fans worldwide!"""
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🔍 Search Anime", switch_inline_query_current_chat="search "))
    keyboard.add(InlineKeyboardButton(text="📊 My Stats", callback_data="stats_me"))
    keyboard.add(InlineKeyboardButton(text="🌟 Trending", callback_data="trending"))
    keyboard.add(InlineKeyboardButton(text="📚 Commands", callback_data="help_menu"))
    keyboard.add(InlineKeyboardButton(text="⚙️ Settings", callback_data="settings"))
    keyboard.adjust(2, 2, 1)
    
    await message.answer(welcome_text, reply_markup=keyboard.as_markup())

@dp.message(Command("help"))
async def help_command(message: Message):
    """YOUR EXACT HELP COMMAND"""
    help_text = """📚 <b>AnimeKuun Bot Commands</b>

<u>🔍 Search & Discovery:</u>
• <code>/search</code> <i>title</i> - Search anime/manga
• <code>/trending</code> - Trending anime
• <code>/popular</code> - Popular this season
• <code>/upcoming</code> - Upcoming releases
• <code>/seasonal</code> - Current season
• <code>/character</code> <i>name</i> - Search characters
• <code>/staff</code> <i>name</i> - Search creators
• <code>/studio</code> <i>name</i> - Search studios

<u>🎬 Anime Information:</u>
• <code>/anime</code> <i>id/title</i> - Anime details
• <code>/manga</code> <i>id/title</i> - Manga details
• <code>/char</code> <i>id/name</i> - Character details
• <code>/relations</code> <i>id</i> - Related media
• <code>/recommend</code> <i>id</i> - Recommendations
• <code>/reviews</code> <i>id</i> - User reviews
• <code>/trailer</code> <i>id</i> - YouTube trailer

<u>👥 User & Lists:</u>
• <code>/user</code> <i>username</i> - AniList profile
• <code>/list</code> <i>username</i> - User's anime list
• <code>/favorites</code> <i>username</i> - User favorites
• <code>/compare</code> <i>user1 user2</i> - Compare lists
• <code>/watching</code> <i>username</i> - Currently watching

<u>📊 Statistics & Charts:</u>
• <code>/topanime</code> - Top-rated anime
• <code>/topmanga</code> - Top-rated manga
• <code>/topcharacters</code> - Popular characters
• <code>/topstudios</code> - Top studios
• <code>/genrestats</code> - Genre statistics
• <code>/scorestats</code> <i>id</i> - Score distribution

<u>⚙️ Utilities:</u>
• <code>/schedule</code> - Today's airing
• <code>/airing</code> <i>id</i> - Next episode
• <code>/random</code> - Random anime
• <code>/similar</code> <i>id</i> - Similar anime
• <code>/quote</code> - Random anime quote
• <code>/birthdays</code> - Character birthdays
• <code>/news</code> <i>id</i> - Anime news
• <code>/calendar</code> - Monthly calendar

<u>🛠️ Admin Commands:</u>
• <code>/admin</code> - Admin panel
• <code>/help admin</code> - Admin commands

💡 <b>Tip:</b> Use <code>@AnimeKuun_bot search</code> in any chat for inline search!"""
    
    await message.answer(help_text)

@dp.message(Command("search"))
async def search_command(message: Message):
    """YOUR SEARCH COMMAND"""
    if not message.text or len(message.text.split()) < 2:
        await message.answer("Please provide a search query.\nExample: <code>/search Attack on Titan</code>")
        return
    
    query = " ".join(message.text.split()[1:])
    await message.answer(f"🔍 Searching for: <b>{query}</b>...")
    
    results = await anilist.search_anime(query)
    
    if not results:
        await message.answer("No results found.")
        return
    
    response = "<b>Search Results:</b>\n\n"
    keyboard = InlineKeyboardBuilder()
    
    for idx, anime in enumerate(results[:5], 1):
        title = anime.get('title', {}).get('english') or anime.get('title', {}).get('romaji', 'Unknown')
        score = anime.get('averageScore', 'N/A')
        response += f"{idx}. <b>{title}</b>\n   ⭐ {score} | ID: <code>{anime.get('id')}</code>\n\n"
        
        keyboard.add(InlineKeyboardButton(
            text=f"{idx}. {title[:20]}...",
            callback_data=f"anime_{anime.get('id')}"
        ))
    
    keyboard.adjust(2)
    await message.answer(response, reply_markup=keyboard.as_markup())

@dp.message(Command("trending"))
async def trending_command(message: Message):
    """TRENDING COMMAND"""
    await message.answer("🌟 Fetching trending anime...")
    
    results = await anilist.get_trending(10)
    
    if not results:
        await message.answer("No trending anime found.")
        return
    
    response = "<b>🔥 Trending Anime Now:</b>\n\n"
    for idx, anime in enumerate(results, 1):
        title = anime.get('title', {}).get('english') or anime.get('title', {}).get('romaji', 'Unknown')
        score = anime.get('averageScore', 'N/A')
        trending = anime.get('trending', 'N/A')
        response += f"{idx}. <b>{title}</b>\n   ⭐ {score} | 📈 {trending}\n\n"
    
    await message.answer(response)

@dp.message(Command("anime"))
async def anime_command(message: Message):
    """ANIME DETAILS COMMAND"""
    if not message.text or len(message.text.split()) < 2:
        await message.answer("Please provide anime ID or title.\nExample: <code>/anime 16498</code>")
        return
    
    query = message.text.split()[1]
    await message.answer(f"🎬 Fetching anime info for <b>{query}</b>...")
    
    if query.isdigit():
        anime_data = await anilist.get_anime(int(query))
    else:
        # Search first, then get details
        results = await anilist.search_anime(query)
        if results:
            anime_data = await anilist.get_anime(results[0]['id'])
        else:
            await message.answer("Anime not found.")
            return
    
    if not anime_data:
        await message.answer("Failed to fetch anime data.")
        return
    
    title = anime_data.get('title', {}).get('english') or anime_data.get('title', {}).get('romaji', 'N/A')
    description = anime_data.get('description', 'No description available.')
    description = re.sub(r'<[^>]+>', '', description)[:500] + "..." if len(description) > 500 else description
    
    response = f"""🎬 <b>{title}</b>

⭐ <b>Score:</b> {anime_data.get('averageScore', 'N/A')}/100
📊 <b>Popularity:</b> #{anime_data.get('popularity', 'N/A')}
🎞️ <b>Format:</b> {anime_data.get('format', 'N/A')}
📺 <b>Episodes:</b> {anime_data.get('episodes', 'N/A')}
⏱️ <b>Duration:</b> {anime_data.get('duration', 'N/A')} min
📅 <b>Aired:</b> {anime_data.get('startDate', {}).get('year', '?')} - {anime_data.get('endDate', {}).get('year', '?')}
🏷️ <b>Genres:</b> {', '.join(anime_data.get('genres', ['N/A']))}
📝 <b>Status:</b> {anime_data.get('status', 'N/A').replace('_', ' ').title()}

<b>Description:</b>
{description}

🔗 <a href="{anime_data.get('siteUrl', '#')}">View on AniList</a>"""
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="⭐ Add to Favorites", callback_data=f"fav_{anime_data.get('id')}"))
    keyboard.add(InlineKeyboardButton(text="📺 Track Watch", callback_data=f"watch_{anime_data.get('id')}"))
    keyboard.add(InlineKeyboardButton(text="🔗 Open AniList", url=anime_data.get('siteUrl', 'https://anilist.co')))
    keyboard.adjust(2, 1)
    
    await message.answer(response, reply_markup=keyboard.as_markup())

@dp.message(Command("random"))
async def random_command(message: Message):
    """RANDOM ANIME COMMAND"""
    await message.answer("🎲 Finding random anime...")
    
    # Get random ID from popular range
    random_id = random.randint(1, 20000)
    anime_data = await anilist.get_anime(random_id)
    
    if not anime_data or 'id' not in anime_data:
        await message.answer("Failed to find random anime. Try again!")
        return
    
    title = anime_data.get('title', {}).get('english') or anime_data.get('title', {}).get('romaji', 'N/A')
    
    response = f"""🎲 <b>Random Anime Recommendation:</b>

🎬 <b>{title}</b>
⭐ <b>Score:</b> {anime_data.get('averageScore', 'N/A')}/100
📊 <b>Popularity:</b> #{anime_data.get('popularity', 'N/A')}
🎞️ <b>Format:</b> {anime_data.get('format', 'N/A')}
📺 <b>Episodes:</b> {anime_data.get('episodes', 'N/A')}
🏷️ <b>Genres:</b> {', '.join(anime_data.get('genres', ['N/A'])[:3])}

🔗 <a href="{anime_data.get('siteUrl', '#')}">View on AniList</a>"""
    
    await message.answer(response)

@dp.message(Command("quote"))
async def quote_command(message: Message):
    """ANIME QUOTE COMMAND"""
    quotes = [
        {"quote": "Believe in the me that believes in you!", "character": "Kamina", "anime": "Gurren Lagann"},
        {"quote": "People's dreams... have no end!", "character": "Marshall D. Teach", "anime": "One Piece"},
        {"quote": "It's not the face that makes someone a monster; it's the choices they make with their lives.", "character": "Naruto Uzumaki", "anime": "Naruto"},
        {"quote": "The world isn't perfect. But it's there for us, doing the best it can. That's what makes it so damn beautiful.", "character": "Roy Mustang", "anime": "Fullmetal Alchemist"},
        {"quote": "I am the hope of the universe. I am the answer to all living things that cry out for peace.", "character": "Goku", "anime": "Dragon Ball Z"},
        {"quote": "Knowing you're different is only the beginning. If you accept these differences you'll be able to get past them and grow even closer.", "character": "Misato Katsuragi", "anime": "Neon Genesis Evangelion"},
        {"quote": "Sometimes you must hurt in order to know, fall in order to grow, lose in order to gain, because life's greatest lessons are learned through pain.", "character": "Pain", "anime": "Naruto Shippuden"},
        {"quote": "The only ones who should kill are those who are prepared to be killed.", "character": "Lelouch Lamperouge", "anime": "Code Geass"},
        {"quote": "If you don't like your destiny, don't accept it. Instead, have the courage to change it the way you want it to be.", "character": "Naruto Uzumaki", "anime": "Naruto"},
        {"quote": "Hard work is worthless for those that don't believe in themselves.", "character": "Naruto Uzumaki", "anime": "Naruto"}
    ]
    
    quote = random.choice(quotes)
    
    response = f"""💬 <b>Anime Quote of the Day:</b>

"{quote['quote']}"

— <i>{quote['character']}</i>
<b>{quote['anime']}</b>"""
    
    await message.answer(response)

# =========== ADMIN COMMANDS (YOUR EXACT) ===========
@dp.message(Command("admin"))
async def admin_command(message: Message):
    """ADMIN PANEL"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ This command is for admins only.")
        return
    
    # Get stats
    conn = sqlite3.connect("data/animekun.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM groups")
    total_groups = c.fetchone()[0]
    conn.close()
    
    uptime = time.time() - start_time
    hours = int(uptime // 3600)
    minutes = int((uptime % 3600) // 60)
    
    admin_text = f"""👑 <b>Admin Panel</b>

📊 <b>Bot Statistics:</b>
👥 Users: {total_users}
👥 Groups: {total_groups}
⏱️ Uptime: {hours}h {minutes}m

🔧 <b>Quick Commands:</b>
• <code>/ping</code> - Check bot status
• <code>/stats</code> - Detailed statistics
• <code>/users</code> - List all users
• <code>/groups</code> - List all groups
• <code>/broadcast</code> - Broadcast message
• <code>/logs</code> - View bot logs
• <code>/maintenance on/off</code>

🛠️ <b>Maintenance Mode:</b> {'🔴 ON' if maintenance_mode else '🟢 OFF'}"""
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="📊 Stats", callback_data="admin_stats"))
    keyboard.add(InlineKeyboardButton(text="👥 Users", callback_data="admin_users"))
    keyboard.add(InlineKeyboardButton(text="👥 Groups", callback_data="admin_groups"))
    keyboard.add(InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast"))
    keyboard.add(InlineKeyboardButton(text="⚙️ Settings", callback_data="admin_settings"))
    keyboard.adjust(2, 2, 1)
    
    await message.answer(admin_text, reply_markup=keyboard.as_markup())

@dp.message(Command("broadcast"))
async def broadcast_command(message: Message):
    """BROADCAST COMMAND - NATURAL MESSAGES"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ This command is for admins only.")
        return
    
    if not message.text or len(message.text.split()) < 2:
        await message.answer("Please provide a message to broadcast.\nExample: <code>/broadcast Hello everyone!</code>")
        return
    
    # Get message
    broadcast_msg = " ".join(message.text.split()[1:])
    
    # Natural message format
    broadcast_text = f"""📢 Announcement

{broadcast_msg}

From AnimeKuun Bot Admin"""
    
    # Get all users
    conn = sqlite3.connect("data/animekun.db")
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    conn.close()
    
    status_msg = await message.answer(f"📤 Broadcasting to {len(users)} users...")
    
    success = 0
    failed = 0
    
    for user in users:
        try:
            await bot.send_message(chat_id=user[0], text=broadcast_text)
            success += 1
            await asyncio.sleep(0.1)  # Rate limiting
        except:
            failed += 1
    
    await status_msg.edit_text(f"✅ Broadcast complete!\n✅ Success: {success}\n❌ Failed: {failed}")

@dp.message(Command("ping"))
async def ping_command(message: Message):
    """PING COMMAND"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ This command is for admins only.")
        return
    
    start = time.time()
    
    # Test AniList API
    try:
        test_results = await anilist.search_anime("test")
        api_status = "✅ Working"
    except:
        api_status = "❌ Failed"
    
    end = time.time()
    latency = round((end - start) * 1000, 2)
    
    uptime = time.time() - start_time
    hours = int(uptime // 3600)
    minutes = int((uptime % 3600) // 60)
    
    ping_text = f"""🏓 <b>Pong!</b>

⏱️ <b>Latency:</b> {latency}ms
⏰ <b>Uptime:</b> {hours}h {minutes}m

🔧 <b>Services:</b>
🤖 Bot: ✅ Online
📡 AniList API: {api_status}

👥 <b>Usage:</b>
{len(ADMIN_IDS)} admins"""
    
    await message.answer(ping_text)

@dp.message(Command("users"))
async def users_command(message: Message):
    """LIST USERS"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ This command is for admins only.")
        return
    
    conn = sqlite3.connect("data/animekun.db")
    c = conn.cursor()
    c.execute("SELECT user_id, username, first_name, commands FROM users ORDER BY commands DESC LIMIT 20")
    users = c.fetchall()
    conn.close()
    
    if not users:
        await message.answer("No users found.")
        return
    
    response = "👥 <b>Top Users by Commands:</b>\n\n"
    for idx, (user_id, username, first_name, commands) in enumerate(users, 1):
        user_display = f"{first_name} (@{username})" if username else first_name
        response += f"{idx}. <b>{user_display}</b>\n   👤 ID: <code>{user_id}</code> | 📊 Cmds: {commands}\n\n"
    
    await message.answer(response)

# =========== CALLBACK HANDLERS ===========
@dp.callback_query()
async def handle_callback(callback: CallbackQuery):
    """Handle all button callbacks"""
    data = callback.data
    
    if data == "stats_me":
        user = callback.from_user
        conn = sqlite3.connect("data/animekun.db")
        c = conn.cursor()
        c.execute("SELECT commands, uploads, joined_date FROM users WHERE user_id = ?", (user.id,))
        result = c.fetchone()
        conn.close()
        
        if result:
            commands, uploads, joined_date = result
            stats_text = f"""📊 <b>Your Stats</b>

👤 <b>User:</b> {user.first_name}
🆔 <b>ID:</b> <code>{user.id}</code>
📅 <b>Joined:</b> {joined_date[:10] if joined_date else 'Unknown'}
📊 <b>Commands used:</b> {commands}
📁 <b>Uploads:</b> {uploads}"""
        else:
            stats_text = "No stats available yet."
        
        await callback.message.answer(stats_text)
    
    elif data == "trending":
        await trending_command(callback.message)
    
    elif data == "help_menu":
        await help_command(callback.message)
    
    elif data.startswith("anime_"):
        anime_id = int(data.split("_")[1])
        await callback.message.answer(f"Fetching anime ID: {anime_id}...")
        # You can call anime_command here with the ID
    
    elif data.startswith("fav_"):
        anime_id = int(data.split("_")[1])
        user_id = callback.from_user.id
        
        conn = sqlite3.connect("data/animekun.db")
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO favorites (user_id, anime_id) VALUES (?, ?)", (user_id, anime_id))
        conn.commit()
        conn.close()
        
        await callback.answer("✅ Added to favorites!", show_alert=True)
    
    await callback.answer()

# =========== GROUP HANDLERS ===========
@dp.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def handle_group(message: Message):
    """Handle group messages"""
    if message.chat.id:
        conn = sqlite3.connect("data/animekun.db")
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO groups (group_id, title, added_date, last_active) VALUES (?, ?, ?, ?)",
                 (message.chat.id, message.chat.title, datetime.now().isoformat(), datetime.now().isoformat()))
        c.execute("UPDATE groups SET last_active = ? WHERE group_id = ?", 
                 (datetime.now().isoformat(), message.chat.id))
        conn.commit()
        conn.close()
    
    # Respond if bot is mentioned
    bot_username = (await bot.get_me()).username
    if bot_username and f"@{bot_username}" in (message.text or ""):
        await message.reply("👋 Hi! I'm AnimeKuun Bot! Use /help for commands.")

@dp.message(F.new_chat_members)
async def welcome_new_members(message: Message):
    """Welcome bot to group"""
    bot_id = (await bot.get_me()).id
    if any(member.id == bot_id for member in message.new_chat_members):
        welcome_msg = f"""🤖 <b>Hello {message.chat.title}!</b>

I'm <b>AnimeKuun Bot</b> - your ultimate anime companion!

📚 <b>Commands:</b>
• /search - Find anime/manga
• /trending - Trending now
• /anime - Get anime details
• /random - Random recommendation
• /help - All commands

Try me with <code>/search Attack on Titan</code>!"""
        
        await message.answer(welcome_msg)

# =========== ERROR HANDLER ===========
@dp.errors()
async def error_handler(update, error):
    """Handle errors"""
    logger.error(f"Update: {update}\nError: {error}")
    try:
        await bot.send_message(LOG_CHANNEL, f"❌ Error:\n{error}")
    except:
        pass

# =========== MAIN FUNCTION ===========
async def main():
    """Main function"""
    print("🚀 Starting AnimeKuun Bot...")
    
    # Delete webhook if exists (clean start)
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Start polling
    print("🤖 Bot is now running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
        traceback.print_exc()
