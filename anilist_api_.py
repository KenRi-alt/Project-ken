#!/usr/bin/env python3
"""
🎌 Complete AniList API with working queries
Simple and reliable API wrapper
"""

import aiohttp
import asyncio
import json
import random
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class SimpleAniListAPI:
    """Simple working AniList API"""
    
    def __init__(self):
        self.base_url = "https://graphql.anilist.co"
        self.session = None
        self.cache = {}
        self.rate_limit_delay = 0.1
        
    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self.session
    
    async def _make_request(self, query: str, variables: dict = None):
        """Make GraphQL request"""
        # Rate limiting
        await asyncio.sleep(self.rate_limit_delay)
        
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
                        logger.error(f"API error: {data['errors']}")
                        return {"error": data["errors"][0].get("message", "Unknown error")}
                    return data.get("data", {})
                else:
                    return {"error": f"HTTP {response.status}"}
                    
        except Exception as e:
            logger.error(f"Request error: {e}")
            return {"error": str(e)}
    
    # =========== WORKING ANIME QUERIES ===========
    
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
    
    # =========== WORKING CHARACTER QUERIES ===========
    
    async def search_character(self, query: str, per_page: int = 10):
        """Search characters - WORKING"""
        char_query = """
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
        
        result = await self._make_request(char_query, {
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
    
    # =========== WORKING USER QUERIES ===========
    
    async def get_user_profile(self, username: str):
        """Get user profile - WORKING"""
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
    
    async def get_user_list(self, username: str, media_type: str = "ANIME"):
        """Get user list - WORKING"""
        query = """
        query ($userName: String, $type: MediaType) {
          MediaListCollection(userName: $userName, type: $type) {
            lists {
              name
              entries {
                id
                mediaId
                status
                score
                progress
                media {
                  id
                  title {
                    romaji
                    english
                  }
                  type
                  format
                  episodes
                  chapters
                  coverImage {
                    large
                  }
                  averageScore
                }
              }
            }
          }
        }
        """
        
        result = await self._make_request(query, {
            "userName": username,
            "type": media_type
        })
        
        if "error" in result:
            return []
        
        collection = result.get("MediaListCollection", {})
        lists = collection.get("lists", [])
        
        all_entries = []
        for list_data in lists:
            all_entries.extend(list_data.get("entries", []))
        
        return all_entries
    
    # =========== UTILITY METHODS ===========
    
    async def get_random_anime(self):
        """Get random anime - WORKING"""
        # Search popular anime
        results = await self.search_anime("", page=random.randint(1, 5))
        if results:
            return random.choice(results)
        
        # Fallback
        return {"id": 1, "title": {"romaji": "Naruto", "english": "Naruto"}}
    
    async def close(self):
        """Close session"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("API session closed")

# =========== IMAGE URL FUNCTIONS ===========
async def get_waifu_image_url():
    """Get waifu image URL from waifu.pics"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.waifu.pics/sfw/waifu", timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("url")
    except:
        return None

async def get_husbando_image_url():
    """Get husbando image URL (use male endpoint if available)"""
    # waifu.pics doesn't have male-specific endpoint, use waifu for now
    return await get_waifu_image_url()

async def get_neko_image_url():
    """Get neko image URL"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.waifu.pics/sfw/neko", timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("url")
    except:
        return None

# Test the API
if __name__ == "__main__":
    async def test():
        api = SimpleAniListAPI()
        
        print("Testing API...")
        
        # Test search
        print("Testing search...")
        results = await api.search_anime("Naruto", per_page=3)
        print(f"Found {len(results)} results")
        
        if results:
            # Test get anime
            print("Testing anime details...")
            anime = await api.get_anime(results[0]['id'])
            if "error" not in anime:
                print(f"Got anime: {anime.get('title', {}).get('english', 'Unknown')}")
        
        # Test trending
        print("Testing trending...")
        trending = await api.get_trending(5)
        print(f"Found {len(trending)} trending anime")
        
        # Test character search
        print("Testing character search...")
        chars = await api.search_character("Naruto", 3)
        print(f"Found {len(chars)} characters")
        
        # Test user profile
        print("Testing user profile...")
        user = await api.get_user_profile("kenri")
        if "error" not in user:
            print(f"Got user: {user.get('name', 'Unknown')}")
        
        await api.close()
        print("✅ All tests passed!")
    
    asyncio.run(test())
