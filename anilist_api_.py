#!/usr/bin/env python3
"""
AniList API Wrapper for AnimeKuun Bot
Complete API implementation with image generation
"""

import aiohttp
import asyncio
import json
import random
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import os
import re
from io import BytesIO

# Image generation imports
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False
    print("⚠️ Pillow not installed, image generation disabled")

import requests

# =========== ANILIST API CLASS ===========
class AniListAPI:
    """Complete AniList API wrapper with caching"""
    
    def __init__(self, redis_client):
        self.base_url = "https://graphql.anilist.co"
        self.redis = redis_client
        self.session = None
        self.cache_ttl = 3600  # 1 hour cache
        self.rate_limit = 90  # requests per minute (AniList limit)
        self.last_request = 0
        
        # API statistics
        self.request_count = 0
        self.error_count = 0
        
        logger.info("✅ AniListAPI initialized")
    
    async def _get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def _rate_limit(self):
        """Implement rate limiting"""
        now = time.time()
        time_since_last = now - self.last_request
        min_interval = 60.0 / self.rate_limit
        
        if time_since_last < min_interval:
            await asyncio.sleep(min_interval - time_since_last)
        
        self.last_request = time.time()
    
    async def _make_request(self, query: str, variables: Dict = None, cache_key: str = None) -> Dict:
        """Make GraphQL request with caching and rate limiting"""
        # Rate limiting
        await self._rate_limit()
        
        # Generate cache key if not provided
        if not cache_key and variables:
            cache_str = query + json.dumps(variables, sort_keys=True)
            cache_key = f"anilist:{hashlib.md5(cache_str.encode()).hexdigest()}"
        
        # Check cache
        if cache_key:
            cached = self.redis.get(cache_key)
            if cached:
                try:
                    return json.loads(cached)
                except:
                    pass
        
        session = await self._get_session()
        
        try:
            async with session.post(
                self.base_url,
                json={"query": query, "variables": variables or {}},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "AnimeKuunBot/1.0"
                }
            ) as response:
                self.request_count += 1
                
                if response.status != 200:
                    self.error_count += 1
                    error_text = await response.text()
                    raise Exception(f"HTTP {response.status}: {error_text}")
                
                result = await response.json()
                
                if "errors" in result:
                    self.error_count += 1
                    error_msg = result["errors"][0].get("message", "Unknown error")
                    raise Exception(f"AniList API Error: {error_msg}")
                
                # Cache successful response
                if cache_key and "data" in result:
                    self.redis.setex(cache_key, self.cache_ttl, json.dumps(result))
                
                return result.get("data", {})
                
        except aiohttp.ClientError as e:
            self.error_count += 1
            raise Exception(f"Network error: {e}")
        except asyncio.TimeoutError:
            self.error_count += 1
            raise Exception("Request timeout")
    
    # =========== ANIME QUERIES ===========
    
    async def search_anime(self, query: str, page: int = 1, per_page: int = 10) -> List[Dict]:
        """Search anime"""
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
              description(asHtml: false)
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
        
        try:
            result = await self._make_request(graphql_query, variables)
            return result.get("Page", {}).get("media", [])
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
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
            description(asHtml: false)
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
        cache_key = f"anime:{anime_id}"
        
        try:
            result = await self._make_request(graphql_query, variables, cache_key)
            return result.get("Media", {})
        except Exception as e:
            print(f"Get anime error: {e}")
            return {}
    
    async def get_trending_anime(self, per_page: int = 15) -> List[Dict]:
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
        cache_key = f"trending:{per_page}"
        
        try:
            result = await self._make_request(graphql_query, variables, cache_key)
            return result.get("Page", {}).get("media", [])
        except Exception as e:
            print(f"Trending error: {e}")
            return []
    
    async def get_popular_anime(self, per_page: int = 15) -> List[Dict]:
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
        cache_key = f"popular:{per_page}"
        
        try:
            result = await self._make_request(graphql_query, variables, cache_key)
            return result.get("Page", {}).get("media", [])
        except Exception as e:
            print(f"Popular error: {e}")
            return []
    
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
        cache_key = f"seasonal:{year}:{season}"
        
        try:
            result = await self._make_request(graphql_query, variables, cache_key)
            return result.get("Page", {}).get("media", [])
        except Exception as e:
            print(f"Seasonal error: {e}")
            return []
    
    async def get_upcoming_anime(self, per_page: int = 15) -> List[Dict]:
        """Get upcoming anime"""
        # Get next season
        today = datetime.now()
        month = today.month
        year = today.year
        
        if month in [1, 2, 3]:  # Winter -> Spring
            next_season = "SPRING"
            next_year = year
        elif month in [4, 5, 6]:  # Spring -> Summer
            next_season = "SUMMER"
            next_year = year
        elif month in [7, 8, 9]:  # Summer -> Fall
            next_season = "FALL"
            next_year = year
        else:  # Fall -> Winter (next year)
            next_season = "WINTER"
            next_year = year + 1
        
        return await self.get_seasonal_anime(next_year, next_season)
    
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
        cache_key = f"schedule:{today.strftime('%Y%m%d')}"
        
        try:
            result = await self._make_request(graphql_query, variables, cache_key)
            return result.get("Page", {}).get("airingSchedules", [])
        except Exception as e:
            print(f"Schedule error: {e}")
            return []
    
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
              description(asHtml: false)
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
        
        try:
            result = await self._make_request(graphql_query, variables)
            return result.get("Page", {}).get("media", [])
        except Exception as e:
            print(f"Manga search error: {e}")
            return []
    
    async def get_manga(self, manga_id: int) -> Dict:
        """Get manga details"""
        graphql_query = """
        query ($id: Int) {
          Media(id: $id, type: MANGA) {
            id
            title {
              romaji
              english
              native
            }
            type
            format
            status
            description(asHtml: false)
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
        """
        
        variables = {"id": manga_id}
        cache_key = f"manga:{manga_id}"
        
        try:
            result = await self._make_request(graphql_query, variables, cache_key)
            return result.get("Media", {})
        except Exception as e:
            print(f"Get manga error: {e}")
            return {}
    
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
              description(asHtml: false)
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
        
        try:
            result = await self._make_request(graphql_query, variables)
            return result.get("Page", {}).get("characters", [])
        except Exception as e:
            print(f"Character search error: {e}")
            return []
    
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
            description(asHtml: false)
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
        cache_key = f"character:{character_id}"
        
        try:
            result = await self._make_request(graphql_query, variables, cache_key)
            return result.get("Character", {})
        except Exception as e:
            print(f"Get character error: {e}")
            return {}
    
    async def get_character_birthdays(self) -> List[Dict]:
        """Get today's character birthdays"""
        today = datetime.now()
        month = today.month
        day = today.day
        
        # We'll get popular characters and filter by birthday
        graphql_query = """
        query ($page: Int, $perPage: Int) {
          Page(page: $page, perPage: $perPage) {
            characters(sort: FAVOURITES_DESC) {
              id
              name {
                full
                native
              }
              image {
                large
              }
              dateOfBirth {
                year
                month
                day
              }
              age
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
        
        variables = {
            "page": 1,
            "perPage": 50
        }
        
        try:
            result = await self._make_request(graphql_query, variables)
            characters = result.get("Page", {}).get("characters", [])
            
            # Filter for today's birthdays
            today_birthdays = []
            for char in characters:
                dob = char.get('dateOfBirth', {})
                if dob.get('month') == month and dob.get('day') == day:
                    today_birthdays.append(char)
            
            return today_birthdays[:10]
        except Exception as e:
            print(f"Birthdays error: {e}")
            return []
    
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
              description(asHtml: false)
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
        
        try:
            result = await self._make_request(graphql_query, variables)
            return result.get("Page", {}).get("staff", [])
        except Exception as e:
            print(f"Staff search error: {e}")
            return []
    
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
                }
                isMain
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
        
        try:
            result = await self._make_request(graphql_query, variables)
            return result.get("Page", {}).get("studios", [])
        except Exception as e:
            print(f"Studio search error: {e}")
            return []
    
    async def get_top_studios(self, per_page: int = 10) -> List[Dict]:
        """Get top studios"""
        graphql_query = """
        query ($perPage: Int) {
          Page(perPage: $perPage) {
            studios(sort: FAVOURITES_DESC) {
              id
              name
              isAnimationStudio
              favourites
              media {
                edges {
                  node {
                    id
                    title {
                      romaji
                    }
                    averageScore
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {"perPage": per_page}
        
        try:
            result = await self._make_request(graphql_query, variables)
            return result.get("Page", {}).get("studios", [])
        except Exception as e:
            print(f"Top studios error: {e}")
            return []
    
    # =========== USER QUERIES ===========
    
    async def get_user_profile(self, username: str) -> Dict:
        """Get user profile"""
        graphql_query = """
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
        cache_key = f"user:{username.lower()}"
        
        try:
            result = await self._make_request(graphql_query, variables, cache_key)
            return result.get("User", {})
        except Exception as e:
            print(f"User profile error: {e}")
            return {}
    
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
        cache_key = f"userlist:{username.lower()}:{media_type}"
        
        try:
            result = await self._make_request(graphql_query, variables, cache_key)
            collection = result.get("MediaListCollection", {})
            lists = collection.get("lists", [])
            
            all_entries = []
            for list_data in lists:
                all_entries.extend(list_data.get("entries", []))
            
            return all_entries
        except Exception as e:
            print(f"User list error: {e}")
            return []
    
    # =========== TOP RATED QUERIES ===========
    
    async def get_top_anime(self, page: int = 1, per_page: int = 15) -> List[Dict]:
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
        cache_key = f"topanime:{page}:{per_page}"
        
        try:
            result = await self._make_request(graphql_query, variables, cache_key)
            return result.get("Page", {}).get("media", [])
        except Exception as e:
            print(f"Top anime error: {e}")
            return []
    
    async def get_top_manga(self, page: int = 1, per_page: int = 15) -> List[Dict]:
        """Get top-rated manga"""
        graphql_query = """
        query ($page: Int, $perPage: Int) {
          Page(page: $page, perPage: $perPage) {
            media(type: MANGA, sort: SCORE_DESC) {
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
              chapters
              volumes
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
        cache_key = f"topmanga:{page}:{per_page}"
        
        try:
            result = await self._make_request(graphql_query, variables, cache_key)
            return result.get("Page", {}).get("media", [])
        except Exception as e:
            print(f"Top manga error: {e}")
            return []
    
    # =========== STATISTICS QUERIES ===========
    
    async def get_anime_stats(self, anime_id: int) -> Dict:
        """Get anime statistics"""
        graphql_query = """
        query ($id: Int) {
          Media(id: $id, type: ANIME) {
            id
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
              id
              rank
              type
              format
              year
              season
              allTime
              context
            }
          }
        }
        """
        
        variables = {"id": anime_id}
        
        try:
            result = await self._make_request(graphql_query, variables)
            return result.get("Media", {})
        except Exception as e:
            print(f"Anime stats error: {e}")
            return {}
    
    async def get_genre_stats(self) -> List[Dict]:
        """Get genre statistics"""
        graphql_query = """
        query {
          GenreCollection
        }
        """
        
        try:
            result = await self._make_request(graphql_query)
            genres = result.get("GenreCollection", [])
            return [{"name": genre, "count": 0} for genre in genres[:20]]
        except Exception as e:
            print(f"Genre stats error: {e}")
            return []
    
    # =========== RELATION QUERIES ===========
    
    async def get_anime_relations(self, anime_id: int) -> List[Dict]:
        """Get anime relations"""
        graphql_query = """
        query ($id: Int) {
          Media(id: $id, type: ANIME) {
            id
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
                  coverImage {
                    large
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {"id": anime_id}
        
        try:
            result = await self._make_request(graphql_query, variables)
            media = result.get("Media", {})
            return media.get("relations", {}).get("edges", [])
        except Exception as e:
            print(f"Anime relations error: {e}")
            return []
    
    async def get_anime_characters(self, anime_id: int) -> List[Dict]:
        """Get anime characters"""
        graphql_query = """
        query ($id: Int) {
          Media(id: $id, type: ANIME) {
            id
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
                  description(asHtml: false)
                }
              }
            }
          }
        }
        """
        
        variables = {"id": anime_id}
        
        try:
            result = await self._make_request(graphql_query, variables)
            media = result.get("Media", {})
            return media.get("characters", {}).get("edges", [])
        except Exception as e:
            print(f"Anime characters error: {e}")
            return []
    
    async def get_anime_staff(self, anime_id: int) -> List[Dict]:
        """Get anime staff"""
        graphql_query = """
        query ($id: Int) {
          Media(id: $id, type: ANIME) {
            id
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
                  description(asHtml: false)
                }
              }
            }
          }
        }
        """
        
        variables = {"id": anime_id}
        
        try:
            result = await self._make_request(graphql_query, variables)
            media = result.get("Media", {})
            return media.get("staff", {}).get("edges", [])
        except Exception as e:
            print(f"Anime staff error: {e}")
            return []
    
    async def get_anime_reviews(self, anime_id: int) -> List[Dict]:
        """Get anime reviews"""
        graphql_query = """
        query ($id: Int, $page: Int, $perPage: Int) {
          Media(id: $id, type: ANIME) {
            id
            reviews(page: $page, perPage: $perPage, sort: RATING_DESC) {
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
                  createdAt
                }
              }
            }
          }
        }
        """
        
        variables = {
            "id": anime_id,
            "page": 1,
            "perPage": 5
        }
        
        try:
            result = await self._make_request(graphql_query, variables)
            media = result.get("Media", {})
            return media.get("reviews", {}).get("edges", [])
        except Exception as e:
            print(f"Anime reviews error: {e}")
            return []
    
    async def get_anime_recommendations(self, anime_id: int) -> List[Dict]:
        """Get anime recommendations"""
        graphql_query = """
        query ($id: Int, $page: Int, $perPage: Int) {
          Media(id: $id, type: ANIME) {
            id
            recommendations(page: $page, perPage: $perPage, sort: RATING_DESC) {
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
                    averageScore
                    popularity
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {
            "id": anime_id,
            "page": 1,
            "perPage": 10
        }
        
        try:
            result = await self._make_request(graphql_query, variables)
            media = result.get("Media", {})
            return media.get("recommendations", {}).get("edges", [])
        except Exception as e:
            print(f"Anime recommendations error: {e}")
            return []
    
    # =========== UTILITY QUERIES ===========
    
    async def get_random_anime(self, genre: str = None) -> Dict:
        """Get random anime"""
        # Get a random page (1-50) and pick first result
        page = random.randint(1, 50)
        
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
              description(asHtml: false)
            }
          }
        }
        """
        
        variables = {
            "page": page,
            "perPage": 1,
            "genre": genre
        }
        
        try:
            result = await self._make_request(graphql_query, variables)
            media_list = result.get("Page", {}).get("media", [])
            
            if media_list:
                return media_list[0]
            return {}
        except Exception as e:
            print(f"Random anime error: {e}")
            return {}
    
    async def get_anime_news(self, anime_id: int) -> List[Dict]:
        """Get anime news (placeholder)"""
        # Note: AniList doesn't have direct news API
        # This could be integrated with other APIs like MyAnimeList
        return []
    
    async def get_anime_trailer(self, anime_id: int) -> Dict:
        """Get anime trailer"""
        graphql_query = """
        query ($id: Int) {
          Media(id: $id, type: ANIME) {
            id
            trailer {
              id
              site
              thumbnail
            }
          }
        }
        """
        
        variables = {"id": anime_id}
        
        try:
            result = await self._make_request(graphql_query, variables)
            media = result.get("Media", {})
            trailer = media.get("trailer", {})
            
            if trailer and trailer.get('site') == 'youtube':
                trailer['url'] = f"https://youtube.com/watch?v={trailer['id']}"
            
            return trailer
        except Exception as e:
            print(f"Anime trailer error: {e}")
            return {}
    
    async def get_anime_quote(self) -> Dict:
        """Get random anime quote"""
        quotes = [
            {
                "quote": "Believe in the me that believes in you!",
                "character": "Kamina",
                "anime": "Gurren Lagann"
            },
            {
                "quote": "People's dreams... have no end!",
                "character": "Marshall D. Teach",
                "anime": "One Piece"
            },
            {
                "quote": "It's not the face that makes someone a monster; it's the choices they make with their lives.",
                "character": "Naruto Uzumaki",
                "anime": "Naruto"
            },
            {
                "quote": "The world isn't perfect. But it's there for us, doing the best it can. That's what makes it so damn beautiful.",
                "character": "Roy Mustang",
                "anime": "Fullmetal Alchemist"
            },
            {
                "quote": "If you don't like your destiny, don't accept it. Instead, have the courage to change it the way you want it to be.",
                "character": "Naruto Uzumaki",
                "anime": "Naruto"
            },
            {
                "quote": "I am the hope of the universe. I am the answer to all living things that cry out for peace.",
                "character": "Goku",
                "anime": "Dragon Ball Z"
            },
            {
                "quote": "A person grows up when they can overcome hardships. To be able to protect something important.",
                "character": "Jiraiya",
                "anime": "Naruto"
            },
            {
                "quote": "Knowing you're different is only the beginning. If you accept these differences you'll be able to get past them and grow even closer.",
                "character": "Misato Katsuragi",
                "anime": "Neon Genesis Evangelion"
            }
        ]
        
        return random.choice(quotes)
    
    async def close(self):
        """Close the session"""
        if self.session and not self.session.closed:
            await self.session.close()
            print("✅ AniListAPI session closed")

# =========== IMAGE GENERATOR CLASS ===========
class ImageGenerator:
    """Image generator for anime cards"""
    
    def __init__(self):
        self.font_cache = {}
        self.image_cache = {}
        
        if not HAS_PILLOW:
            print("⚠️ Pillow not available, image generation disabled")
        
        print("✅ ImageGenerator initialized")
    
    def _get_font(self, size: int, bold: bool = False):
        """Get font with fallback"""
        try:
            # Try to load system fonts
            if bold:
                try:
                    return ImageFont.truetype("arialbd.ttf", size)
                except:
                    return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
            else:
                try:
                    return ImageFont.truetype("arial.ttf", size)
                except:
                    return ImageFont.truetype("DejaVuSans.ttf", size)
        except:
            # Ultimate fallback
            return ImageFont.load_default()
    
    async def _download_image(self, url: str) -> Optional[Image.Image]:
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
    
    def _wrap_text(self, text: str, max_width: int, font) -> List[str]:
        """Wrap text to fit within width"""
        if not text:
            return []
        
        lines = []
        words = text.split()
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = font.getbbox(test_line)
            width = bbox[2] - bbox[0]
            
            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
    async def generate_anime_card(self, anime_data: Dict) -> Optional[str]:
        """Generate anime info card image"""
        if not HAS_PILLOW:
            return None
        
        try:
            # Create canvas
            width, height = 800, 1000
            image = Image.new('RGB', (width, height), '#0f172a')  # Dark blue background
            draw = ImageDraw.Draw(image)
            
            # Download cover image
            cover_url = anime_data.get('coverImage', {}).get('extraLarge')
            cover_img = None
            
            if cover_url:
                cover_img = await self._download_image(cover_url)
                if cover_img:
                    # Resize and add to image
                    cover_img = cover_img.resize((800, 300))
                    
                    # Add dark overlay
                    overlay = Image.new('RGBA', (800, 300), (15, 23, 42, 180))
                    cover_img.paste(overlay, (0, 0), overlay)
                    
                    image.paste(cover_img, (0, 0))
            
            # Title
            title = anime_data.get('title', {}).get('english') or anime_data.get('title', {}).get('romaji', 'N/A')
            title_font = self._get_font(36, bold=True)
            draw.text((50, 320), title, fill='white', font=title_font)
            
            # Score badge
            score = anime_data.get('averageScore')
            if score:
                # Draw circular badge
                draw.ellipse([(50, 380), (110, 440)], 
                           fill='#f59e0b' if score >= 80 else '#10b981' if score >= 60 else '#ef4444')
                score_font = self._get_font(24, bold=True)
                draw.text((63, 390), str(score), fill='white', font=score_font)
                draw.text((120, 395), "Score", fill='#94a3b8', font=self._get_font(16))
            
            # Status
            status = anime_data.get('status', 'N/A').capitalize()
            status_color = {
                'Finished': '#10b981',
                'Releasing': '#3b82f6',
                'Not yet released': '#f59e0b',
                'Cancelled': '#ef4444',
                'Hiatus': '#8b5cf6'
            }.get(status, '#64748b')
            
            draw.rounded_rectangle([(200, 380), (350, 420)], radius=10, fill=status_color)
            draw.text((210, 385), status, fill='white', font=self._get_font(18, bold=True))
            
            # Info section
            y_offset = 450
            
            # Format and episodes
            format_text = anime_data.get('format', 'N/A')
            episodes = anime_data.get('episodes', 'N/A')
            info_text = f"{format_text} • {episodes} episodes"
            draw.text((50, y_offset), info_text, fill='#cbd5e1', font=self._get_font(18))
            y_offset += 40
            
            # Genres
            genres = anime_data.get('genres', [])[:5]
            if genres:
                genre_text = " • ".join(genres)
                draw.text((50, y_offset), genre_text, fill='#60a5fa', font=self._get_font(16))
                y_offset += 40
            
            # Studios
            studios = [edge.get('node', {}).get('name') for edge in anime_data.get('studios', {}).get('edges', [])[:3]]
            if studios:
                studio_text = f"Studio: {', '.join(studios)}"
                draw.text((50, y_offset), studio_text, fill='#cbd5e1', font=self._get_font(16))
                y_offset += 40
            
            # Description
            description = anime_data.get('description', 'No description available.')
            # Remove HTML tags
            description = re.sub(r'<[^>]+>', '', description)[:400]
            
            desc_y = 580
            draw.text((50, desc_y), "📖 Description:", fill='#fbbf24', font=self._get_font(18, bold=True))
            desc_y += 40
            
            # Wrap and draw description
            desc_lines = self._wrap_text(description, 90, self._get_font(14))
            for i, line in enumerate(desc_lines[:6]):
                draw.text((70, desc_y + i*25), line, fill='#e2e8f0', font=self._get_font(14))
            
            # Stats section
            stats_y = 750
            
            # Popularity and favorites
            popularity = anime_data.get('popularity', 'N/A')
            favorites = anime_data.get('favourites', 'N/A')
            
            stats_text = f"📊 Popularity: #{popularity} | ❤️ Favorites: {favorites}"
            draw.text((50, stats_y), stats_text, fill='#cbd5e1', font=self._get_font(16))
            
            # Footer
            footer_y = height - 50
            draw.text((50, footer_y), "AnimeKuun Bot • anilist.co", fill='#64748b', font=self._get_font(14))
            
            # Save image
            import tempfile
            import uuid
            temp_dir = tempfile.gettempdir()
            filename = f"anime_{anime_data.get('id', uuid.uuid4())}.jpg"
            output_path = os.path.join(temp_dir, filename)
            
            image.save(output_path, 'JPEG', quality=90)
            print(f"✅ Generated image: {output_path}")
            
            return output_path
            
        except Exception as e:
            print(f"Image generation error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def generate_user_card(self, user_data: Dict) -> Optional[str]:
        """Generate user profile card"""
        if not HAS_PILLOW:
            return None
        
        try:
            # Create canvas
            width, height = 800, 1000
            image = Image.new('RGB', (width, height), '#0f172a')
            draw = ImageDraw.Draw(image)
            
            # Download avatar
            avatar_url = user_data.get('avatar', {}).get('large')
            avatar_img = None
            
            if avatar_url:
                avatar_img = await self._download_image(avatar_url)
                if avatar_img:
                    # Create circular avatar
                    avatar_img = avatar_img.resize((200, 200))
                    
                    # Create circular mask
                    mask = Image.new('L', (200, 200), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    mask_draw.ellipse([(0, 0), (200, 200)], fill=255)
                    
                    # Apply mask
                    avatar_img.putalpha(mask)
                    
                    image.paste(avatar_img, (50, 50), avatar_img)
            
            # Username
            username = user_data.get('name', 'N/A')
            name_font = self._get_font(42, bold=True)
            draw.text((270, 70), username, fill='white', font=name_font)
            
            # About section
            about = user_data.get('about', 'No bio available.')[:300]
            
            y_offset = 220
            draw.text((50, y_offset), "📝 About:", fill='#3b82f6', font=self._get_font(18, bold=True))
            y_offset += 40
            
            about_lines = self._wrap_text(about, 50, self._get_font(14))
            for i, line in enumerate(about_lines[:6]):
                draw.text((70, y_offset + i*25), line, fill='#e2e8f0', font=self._get_font(14))
            
            # Statistics
            stats = user_data.get('statistics', {}).get('anime', {})
            
            # Stats boxes
            box_width = 150
            box_height = 80
            box_margin = 20
            stats_y = 450 if about_lines else 400
            
            stats_data = [
                ("🎬 Total", str(stats.get('count', 0))),
                ("⭐ Mean Score", f"{stats.get('meanScore', 0)}"),
                ("⏱️ Minutes", f"{stats.get('minutesWatched', 0):,}"),
                ("📺 Episodes", f"{stats.get('episodesWatched', 0):,}")
            ]
            
            for i, (label, value) in enumerate(stats_data):
                x = 50 + (i % 2) * (box_width + box_margin)
                y = stats_y + (i // 2) * (box_height + box_margin)
                
                # Draw box
                draw.rounded_rectangle([(x, y), (x + box_width, y + box_height)], 
                                      radius=15, fill='#1e293b')
                
                # Draw label and value
                draw.text((x + 10, y + 10), label, fill='#94a3b8', font=self._get_font(14))
                draw.text((x + 10, y + 40), value, fill='white', font=self._get_font(20, bold=True))
            
            # Footer
            footer_y = height - 50
            draw.text((50, footer_y), "AnimeKuun Bot • User Profile", fill='#64748b', font=self._get_font(14))
            
            # Save image
            import tempfile
            import uuid
            temp_dir = tempfile.gettempdir()
            filename = f"user_{user_data.get('id', uuid.uuid4())}.jpg"
            output_path = os.path.join(temp_dir, filename)
            
            image.save(output_path, 'JPEG', quality=90)
            print(f"✅ Generated user image: {output_path}")
            
            return output_path
            
        except Exception as e:
            print(f"User card generation error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def generate_character_card(self, character_data: Dict) -> Optional[str]:
        """Generate character card"""
        if not HAS_PILLOW:
            return None
        
        try:
            # Create canvas
            width, height = 800, 1000
            image = Image.new('RGB', (width, height), '#0f172a')
            draw = ImageDraw.Draw(image)
            
            # Download character image
            char_url = character_data.get('image', {}).get('large')
            char_img = None
            
            if char_url:
                char_img = await self._download_image(char_url)
                if char_img:
                    # Resize and position
                    char_img = char_img.resize((400, 500))
                    image.paste(char_img, (0, 0))
            
            # Character name
            name = character_data.get('name', {}).get('full', 'N/A')
            name_font = self._get_font(48, bold=True)
            draw.text((420, 50), name, fill='white', font=name_font)
            
            # Character info
            y_offset = 200
            
            # Gender and age
            gender = character_data.get('gender', 'Unknown')
            age = character_data.get('age', 'Unknown')
            draw.text((420, y_offset), f"⚧ {gender} • 🎂 {age}", fill='#3b82f6', font=self._get_font(18))
            y_offset += 40
            
            # Favorites
            favorites = character_data.get('favourites', 0)
            draw.text((420, y_offset), f"❤️ {favorites:,} favorites", fill='#ef4444', font=self._get_font(18))
            y_offset += 60
            
            # Description
            description = character_data.get('description', 'No description available.')
            description = re.sub(r'<[^>]+>', '', description)
            
            draw.text((420, y_offset), "📖 Description:", fill='#fbbf24', font=self._get_font(16, bold=True))
            y_offset += 40
            
            desc_lines = self._wrap_text(description, 40, self._get_font(14))
            for i, line in enumerate(desc_lines[:8]):
                draw.text((440, y_offset + i*25), line, fill='#e2e8f0', font=self._get_font(14))
            
            # Footer
            footer_y = height - 50
            draw.text((50, footer_y), "AnimeKuun Bot • Character Card", fill='#64748b', font=self._get_font(14))
            
            # Save image
            import tempfile
            import uuid
            temp_dir = tempfile.gettempdir()
            filename = f"character_{character_data.get('id', uuid.uuid4())}.jpg"
            output_path = os.path.join(temp_dir, filename)
            
            image.save(output_path, 'JPEG', quality=90)
            print(f"✅ Generated character image: {output_path}")
            
            return output_path
            
        except Exception as e:
            print(f"Character card generation error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def close(self):
        """Cleanup"""
        print("✅ ImageGenerator cleaned up")

# =========== SETUP LOGGING ===========
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("✅ anilist_api.py loaded successfully")
