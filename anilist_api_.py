import aiohttp
import asyncio
import json
import random
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import io
import os
import requests
from io import BytesIO
import redis

class AniListAPI:
    """AniList API wrapper with caching"""
    
    def __init__(self, redis_client):
        self.base_url = "https://graphql.anilist.co"
        self.redis = redis_client
        self.session = None
        self.cache_ttl = 3600  # 1 hour
        
    async def _get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def _make_request(self, query: str, variables: Dict = None) -> Dict:
        """Make GraphQL request with caching"""
        cache_key = None
        if variables:
            # Create cache key from query and variables
            cache_str = query + json.dumps(variables, sort_keys=True)
            cache_key = f"graphql:{hashlib.md5(cache_str.encode()).hexdigest()}"
            
            # Check cache
            cached = self.redis.get(cache_key)
            if cached:
                return json.loads(cached)
        
        session = await self._get_session()
        
        try:
            async with session.post(
                self.base_url,
                json={"query": query, "variables": variables or {}},
                headers={"Content-Type": "application/json"}
            ) as response:
                result = await response.json()
                
                if "errors" in result:
                    error_msg = result["errors"][0].get("message", "Unknown error")
                    raise Exception(f"AniList API Error: {error_msg}")
                
                # Cache successful response
                if cache_key and "data" in result:
                    self.redis.setex(cache_key, self.cache_ttl, json.dumps(result))
                
                # Update API call statistics
                self.redis.incr("stats:anilist_calls")
                
                return result.get("data", {})
                
        except Exception as e:
            raise Exception(f"Request failed: {e}")
    
    # =========== ANIME QUERIES ===========
    
    async def search_anime(self, query: str, page: int = 1, per_page: int = 10) -> List[Dict]:
        """Search anime/manga"""
        graphql_query = """
        query ($search: String, $page: Int, $perPage: Int) {
          Page(page: $page, perPage: $perPage) {
            media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
              id
              title {
                romaji
                english
                native
              }
              type
              format
              status
              description
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
              episodes
              duration
              chapters
              volumes
              source
              hashtag
              trailer {
                id
                site
                thumbnail
              }
              updatedAt
              coverImage {
                extraLarge
                large
                medium
                color
              }
              bannerImage
              genres
              synonyms
              averageScore
              meanScore
              popularity
              trending
              favourites
              tags {
                name
                description
                category
                rank
                isGeneralSpoiler
                isMediaSpoiler
                isAdult
              }
              relations {
                edges {
                  id
                  relationType
                  node {
                    id
                    title {
                      romaji
                      english
                    }
                    type
                    format
                    status
                    averageScore
                    popularity
                  }
                }
              }
              characters {
                edges {
                  id
                  role
                  name
                  node {
                    id
                    name {
                      full
                    }
                    image {
                      large
                    }
                  }
                }
              }
              studios {
                edges {
                  isMain
                  node {
                    id
                    name
                  }
                }
              }
              isAdult
              nextAiringEpisode {
                airingAt
                timeUntilAiring
                episode
              }
              siteUrl
            }
          }
        }
        """
        
        variables = {
            "search": query,
            "page": page,
            "perPage": per_page
        }
        
        result = await self._make_request(graphql_query, variables)
        return result.get("Page", {}).get("media", [])
    
    async def get_anime(self, anime_id: int) -> Dict:
        """Get detailed anime information"""
        graphql_query = """
        query ($id: Int) {
          Media(id: $id, type: ANIME) {
            id
            title {
              romaji
              english
              native
            }
            type
            format
            status
            description
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
            episodes
            duration
            chapters
            volumes
            source
            hashtag
            trailer {
              id
              site
              thumbnail
            }
            updatedAt
            coverImage {
              extraLarge
              large
              medium
              color
            }
            bannerImage
            genres
            synonyms
            averageScore
            meanScore
            popularity
            trending
            favourites
            tags {
              name
              description
              category
              rank
              isGeneralSpoiler
              isMediaSpoiler
              isAdult
            }
            relations {
              edges {
                id
                relationType
                node {
                  id
                  title {
                    romaji
                    english
                  }
                  type
                  format
                  status
                    averageScore
                  popularity
                }
              }
            }
            characters {
              edges {
                id
                role
                name
                node {
                  id
                  name {
                    full
                  }
                  image {
                    large
                  }
                }
              }
            }
            staff {
              edges {
                id
                role
                node {
                  id
                  name {
                    full
                  }
                  image {
                    large
                  }
                }
              }
            }
            studios {
              edges {
                isMain
                node {
                  id
                  name
                }
              }
            }
            rankings {
              id
              rank
              type
              format
              year
              season
              allTime
              context
            }
            reviews {
              edges {
                node {
                  id
                  summary
                  rating
                  ratingAmount
                  user {
                    id
                    name
                    avatar {
                      large
                    }
                  }
                }
              }
            }
            recommendations {
              edges {
                node {
                  id
                  rating
                  mediaRecommendation {
                    id
                    title {
                      romaji
                      english
                    }
                    coverImage {
                      large
                    }
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
            isAdult
            nextAiringEpisode {
              airingAt
              timeUntilAiring
              episode
            }
            siteUrl
          }
        }
        """
        
        variables = {"id": anime_id}
        result = await self._make_request(graphql_query, variables)
        return result.get("Media", {})
    
    async def get_trending_anime(self, per_page: int = 10) -> List[Dict]:
        """Get trending anime"""
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
              popularity
              format
              episodes
              status
              nextAiringEpisode {
                episode
                airingAt
              }
            }
          }
        }
        """
        
        variables = {"perPage": per_page}
        result = await self._make_request(graphql_query, variables)
        return result.get("Page", {}).get("media", [])
    
    async def get_popular_anime(self, per_page: int = 10) -> List[Dict]:
        """Get popular anime"""
        graphql_query = """
        query ($perPage: Int) {
          Page(perPage: $perPage) {
            media(type: ANIME, sort: POPULARITY_DESC) {
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
        
        variables = {"perPage": per_page}
        result = await self._make_request(graphql_query, variables)
        return result.get("Page", {}).get("media", [])
    
    async def get_seasonal_anime(self, year: int = None, season: str = None) -> List[Dict]:
        """Get seasonal anime"""
        if not year:
            year = datetime.now().year
        if not season:
            month = datetime.now().month
            if month in [1, 2, 3]:
                season = "WINTER"
            elif month in [4, 5, 6]:
                season = "SPRING"
            elif month in [7, 8, 9]:
                season = "SUMMER"
            else:
                season = "FALL"
        
        graphql_query = """
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
              startDate {
                year
                month
                day
              }
            }
          }
        }
        """
        
        variables = {
            "season": season,
            "seasonYear": year,
            "perPage": 20
        }
        result = await self._make_request(graphql_query, variables)
        return result.get("Page", {}).get("media", [])
    
    async def get_airing_schedule(self) -> List[Dict]:
        """Get today's airing schedule"""
        today = datetime.now()
        start_of_day = int(datetime(today.year, today.month, today.day).timestamp())
        end_of_day = start_of_day + 86400
        
        graphql_query = """
        query ($page: Int, $perPage: Int, $airingAt_greater: Int, $airingAt_lesser: Int) {
          Page(page: $page, perPage: $perPage) {
            airingSchedules(airingAt_greater: $airingAt_greater, airingAt_lesser: $airingAt_lesser, sort: TIME) {
              id
              airingAt
              timeUntilAiring
              episode
              media {
                id
                title {
                  romaji
                  english
                }
                coverImage {
                  large
                }
                episodes
                nextAiringEpisode {
                  episode
                }
              }
            }
          }
        }
        """
        
        variables = {
            "page": 1,
            "perPage": 50,
            "airingAt_greater": start_of_day,
            "airingAt_lesser": end_of_day
        }
        
        result = await self._make_request(graphql_query, variables)
        return result.get("Page", {}).get("airingSchedules", [])
    
    # =========== MANGA QUERIES ===========
    
    async def search_manga(self, query: str, page: int = 1, per_page: int = 10) -> List[Dict]:
        """Search manga"""
        graphql_query = """
        query ($search: String, $page: Int, $perPage: Int) {
          Page(page: $page, perPage: $perPage) {
            media(search: $search, type: MANGA, sort: SEARCH_MATCH) {
              id
              title {
                romaji
                english
                native
              }
              type
              format
              status
              description
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
              chapters
              volumes
              coverImage {
                extraLarge
                large
                medium
                color
              }
              bannerImage
              genres
              averageScore
              meanScore
              popularity
              trending
              favourites
              tags {
                name
                description
                category
                rank
                isGeneralSpoiler
                isMediaSpoiler
                isAdult
              }
              isAdult
              siteUrl
            }
          }
        }
        """
        
        variables = {
            "search": query,
            "page": page,
            "perPage": per_page
        }
        
        result = await self._make_request(graphql_query, variables)
        return result.get("Page", {}).get("media", [])
    
    # =========== CHARACTER QUERIES ===========
    
    async def search_character(self, query: str, page: int = 1, per_page: int = 10) -> List[Dict]:
        """Search characters"""
        graphql_query = """
        query ($search: String, $page: Int, $perPage: Int) {
          Page(page: $page, perPage: $perPage) {
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
              description
              gender
              dateOfBirth {
                year
                month
                day
              }
              age
              bloodType
              siteUrl
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
                  voiceActors {
                    id
                    name {
                      full
                    }
                    language
                    image {
                      large
                    }
                  }
                }
              }
              favourites
            }
          }
        }
        """
        
        variables = {
            "search": query,
            "page": page,
            "perPage": per_page
        }
        
        result = await self._make_request(graphql_query, variables)
        return result.get("Page", {}).get("characters", [])
    
    async def get_character(self, character_id: int) -> Dict:
        """Get character details"""
        graphql_query = """
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
            description
            gender
            dateOfBirth {
              year
              month
              day
            }
            age
            bloodType
            siteUrl
            media {
              edges {
                node {
                  id
                  title {
                    romaji
                    english
                  }
                  type
                  format
                  coverImage {
                    large
                  }
                }
                voiceActors {
                  id
                  name {
                    full
                  }
                  language
                  image {
                    large
                  }
                }
              }
            }
            favourites
          }
        }
        """
        
        variables = {"id": character_id}
        result = await self._make_request(graphql_query, variables)
        return result.get("Character", {})
    
    # =========== STAFF QUERIES ===========
    
    async def search_staff(self, query: str, page: int = 1, per_page: int = 10) -> List[Dict]:
        """Search staff"""
        graphql_query = """
        query ($search: String, $page: Int, $perPage: Int) {
          Page(page: $page, perPage: $perPage) {
            staff(search: $search) {
              id
              name {
                full
                native
              }
              image {
                large
                medium
              }
              description
              gender
              dateOfBirth {
                year
                month
                day
              }
              dateOfDeath {
                year
                month
                day
              }
              age
              bloodType
              homeTown
              siteUrl
              staffMedia {
                edges {
                  node {
                    id
                    title {
                      romaji
                      english
                    }
                    type
                  }
                  staffRole
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
              favourites
            }
          }
        }
        """
        
        variables = {
            "search": query,
            "page": page,
            "perPage": per_page
        }
        
        result = await self._make_request(graphql_query, variables)
        return result.get("Page", {}).get("staff", [])
    
    # =========== STUDIO QUERIES ===========
    
    async def search_studio(self, query: str, page: int = 1, per_page: int = 10) -> List[Dict]:
        """Search studios"""
        graphql_query = """
        query ($search: String, $page: Int, $perPage: Int) {
          Page(page: $page, perPage: $perPage) {
            studios(search: $search) {
              id
              name
              isAnimationStudio
              siteUrl
              media {
                edges {
                  node {
                    id
                    title {
                      romaji
                      english
                    }
                    type
                    format
                    coverImage {
                      large
                    }
                    averageScore
                    popularity
                  }
                  isMain
                }
              }
              favourites
            }
          }
        }
        """
        
        variables = {
            "search": query,
            "page": page,
            "perPage": per_page
        }
        
        result = await self._make_request(graphql_query, variables)
        return result.get("Page", {}).get("studios", [])
    
    # =========== USER QUERIES ===========
    
    async def get_user_profile(self, username: str) -> Dict:
        """Get user profile"""
        graphql_query = """
        query ($name: String) {
          User(name: $name) {
            id
            name
            about
            avatar {
              large
              medium
            }
            bannerImage
            isFollowing
            isFollower
            isBlocked
            bans
            options {
              titleLanguage
              displayAdultContent
              airingNotifications
              profileColor
            }
            mediaListOptions {
              scoreFormat
              rowOrder
              animeList {
                sectionOrder
                splitCompletedSectionByFormat
                customLists
                advancedScoring
                advancedScoringEnabled
              }
              mangaList {
                sectionOrder
                splitCompletedSectionByFormat
                customLists
                advancedScoring
                advancedScoringEnabled
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
              manga {
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
              staff {
                edges {
                  node {
                    id
                    name {
                      full
                    }
                  }
                }
              }
              studios {
                edges {
                  node {
                    id
                    name
                  }
                }
              }
            }
            statistics {
              anime {
                count
                meanScore
                standardDeviation
                minutesWatched
                episodesWatched
                chaptersRead
                volumesRead
                statuses {
                  status
                  count
                }
                formats {
                  format
                  count
                }
                lengths {
                  length
                  count
                }
                releaseYears {
                  releaseYear
                  count
                }
                startYears {
                  startYear
                  count
                }
                countries {
                  country
                  count
                }
                scores {
                  score
                  count
                }
                voiceActors {
                  voiceActor {
                    id
                    name {
                      full
                    }
                  }
                  count
                  meanScore
                  minutesWatched
                  chaptersRead
                }
                staff {
                  staff {
                    id
                    name {
                      full
                    }
                  }
                  count
                  meanScore
                  minutesWatched
                  chaptersRead
                }
                studios {
                  studio {
                    id
                    name
                  }
                  count
                  meanScore
                  minutesWatched
                  chaptersRead
                }
              }
              manga {
                count
                meanScore
                standardDeviation
                chaptersRead
                volumesRead
                statuses {
                  status
                  count
                }
                formats {
                  format
                  count
                }
                lengths {
                  length
                  count
                }
                releaseYears {
                  releaseYear
                  count
                }
                startYears {
                  startYear
                  count
                }
                countries {
                  country
                  count
                }
                scores {
                  score
                  count
                }
                staff {
                  staff {
                    id
                    name {
                      full
                    }
                  }
                  count
                  meanScore
                  chaptersRead
                }
                studios {
                  studio {
                    id
                    name
                  }
                  count
                  meanScore
                  chaptersRead
                }
              }
            }
            donatorTier
            donatorBadge
            moderatorRoles {
              role
            }
            siteUrl
            updatedAt
            stats {
              watchedTime
              chaptersRead
              animeStatusDistribution {
                status
                amount
              }
              mangaStatusDistribution {
                status
                amount
              }
            }
          }
        }
        """
        
        variables = {"name": username}
        result = await self._make_request(graphql_query, variables)
        return result.get("User", {})
    
    async def get_user_list(self, username: str, media_type: str = "ANIME") -> List[Dict]:
        """Get user's anime/manga list"""
        graphql_query = """
        query ($userName: String, $type: MediaType) {
          MediaListCollection(userName: $userName, type: $type) {
            lists {
              name
              isCustomList
              isCompletedList: isSplitCompletedList
              entries {
                id
                mediaId
                status
                score
                progress
                repeat
                priority
                private
                notes
                hiddenFromStatusLists
                customLists
                advancedScores
                startedAt {
                  year
                  month
                  day
                }
                completedAt {
                  year
                  month
                  day
                }
                updatedAt
                createdAt
                media {
                  id
                  title {
                    romaji
                    english
                  }
                  type
                  format
                  status
                  episodes
                  chapters
                  volumes
                  coverImage {
                    large
                  }
                  averageScore
                  popularity
                  nextAiringEpisode {
                    episode
                    airingAt
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {
            "userName": username,
            "type": media_type
        }
        
        result = await self._make_request(graphql_query, variables)
        collection = result.get("MediaListCollection", {})
        lists = collection.get("lists", [])
        
        all_entries = []
        for list_data in lists:
            all_entries.extend(list_data.get("entries", []))
        
        return all_entries
    
    async def get_top_anime(self, page: int = 1, per_page: int = 10) -> List[Dict]:
        """Get top-rated anime"""
        graphql_query = """
        query ($page: Int, $perPage: Int) {
          Page(page: $page, perPage: $perPage) {
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
              meanScore
              popularity
              format
              episodes
              status
              startDate {
                year
              }
            }
          }
        }
        """
        
        variables = {
            "page": page,
            "perPage": per_page
        }
        
        result = await self._make_request(graphql_query, variables)
        return result.get("Page", {}).get("media", [])
    
    async def get_random_anime(self, genre: str = None) -> Dict:
        """Get random anime"""
        page = random.randint(1, 50)
        per_page = 10
        
        graphql_query = """
        query ($page: Int, $perPage: Int, $genre: String) {
          Page(page: $page, perPage: $perPage) {
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
              status
              genres
              description
            }
          }
        }
        """
        
        variables = {
            "page": page,
            "perPage": per_page,
            "genre": genre
        }
        
        result = await self._make_request(graphql_query, variables)
        media_list = result.get("Page", {}).get("media", [])
        
        if media_list:
            return random.choice(media_list)
        return {}
    
    async def close(self):
        """Close the session"""
        if self.session and not self.session.closed:
            await self.session.close()

class ImageGenerator:
    """Generate anime image cards"""
    
    def __init__(self):
        self.font_cache = {}
        self.redis = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        
    async def download_image(self, url: str) -> Optional[Image.Image]:
        """Download image from URL"""
        if not url:
            return None
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return Image.open(BytesIO(response.content))
        except Exception as e:
            print(f"Failed to download image: {e}")
        return None
    
    def get_font(self, size: int, bold: bool = False):
        """Get font with caching"""
        font_key = f"font_{size}_{bold}"
        if font_key in self.font_cache:
            return self.font_cache[font_key]
        
        try:
            if bold:
                font = ImageFont.truetype("arialbd.ttf", size)
            else:
                font = ImageFont.truetype("arial.ttf", size)
        except:
            # Fallback to default font
            font = ImageFont.load_default()
        
        self.font_cache[font_key] = font
        return font
    
    def wrap_text(self, text: str, max_width: int, font) -> List[str]:
        """Wrap text to fit within width"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = font.getbbox(test_line)
            width = bbox[2] - bbox[0]
            
            if width <= max_width:
                current_line.append(word)
            else:
                lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
    async def generate_anime_card(self, anime_data: Dict) -> str:
        """Generate anime info card image"""
        # Update image generation stats
        self.redis.incr("stats:image_gen")
        
        # Create canvas
        width, height = 800, 1200
        image = Image.new('RGB', (width, height), '#1a1a2e')
        draw = ImageDraw.Draw(image)
        
        # Download cover image
        cover_url = anime_data.get('coverImage', {}).get('extraLarge')
        if cover_url:
            cover_img = await self.download_image(cover_url)
            if cover_img:
                # Resize and add blur effect
                cover_img = cover_img.resize((width, 400))
                blurred = cover_img.filter(ImageFilter.GaussianBlur(5))
                image.paste(blurred, (0, 0))
                
                # Add overlay
                overlay = Image.new('RGBA', (width, 400), (26, 26, 46, 180))
                image.paste(overlay, (0, 0), overlay)
                
                # Add original cover
                cover_img = cover_img.resize((250, 350))
                image.paste(cover_img, (50, 25))
        
        # Add anime title
        title = anime_data.get('title', {}).get('english') or anime_data.get('title', {}).get('romaji', 'N/A')
        title_font = self.get_font(36, bold=True)
        draw.text((320, 50), title, fill='white', font=title_font)
        
        # Add score badge
        score = anime_data.get('averageScore', 0)
        if score:
            # Draw score circle
            draw.ellipse([(320, 120), (380, 180)], fill='#FFD700' if score >= 80 else '#4CAF50' if score >= 60 else '#FF9800')
            score_font = self.get_font(24, bold=True)
            draw.text((335, 130), str(score), fill='white', font=score_font)
            
            # Add "Score" text
            draw.text((400, 135), "Score", fill='#cccccc', font=self.get_font(16))
        
        # Add status
        status = anime_data.get('status', 'N/A').capitalize()
        status_color = {
            'Finished': '#4CAF50',
            'Releasing': '#2196F3',
            'Not yet released': '#FF9800',
            'Cancelled': '#F44336',
            'Hiatus': '#9C27B0'
        }.get(status, '#757575')
        
        draw.rounded_rectangle([(500, 120), (600, 160)], radius=10, fill=status_color)
        draw.text((510, 125), status, fill='white', font=self.get_font(18, bold=True))
        
        # Add info section
        y_offset = 200
        
        # Type and episodes
        media_type = anime_data.get('format', 'N/A')
        episodes = anime_data.get('episodes', 'N/A')
        info_text = f"{media_type} • {episodes} episodes"
        draw.text((320, y_offset), info_text, fill='#cccccc', font=self.get_font(18))
        y_offset += 40
        
        # Genres
        genres = anime_data.get('genres', [])[:5]
        genre_text = " • ".join(genres)
        draw.text((320, y_offset), genre_text, fill='#FF9800', font=self.get_font(16))
        y_offset += 40
        
        # Studios
        studios = [edge.get('node', {}).get('name') for edge in anime_data.get('studios', {}).get('edges', [])[:3]]
        if studios:
            studio_text = f"Studio: {', '.join(studios)}"
            draw.text((320, y_offset), studio_text, fill='#cccccc', font=self.get_font(16))
            y_offset += 40
        
        # Add description
        description = anime_data.get('description', 'No description available.')
        # Remove HTML tags
        import re
        description = re.sub(r'<[^>]+>', '', description)
        
        desc_lines = self.wrap_text(description, 450, self.get_font(14))
        for i, line in enumerate(desc_lines[:8]):
            draw.text((50, 450 + i*25), line, fill='#eeeeee', font=self.get_font(14))
        
        # Add stats section
        stats_y = 700
        
        # Popularity
        popularity = anime_data.get('popularity', 'N/A')
        draw.text((50, stats_y), f"📊 Popularity: #{popularity}", fill='#2196F3', font=self.get_font(16))
        
        # Favorites
        favorites = anime_data.get('favourites', 'N/A')
        draw.text((300, stats_y), f"❤️ Favorites: {favorites}", fill='#E91E63', font=self.get_font(16))
        
        # Start date
        start_date = anime_data.get('startDate', {})
        date_text = f"{start_date.get('year', 'N/A')}-{start_date.get('month', 'N/A')}-{start_date.get('day', 'N/A')}"
        draw.text((550, stats_y), f"📅 {date_text}", fill='#4CAF50', font=self.get_font(16))
        
        # Add progress bar for airing anime
        if anime_data.get('status') == 'RELEASING':
            next_ep = anime_data.get('nextAiringEpisode', {})
            if next_ep:
                episode = next_ep.get('episode', 1)
                total_eps = anime_data.get('episodes', episode + 12)
                
                # Draw progress bar
                bar_width = 700
                bar_height = 20
                bar_x, bar_y = 50, 800
                
                # Background
                draw.rounded_rectangle([(bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height)], 
                                      radius=10, fill='#333333')
                
                # Progress
                if total_eps:
                    progress_width = int((episode / total_eps) * bar_width)
                    draw.rounded_rectangle([(bar_x, bar_y), (bar_x + progress_width, bar_y + bar_height)], 
                                          radius=10, fill='#2196F3')
                
                # Text
                progress_text = f"Episode {episode}/{total_eps if total_eps else '?'}"
                draw.text((bar_x + bar_width//2 - 60, bar_y - 25), progress_text, 
                         fill='white', font=self.get_font(16, bold=True))
        
        # Add footer
        draw.text((50, height - 50), "AnimeKuun Bot • anilist.co", 
                 fill='#757575', font=self.get_font(14))
        
        # Add QR code placeholder
        draw.text((width - 150, height - 50), "📱 Scan for AniList", 
                 fill='#4CAF50', font=self.get_font(12))
        
        # Save image
        output_path = f"anime_{anime_data['id']}_{int(time.time())}.jpg"
        image.save(output_path, quality=85)
        
        return output_path
    
    async def generate_user_card(self, user_data: Dict) -> str:
        """Generate user profile card"""
        # Update image generation stats
        self.redis.incr("stats:image_gen")
        
        # Create canvas
        width, height = 800, 1000
        image = Image.new('RGB', (width, height), '#1a1a2e')
        draw = ImageDraw.Draw(image)
        
        # Download avatar
        avatar_url = user_data.get('avatar', {}).get('large')
        if avatar_url:
            avatar_img = await self.download_image(avatar_url)
            if avatar_img:
                # Make circular avatar
                avatar_img = avatar_img.resize((200, 200))
                
                # Create circular mask
                mask = Image.new('L', (200, 200), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse([(0, 0), (200, 200)], fill=255)
                
                # Apply mask
                avatar_img.putalpha(mask)
                
                # Add shadow
                shadow = Image.new('RGBA', (210, 210), (0, 0, 0, 100))
                shadow_mask = Image.new('L', (210, 210), 0)
                shadow_draw = ImageDraw.Draw(shadow_mask)
                shadow_draw.ellipse([(0, 0), (210, 210)], fill=255)
                shadow.putalpha(shadow_mask)
                
                image.paste(shadow, (45, 45), shadow)
                image.paste(avatar_img, (50, 50), avatar_img)
        
        # User name
        username = user_data.get('name', 'N/A')
        name_font = self.get_font(42, bold=True)
        draw.text((270, 70), username, fill='white', font=name_font)
        
        # Donator badge
        donator_tier = user_data.get('donatorTier', 0)
        if donator_tier > 0:
            badge_color = '#FFD700' if donator_tier >= 3 else '#C0C0C0' if donator_tier >= 2 else '#CD7F32'
            draw.ellipse([(270, 130), (310, 170)], fill=badge_color)
            draw.text((280, 135), "★", fill='white', font=self.get_font(20, bold=True))
            draw.text((320, 140), f"Tier {donator_tier} Donator", fill=badge_color, font=self.get_font(16))
        
        # Add about section
        about = user_data.get('about', 'No bio available.')[:300]
        about_lines = self.wrap_text(about, 500, self.get_font(14))
        
        y_offset = 220
        draw.text((50, y_offset), "📝 About:", fill='#2196F3', font=self.get_font(18, bold=True))
        y_offset += 40
        
        for i, line in enumerate(about_lines[:6]):
            draw.text((70, y_offset + i*25), line, fill='#eeeeee', font=self.get_font(14))
        
        # Anime statistics
        stats_y = 450
        stats = user_data.get('statistics', {}).get('anime', {})
        
        # Stats boxes
        box_width = 150
        box_height = 80
        box_margin = 20
        
        stats_data = [
            ("🎬 Total", str(stats.get('count', 0))),
            ("⭐ Mean Score", f"{stats.get('meanScore', 0)}"),
            ("⏱️ Minutes", f"{stats.get('minutesWatched', 0):,}"),
            ("📺 Episodes", f"{stats.get('episodesWatched', 0):,}")
        ]
        
        for i, (label, value) in enumerate(stats_data):
            x = 50 + (i % 4) * (box_width + box_margin)
            y = stats_y + (i // 4) * (box_height + box_margin)
            
            # Draw box
            draw.rounded_rectangle([(x, y), (x + box_width, y + box_height)], 
                                  radius=15, fill='#252547')
            
            # Draw label and value
            draw.text((x + 10, y + 10), label, fill='#cccccc', font=self.get_font(14))
            draw.text((x + 10, y + 40), value, fill='white', font=self.get_font(20, bold=True))
        
        # Status distribution
        status_y = stats_y + box_height + box_margin + 100
        draw.text((50, status_y), "📊 Anime Status:", fill='#4CAF50', font=self.get_font(18, bold=True))
        
        status_dist = stats.get('statuses', [])
        if status_dist:
            status_y += 40
            max_count = max([s.get('count', 0) for s in status_dist])
            
            for i, status in enumerate(status_dist[:4]):
                status_name = status.get('status', '').capitalize()
                count = status.get('count', 0)
                
                # Draw status bar
                bar_width = int((count / max_count) * 400) if max_count > 0 else 0
                bar_height = 20
                
                colors = {
                    'Watching': '#2196F3',
                    'Completed': '#4CAF50',
                    'Planning': '#FF9800',
                    'Dropped': '#F44336',
                    'Paused': '#9C27B0'
                }
                
                bar_color = colors.get(status_name, '#757575')
                
                draw.text((50, status_y + i*35), status_name, fill='white', font=self.get_font(16))
                draw.rounded_rectangle([(200, status_y + i*35), (200 + bar_width, status_y + i*35 + bar_height)], 
                                      radius=10, fill=bar_color)
                draw.text((210 + bar_width, status_y + i*35), str(count), 
                         fill='#cccccc', font=self.get_font(14))
        
        # Add footer
        draw.text((50, height - 40), "Generated by AnimeKuun Bot", 
                 fill='#757575', font=self.get_font(14))
        draw.text((width - 200, height - 40), f"User ID: {user_data.get('id', 'N/A')}", 
                 fill='#757575', font=self.get_font(12))
        
        # Save image
        output_path = f"user_{user_data.get('id', int(time.time()))}_{int(time.time())}.jpg"
        image.save(output_path, quality=85)
        
        return output_path
    
    async def generate_character_card(self, character_data: Dict) -> str:
        """Generate character card"""
        # Update image generation stats
        self.redis.incr("stats:image_gen")
        
        # Create canvas
        width, height = 800, 1000
        image = Image.new('RGB', (width, height), '#1a1a2e')
        draw = ImageDraw.Draw(image)
        
        # Download character image
        char_url = character_data.get('image', {}).get('large')
        if char_url:
            char_img = await self.download_image(char_url)
            if char_img:
                # Resize and position
                char_img = char_img.resize((400, 500))
                image.paste(char_img, (0, 0))
                
                # Add gradient overlay
                overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
                overlay_draw = ImageDraw.Draw(overlay)
                
                # Create gradient
                for i in range(400):
                    alpha = int(255 * (i / 400))
                    overlay_draw.line([(i, 0), (i, height)], fill=(26, 26, 46, alpha))
                
                image.paste(overlay, (0, 0), overlay)
        
        # Character name
        name = character_data.get('name', {}).get('full', 'N/A')
        name_font = self.get_font(48, bold=True)
        draw.text((420, 50), name, fill='white', font=name_font)
        
        # Native name
        native_name = character_data.get('name', {}).get('native', '')
        if native_name:
            draw.text((420, 120), native_name, fill='#FF9800', font=self.get_font(24))
        
        # Character info
        y_offset = 200
        
        # Gender and age
        gender = character_data.get('gender', 'Unknown')
        age = character_data.get('age', 'Unknown')
        draw.text((420, y_offset), f"⚧ {gender} • 🎂 {age}", fill='#2196F3', font=self.get_font(18))
        y_offset += 40
        
        # Birthday
        dob = character_data.get('dateOfBirth', {})
        if dob.get('year'):
            birthday = f"{dob.get('month', '?')}/{dob.get('day', '?')}/{dob.get('year', '?')}"
            draw.text((420, y_offset), f"🎁 {birthday}", fill='#4CAF50', font=self.get_font(18))
            y_offset += 40
        
        # Blood type
        blood_type = character_data.get('bloodType', 'Unknown')
        if blood_type != 'Unknown':
            draw.text((420, y_offset), f"💉 Blood Type: {blood_type}", fill='#E91E63', font=self.get_font(18))
            y_offset += 40
        
        # Favorites
        favorites = character_data.get('favourites', 0)
        draw.text((420, y_offset), f"❤️ {favorites:,} favorites", fill='#FF4081', font=self.get_font(18))
        y_offset += 60
        
        # Description
        description = character_data.get('description', 'No description available.')
        import re
        description = re.sub(r'<[^>]+>', '', description)
        
        desc_lines = self.wrap_text(description, 350, self.get_font(14))
        draw.text((420, y_offset), "📖 Description:", fill='#FF9800', font=self.get_font(16, bold=True))
        y_offset += 40
        
        for i, line in enumerate(desc_lines[:10]):
            draw.text((420, y_offset + i*25), line, fill='#eeeeee', font=self.get_font(14))
        
        # Anime appearances
        media = character_data.get('media', {}).get('edges', [])
        if media:
            media_y = 650
            draw.text((50, media_y), "🎬 Appears in:", fill='#2196F3', font=self.get_font(18, bold=True))
            media_y += 40
            
            for i, edge in enumerate(media[:5]):
                anime = edge.get('node', {})
                title = anime.get('title', {}).get('english') or anime.get('title', {}).get('romaji', 'N/A')
                role = edge.get('role', 'Supporting')
                
                draw.text((70, media_y + i*30), f"• {title}", fill='white', font=self.get_font(14))
                draw.text((550, media_y + i*30), role, fill='#4CAF50', font=self.get_font(12))
        
        # Add footer
        draw.text((50, height - 40), "AnimeKuun Bot • Character Card", 
                 fill='#757575', font=self.get_font(14))
        
        # Save image
        output_path = f"character_{character_data.get('id', int(time.time()))}_{int(time.time())}.jpg"
        image.save(output_path, quality=85)
        
        return output_path
    
    async def close(self):
        """Clean up"""
        pass
