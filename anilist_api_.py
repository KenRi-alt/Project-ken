#!/usr/bin/env python3
"""
🎌 AniList OAuth Handler & Image Processor
Handles OAuth callbacks and creates beautiful profile images
"""

import os
import sys
import json
import base64
import hashlib
import secrets
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import requests
from urllib.parse import urlencode, parse_qs

# Add parent directory to path
sys.path.append('..')

# Import database functions
from animekun_complete import Database, ANILIST_CLIENT_ID, ANILIST_CLIENT_SECRET

class AniListOAuth:
    """Handle AniList OAuth authentication"""
    
    def __init__(self):
        self.base_url = "https://anilist.co/api/v2"
        self.oauth_url = "https://anilist.co/api/v2/oauth/authorize"
        self.token_url = "https://anilist.co/api/v2/oauth/token"
        self.session = None
        self.callback_states = {}
    
    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self.session
    
    def generate_state_token(self, user_id: int) -> str:
        """Generate and store state token for OAuth"""
        state = secrets.token_urlsafe(32)
        self.callback_states[state] = {
            "user_id": user_id,
            "created_at": datetime.now().timestamp(),
            "used": False
        }
        return state
    
    def validate_state_token(self, state: str) -> Optional[int]:
        """Validate state token and return user_id"""
        if state not in self.callback_states:
            return None
        
        state_data = self.callback_states[state]
        
        # Check if expired (5 minutes)
        if datetime.now().timestamp() - state_data["created_at"] > 300:
            del self.callback_states[state]
            return None
        
        # Check if already used
        if state_data["used"]:
            del self.callback_states[state]
            return None
        
        # Mark as used
        state_data["used"] = True
        user_id = state_data["user_id"]
        
        # Clean up old states
        self._cleanup_states()
        
        return user_id
    
    def _cleanup_states(self):
        """Clean up expired states"""
        current_time = datetime.now().timestamp()
        expired_states = []
        
        for state, data in self.callback_states.items():
            if current_time - data["created_at"] > 300:  # 5 minutes
                expired_states.append(state)
        
        for state in expired_states:
            del self.callback_states[state]
    
    async def get_authorization_url(self, user_id: int, redirect_uri: str) -> str:
        """Generate OAuth authorization URL"""
        state = self.generate_state_token(user_id)
        
        params = {
            "client_id": ANILIST_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state
        }
        
        return f"{self.oauth_url}?{urlencode(params)}"
    
    async def exchange_code_for_token(self, code: str) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for access token"""
        session = await self._get_session()
        
        data = {
            "grant_type": "authorization_code",
            "client_id": ANILIST_CLIENT_ID,
            "client_secret": ANILIST_CLIENT_SECRET,
            "redirect_uri": "https://t.me/animekun_bot",  # Your bot's redirect URI
            "code": code
        }
        
        try:
            async with session.post(self.token_url, data=data) as response:
                if response.status == 200:
                    token_data = await response.json()
                    return token_data
                else:
                    error_text = await response.text()
                    print(f"Token exchange failed: {response.status} - {error_text}")
                    return None
        except Exception as e:
            print(f"Token exchange error: {e}")
            return None
    
    async def get_user_data(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Get user data using access token"""
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
        
        session = await self._get_session()
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            async with session.post(
                "https://graphql.anilist.co",
                json={"query": query},
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if "errors" in data:
                        print(f"AniList API error: {data['errors']}")
                        return None
                    return data.get("data", {}).get("Viewer", {})
                else:
                    print(f"Failed to get user data: {response.status}")
                    return None
        except Exception as e:
            print(f"Error getting user data: {e}")
            return None
    
    async def close(self):
        """Close session"""
        if self.session and not self.session.closed:
            await self.session.close()

class ImageGenerator:
    """Generate beautiful profile and info cards"""
    
    def __init__(self):
        self.font_cache = {}
        
    async def download_image(self, url: str) -> Optional[Image.Image]:
        """Download image from URL"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        return Image.open(io.BytesIO(image_data))
        except Exception as e:
            print(f"Error downloading image {url}: {e}")
            return None
    
    def get_font(self, size: int, bold: bool = False):
        """Get font with caching"""
        font_key = f"{size}_{bold}"
        
        if font_key not in self.font_cache:
            try:
                if bold:
                    font = ImageFont.truetype("arialbd.ttf", size)
                else:
                    font = ImageFont.truetype("arial.ttf", size)
            except:
                # Fallback to default font
                font = ImageFont.load_default()
            
            self.font_cache[font_key] = font
        
        return self.font_cache[font_key]
    
    def create_gradient_background(self, width: int, height: int, colors: list) -> Image.Image:
        """Create gradient background"""
        # Create base image
        base = Image.new('RGB', (width, height), colors[0])
        
        if len(colors) == 1:
            return base
        
        # Create gradient overlay
        gradient = Image.new('RGB', (width, height))
        draw = ImageDraw.Draw(gradient)
        
        # Draw gradient
        for i in range(height):
            ratio = i / height
            r = int(colors[0][0] * (1 - ratio) + colors[1][0] * ratio)
            g = int(colors[0][1] * (1 - ratio) + colors[1][1] * ratio)
            b = int(colors[0][2] * (1 - ratio) + colors[1][2] * ratio)
            draw.line([(0, i), (width, i)], fill=(r, g, b))
        
        return gradient
    
    def add_rounded_corners(self, image: Image.Image, radius: int = 20) -> Image.Image:
        """Add rounded corners to image"""
        if radius == 0:
            return image
        
        circle = Image.new('L', (radius * 2, radius * 2), 0)
        draw = ImageDraw.Draw(circle)
        draw.ellipse((0, 0, radius * 2, radius * 2), fill=255)
        
        alpha = Image.new('L', image.size, 255)
        w, h = image.size
        
        # Apply rounded corners
        alpha.paste(circle.crop((0, 0, radius, radius)), (0, 0))
        alpha.paste(circle.crop((radius, 0, radius * 2, radius)), (w - radius, 0))
        alpha.paste(circle.crop((0, radius, radius, radius * 2)), (0, h - radius))
        alpha.paste(circle.crop((radius, radius, radius * 2, radius * 2)), (w - radius, h - radius))
        
        image.putalpha(alpha)
        return image
    
    def add_shadow(self, image: Image.Image, offset: int = 5, shadow_color: tuple = (0, 0, 0, 100)) -> Image.Image:
        """Add shadow to image"""
        shadow = Image.new('RGBA', 
                          (image.width + offset * 2, image.height + offset * 2), 
                          (0, 0, 0, 0))
        
        # Create shadow
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rounded_rectangle(
            [offset, offset, image.width + offset, image.height + offset],
            radius=20,
            fill=shadow_color
        )
        
        # Composite images
        result = Image.alpha_composite(shadow, image)
        return result
    
    async def create_profile_card(self, user_data: dict, anilist_data: dict = None) -> Optional[bytes]:
        """Create beautiful profile card image"""
        try:
            # Image dimensions
            width, height = 1000, 700
            
            # Create gradient background
            bg_colors = [(30, 30, 46), (21, 101, 192)]  # Dark blue to light blue
            bg = self.create_gradient_background(width, height, bg_colors)
            
            # Add some decorative elements
            draw = ImageDraw.Draw(bg)
            
            # Draw anime-themed pattern
            for i in range(0, width, 50):
                draw.line([(i, 0), (i, height)], fill=(255, 255, 255, 10), width=1)
            for i in range(0, height, 50):
                draw.line([(0, i), (width, i)], fill=(255, 255, 255, 10), width=1)
            
            # Draw main content area
            content_bg = Image.new('RGBA', (width - 100, height - 100), (255, 255, 255, 230))
            content_bg = self.add_rounded_corners(content_bg, 30)
            content_bg = self.add_shadow(content_bg)
            
            # Composite content bg
            bg = Image.alpha_composite(bg.convert('RGBA'), content_bg)
            draw = ImageDraw.Draw(bg)
            
            # Get fonts
            title_font = self.get_font(48, bold=True)
            heading_font = self.get_font(32, bold=True)
            text_font = self.get_font(24)
            small_font = self.get_font(18)
            
            # Title
            username = user_data.get('username') or user_data.get('first_name', 'User')
            draw.text((width // 2, 60), f"👤 {username}", 
                     fill=(21, 101, 192), font=title_font, anchor="mm")
            
            # Draw divider
            draw.line([(100, 120), (width - 100, 120)], fill=(200, 200, 200), width=2)
            
            # User stats
            stats_y = 150
            stats = json.loads(user_data.get('stats', '{}'))
            
            stats_sections = [
                ("📊 Bot Statistics", [
                    f"Commands Used: {stats.get('commands_used', 0)}",
                    f"Daily Streak: {stats.get('daily_streak', 0)} days",
                    f"Quiz Score: {stats.get('quiz_score', 0)} points",
                    f"Battle Wins: {stats.get('battle_wins', 0)}",
                ]),
            ]
            
            # Add achievements if any
            achievements = Database.get_user_achievements(user_data['user_id'])
            if achievements:
                stats_sections.append(("🏆 Achievements", [f"Unlocked: {len(achievements)}"]))
            
            # Add AniList stats if available
            if anilist_data:
                anime_stats = anilist_data.get('statistics', {}).get('anime', {})
                stats_sections.append(("🎬 AniList Stats", [
                    f"Anime Count: {anime_stats.get('count', 0)}",
                    f"Mean Score: {anime_stats.get('meanScore', 0)}/100",
                    f"Days Watched: {anime_stats.get('minutesWatched', 0) // 1440}",
                    f"Episodes: {anime_stats.get('episodesWatched', 0):,}",
                ]))
            
            # Draw stats sections
            section_width = (width - 200) // len(stats_sections)
            
            for i, (section_title, section_items) in enumerate(stats_sections):
                x = 120 + i * section_width
                
                # Section title
                draw.text((x, stats_y), section_title, 
                         fill=(21, 101, 192), font=heading_font)
                
                # Section items
                for j, item in enumerate(section_items):
                    draw.text((x, stats_y + 50 + j * 35), item,
                             fill=(50, 50, 50), font=text_font)
            
            # Add avatar if available
            avatar_url = None
            if anilist_data and anilist_data.get('avatar'):
                avatar_url = anilist_data['avatar'].get('large')
            
            if avatar_url:
                try:
                    avatar_img = await self.download_image(avatar_url)
                    if avatar_img:
                        # Resize and make circular
                        avatar_size = 150
                        avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                        
                        # Create circular mask
                        mask = Image.new('L', (avatar_size, avatar_size), 0)
                        mask_draw = ImageDraw.Draw(mask)
                        mask_draw.ellipse([(0, 0), (avatar_size, avatar_size)], fill=255)
                        
                        avatar_img.putalpha(mask)
                        
                        # Add border
                        border = Image.new('RGBA', (avatar_size + 10, avatar_size + 10), (255, 255, 255, 0))
                        border_draw = ImageDraw.Draw(border)
                        border_draw.ellipse([(0, 0), (avatar_size + 10, avatar_size + 10)], 
                                          fill=(21, 101, 192, 200))
                        
                        # Composite avatar
                        border.paste(avatar_img, (5, 5), avatar_img)
                        
                        # Position avatar
                        bg.paste(border, (width - 200, 50), border)
                except Exception as e:
                    print(f"Error adding avatar: {e}")
            
            # Add decorative anime elements
            # Draw cherry blossoms
            for _ in range(10):
                x = random.randint(50, width - 50)
                y = random.randint(50, height - 50)
                size = random.randint(5, 15)
                draw.ellipse([(x, y), (x + size, y + size)], 
                           fill=(255, 182, 193, 100))  # Pink
            
            # Draw stars
            for _ in range(20):
                x = random.randint(50, width - 50)
                y = random.randint(50, height - 50)
                size = random.randint(2, 6)
                draw.rectangle([(x, y), (x + size, y + size)], 
                             fill=(255, 255, 255, 150))
            
            # Save to bytes
            img_bytes = io.BytesIO()
            bg.save(img_bytes, format='PNG', quality=95)
            img_bytes.seek(0)
            
            return img_bytes.getvalue()
            
        except Exception as e:
            print(f"Error creating profile card: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def create_anime_card(self, anime_data: dict) -> Optional[bytes]:
        """Create beautiful anime info card"""
        try:
            width, height = 900, 600
            
            # Get anime info
            title = anime_data.get('title', {}).get('english') or anime_data.get('title', {}).get('romaji', 'Unknown')
            score = anime_data.get('averageScore', 'N/A')
            episodes = anime_data.get('episodes', 'N/A')
            status = anime_data.get('status', 'N/A').replace('_', ' ').title()
            genres = ', '.join(anime_data.get('genres', [])[:5])
            description = anime_data.get('description', 'No description available.')
            
            # Clean description
            import re
            description = re.sub(r'<[^>]+>', '', description)
            if len(description) > 300:
                description = description[:300] + "..."
            
            # Create background
            bg = Image.new('RGB', (width, height), (30, 30, 46))
            draw = ImageDraw.Draw(bg)
            
            # Get fonts
            title_font = self.get_font(42, bold=True)
            header_font = self.get_font(28, bold=True)
            text_font = self.get_font(22)
            small_font = self.get_font(18)
            
            # Title
            draw.text((50, 30), title, fill=(255, 255, 255), font=title_font)
            
            # Draw info boxes
            info_y = 100
            info_items = [
                ("⭐ Score", str(score)),
                ("📺 Episodes", str(episodes)),
                ("📅 Status", status),
            ]
            
            box_width = 250
            box_height = 80
            box_spacing = 20
            
            for i, (label, value) in enumerate(info_items):
                x = 50 + i * (box_width + box_spacing)
                
                # Draw box
                draw.rounded_rectangle([(x, info_y), (x + box_width, info_y + box_height)], 
                                     radius=15, fill=(21, 101, 192))
                
                # Draw label and value
                draw.text((x + box_width//2, info_y + 25), label, 
                         fill=(255, 255, 255), font=small_font, anchor="mm")
                draw.text((x + box_width//2, info_y + 55), value, 
                         fill=(255, 255, 255), font=header_font, anchor="mm")
            
            # Genres
            genres_y = info_y + box_height + 30
            draw.text((50, genres_y), "🏷️ Genres:", fill=(200, 200, 200), font=header_font)
            draw.text((200, genres_y), genres, fill=(255, 255, 255), font=text_font)
            
            # Description
            desc_y = genres_y + 50
            draw.text((50, desc_y), "📝 Description:", fill=(200, 200, 200), font=header_font)
            
            # Wrap text
            desc_lines = []
            current_line = ""
            words = description.split()
            
            for word in words:
                test_line = f"{current_line} {word}".strip()
                bbox = draw.textbbox((0, 0), test_line, font=text_font)
                if bbox[2] - bbox[0] < width - 100:
                    current_line = test_line
                else:
                    desc_lines.append(current_line)
                    current_line = word
            
            if current_line:
                desc_lines.append(current_line)
            
            # Draw description lines
            for i, line in enumerate(desc_lines[:5]):  # Max 5 lines
                draw.text((50, desc_y + 40 + i * 30), line, 
                         fill=(220, 220, 220), font=text_font)
            
            # Add cover image if available
            cover_url = anime_data.get('coverImage', {}).get('large')
            if cover_url:
                try:
                    cover_img = await self.download_image(cover_url)
                    if cover_img:
                        # Resize
                        cover_size = 200
                        cover_img = cover_img.resize((cover_size, cover_size), Image.Resampling.LANCZOS)
                        
                        # Add rounded corners
                        cover_img = self.add_rounded_corners(cover_img, 20)
                        
                        # Add border
                        border_size = 5
                        bordered = Image.new('RGBA', 
                                           (cover_size + border_size*2, cover_size + border_size*2),
                                           (21, 101, 192))
                        
                        bordered.paste(cover_img, (border_size, border_size), cover_img)
                        
                        # Position
                        bg.paste(bordered, (width - 250, 100), bordered)
                except:
                    pass
            
            # Add decorative elements
            # Draw sakura petals
            for _ in range(15):
                x = random.randint(0, width)
                y = random.randint(0, height)
                size = random.randint(3, 8)
                
                # Draw petal shape (simplified)
                draw.ellipse([(x, y), (x + size, y + size)], 
                           fill=(255, 182, 193, 150))
            
            # Save to bytes
            img_bytes = io.BytesIO()
            bg.save(img_bytes, format='PNG', quality=95)
            img_bytes.seek(0)
            
            return img_bytes.getvalue()
            
        except Exception as e:
            print(f"Error creating anime card: {e}")
            return None
    
    async def create_character_card(self, character_data: dict) -> Optional[bytes]:
        """Create beautiful character info card"""
        try:
            width, height = 800, 500
            
            # Get character info
            name = character_data.get('name', {}).get('full', 'Unknown')
            gender = character_data.get('gender', 'Unknown')
            age = character_data.get('age', 'Unknown')
            favorites = character_data.get('favourites', 0)
            
            # Get anime appearances
            media = character_data.get('media', {}).get('edges', [])
            anime_list = []
            for m in media[:3]:
                if m['node']['type'] == 'ANIME':
                    title = m['node']['title'].get('english') or m['node']['title'].get('romaji', 'Unknown')
                    anime_list.append(title)
            
            # Create background
            bg = Image.new('RGB', (width, height), (40, 40, 60))
            draw = ImageDraw.Draw(bg)
            
            # Get fonts
            name_font = self.get_font(40, bold=True)
            info_font = self.get_font(26, bold=True)
            text_font = self.get_font(22)
            small_font = self.get_font(18)
            
            # Character name
            draw.text((width // 2, 40), name, 
                     fill=(255, 255, 255), font=name_font, anchor="mm")
            
            # Character info boxes
            info_y = 100
            info_items = [
                ("⚧️ Gender", gender),
                ("🎂 Age", str(age)),
                ("❤️ Favorites", f"{favorites:,}"),
            ]
            
            box_width = 200
            box_spacing = 30
            
            for i, (label, value) in enumerate(info_items):
                x = 50 + i * (box_width + box_spacing)
                
                # Draw box
                draw.rounded_rectangle([(x, info_y), (x + box_width, info_y + 70)], 
                                     radius=15, fill=(50, 150, 200))
                
                # Draw label and value
                draw.text((x + box_width//2, info_y + 20), label, 
                         fill=(255, 255, 255), font=small_font, anchor="mm")
                draw.text((x + box_width//2, info_y + 45), value, 
                         fill=(255, 255, 255), font=info_font, anchor="mm")
            
            # Anime appearances
            anime_y = info_y + 100
            draw.text((50, anime_y), "📺 Appears in:", 
                     fill=(200, 200, 200), font=info_font)
            
            for i, anime in enumerate(anime_list[:3]):
                draw.text((250, anime_y + i * 35), f"• {anime}", 
                         fill=(255, 255, 255), font=text_font)
            
            # Add character image if available
            image_url = character_data.get('image', {}).get('large')
            if image_url:
                try:
                    char_img = await self.download_image(image_url)
                    if char_img:
                        # Resize
                        img_size = 300
                        char_img = char_img.resize((img_size, img_size), Image.Resampling.LANCZOS)
                        
                        # Add rounded corners
                        char_img = self.add_rounded_corners(char_img, 20)
                        
                        # Position
                        bg.paste(char_img, (width - 350, 100), char_img)
                except:
                    pass
            
            # Add decorative elements
            # Draw stars
            for _ in range(20):
                x = random.randint(0, width)
                y = random.randint(0, height)
                size = random.randint(1, 4)
                draw.ellipse([(x, y), (x + size, y + size)], 
                           fill=(255, 255, 255, 200))
            
            # Save to bytes
            img_bytes = io.BytesIO()
            bg.save(img_bytes, format='PNG', quality=95)
            img_bytes.seek(0)
            
            return img_bytes.getvalue()
            
        except Exception as e:
            print(f"Error creating character card: {e}")
            return None

class WebhookHandler:
    """Handle OAuth webhook callbacks"""
    
    def __init__(self, oauth_handler: AniListOAuth):
        self.oauth = oauth_handler
        self.image_gen = ImageGenerator()
    
    async def handle_callback(self, code: str, state: str) -> Optional[Dict[str, Any]]:
        """Handle OAuth callback"""
        # Validate state
        user_id = self.oauth.validate_state_token(state)
        if not user_id:
            return {"error": "Invalid or expired state token"}
        
        # Exchange code for token
        token_data = await self.oauth.exchange_code_for_token(code)
        if not token_data:
            return {"error": "Failed to exchange code for token"}
        
        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')
        expires_in = token_data.get('expires_in', 3600)
        
        # Get user data
        user_data = await self.oauth.get_user_data(access_token)
        if not user_data:
            return {"error": "Failed to get user data"}
        
        # Calculate expiration time
        expires_at = int(datetime.now().timestamp()) + expires_in
        
        # Update user in database
        Database.update_user(
            user_id,
            anilist_id=user_data.get('id'),
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            anilist_username=user_data.get('name'),
            anilist_avatar=user_data.get('avatar', {}).get('large'),
            anilist_banner=user_data.get('bannerImage'),
            anime_stats=json.dumps(user_data.get('statistics', {}).get('anime', {})),
            manga_stats=json.dumps(user_data.get('statistics', {}).get('manga', {}))
        )
        
        # Create profile image
        user_db = Database.get_user(user_id)
        profile_image = await self.image_gen.create_profile_card(user_db, user_data)
        
        return {
            "success": True,
            "user_id": user_id,
            "anilist_username": user_data.get('name'),
            "profile_image": base64.b64encode(profile_image).decode() if profile_image else None
        }

# Singleton instances
oauth_handler = AniListOAuth()
image_generator = ImageGenerator()

# =========== TEST FUNCTIONS ===========
async def test_oauth():
    """Test OAuth flow"""
    print("Testing OAuth flow...")
    
    # Generate authorization URL
    user_id = 123456  # Test user ID
    redirect_uri = "https://t.me/animekun_bot"
    
    auth_url = await oauth_handler.get_authorization_url(user_id, redirect_uri)
    print(f"Authorization URL: {auth_url}")
    
    # Simulate callback (in real scenario, user would be redirected here)
    print("\nSimulating callback...")
    
    # You would normally get these from the redirect
    test_state = list(oauth_handler.callback_states.keys())[0]
    test_code = "test_code_123"  # This would be provided by AniList
    
    # Create webhook handler
    webhook = WebhookHandler(oauth_handler)
    
    # Handle callback
    result = await webhook.handle_callback(test_code, test_state)
    print(f"Callback result: {result}")
    
    await oauth_handler.close()

async def test_image_generation():
    """Test image generation"""
    print("\nTesting image generation...")
    
    # Test user data
    test_user = {
        "user_id": 123456,
        "username": "TestUser",
        "first_name": "Test",
        "stats": json.dumps({
            "commands_used": 150,
            "daily_streak": 7,
            "quiz_score": 1250,
            "battle_wins": 12
        })
    }
    
    # Test AniList data
    test_anilist = {
        "name": "AniListUser",
        "statistics": {
            "anime": {
                "count": 250,
                "meanScore": 85,
                "minutesWatched": 150000,
                "episodesWatched": 5000
            }
        },
        "avatar": {
            "large": "https://s4.anilist.co/file/anilistcdn/user/avatar/large/default.png"
        }
    }
    
    # Generate profile card
    profile_image = await image_generator.create_profile_card(test_user, test_anilist)
    
    if profile_image:
        # Save test image
        with open("test_profile.png", "wb") as f:
            f.write(profile_image)
        print("✅ Profile image generated: test_profile.png")
    else:
        print("❌ Failed to generate profile image")
    
    # Test anime card
    test_anime = {
        "title": {
            "english": "Attack on Titan",
            "romaji": "Shingeki no Kyojin"
        },
        "averageScore": 86,
        "episodes": 75,
        "status": "FINISHED",
        "genres": ["Action", "Drama", "Fantasy"],
        "description": "Centuries ago, mankind was slaughtered to near extinction by monstrous humanoid creatures called titans...",
        "coverImage": {
            "large": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx16498-6HkqjNl6tT65.jpg"
        }
    }
    
    anime_image = await image_generator.create_anime_card(test_anime)
    
    if anime_image:
        with open("test_anime.png", "wb") as f:
            f.write(anime_image)
        print("✅ Anime image generated: test_anime.png")
    
    # Test character card
    test_character = {
        "name": {
            "full": "Eren Yeager"
        },
        "gender": "Male",
        "age": "19",
        "favourites": 150000,
        "media": {
            "edges": [
                {
                    "node": {
                        "type": "ANIME",
                        "title": {
                            "english": "Attack on Titan",
                            "romaji": "Shingeki no Kyojin"
                        }
                    }
                }
            ]
        },
        "image": {
            "large": "https://s4.anilist.co/file/anilistcdn/character/large/b14744-dHw17DNnXe2z.png"
        }
    }
    
    char_image = await image_generator.create_character_card(test_character)
    
    if char_image:
        with open("test_character.png", "wb") as f:
            f.write(char_image)
        print("✅ Character image generated: test_character.png")

if __name__ == "__main__":
    # Run tests
    async def main():
        await test_oauth()
        await test_image_generation()
    
    asyncio.run(main())
