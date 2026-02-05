import aiohttp
import json
import redis
from typing import Dict, List

class AniListAPI:
    """Minimal AniList API wrapper"""
    
    def __init__(self, redis_client):
        self.base_url = "https://graphql.anilist.co"
        self.redis = redis_client
        self.session = None
        
    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def search_anime(self, query: str, page: int = 1, per_page: int = 10) -> List[Dict]:
        """Search for anime"""
        graphql_query = """
        query ($search: String, $page: Int, $perPage: Int) {
          Page(page: $page, perPage: $perPage) {
            media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
              id
              title {
                romaji
                english
              }
              averageScore
              trending
              popularity
              format
              episodes
              status
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
            session = await self._get_session()
            async with session.post(
                self.base_url,
                json={"query": graphql_query, "variables": variables},
                headers={"Content-Type": "application/json"}
            ) as response:
                result = await response.json()
                return result.get("data", {}).get("Page", {}).get("media", [])
        except Exception as e:
            print(f"API Error: {e}")
            return []
    
    async def get_anime(self, anime_id: int) -> Dict:
        """Get anime details"""
        graphql_query = """
        query ($id: Int) {
          Media(id: $id, type: ANIME) {
            id
            title {
              romaji
              english
            }
            format
            status
            episodes
            averageScore
            genres
            description
            coverImage {
              large
            }
            siteUrl
          }
        }
        """
        
        variables = {"id": anime_id}
        
        try:
            session = await self._get_session()
            async with session.post(
                self.base_url,
                json={"query": graphql_query, "variables": variables},
                headers={"Content-Type": "application/json"}
            ) as response:
                result = await response.json()
                return result.get("data", {}).get("Media", {})
        except Exception as e:
            print(f"API Error: {e}")
            return {}
    
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
              averageScore
              trending
              popularity
              format
              episodes
              status
            }
          }
        }
        """
        
        variables = {"perPage": per_page}
        
        try:
            session = await self._get_session()
            async with session.post(
                self.base_url,
                json={"query": graphql_query, "variables": variables},
                headers={"Content-Type": "application/json"}
            ) as response:
                result = await response.json()
                return result.get("data", {}).get("Page", {}).get("media", [])
        except Exception as e:
            print(f"API Error: {e}")
            return []
    
    async def close(self):
        """Close session"""
        if self.session and not self.session.closed:
            await self.session.close()

class ImageGenerator:
    """Dummy image generator"""
    def __init__(self):
        pass
    
    async def generate_anime_card(self, *args, **kwargs):
        return "dummy.jpg"
    
    async def generate_user_card(self, *args, **kwargs):
        return "dummy.jpg"
