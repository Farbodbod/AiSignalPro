# backend/core/news_fetcher.py (v2.0 - The Intelligent Caching Engine)
import asyncio
import logging
import os
from typing import List, Dict, Optional, Set
import httpx
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class NewsFetcher:
    """
    A specialized module to fetch relevant financial and crypto news.
    v2.0 (The Intelligent Caching Engine): This version introduces a powerful
    in-memory caching mechanism with a configurable TTL (Time-to-Live). This
    drastically reduces redundant API calls, permanently solving the rate limit
    issue, and significantly improving system performance and efficiency.
    """

    def __init__(self):
        self.api_key = os.getenv("NEWS_API_KEY")
        if not self.api_key:
            logger.warning("NEWS_API_KEY not found. NewsFetcher will be disabled.")
        self.base_url = "https://newsapi.org/v2/everything"
        self.client = httpx.AsyncClient(timeout=10.0)
        
        # ✅ CACHING ENGINE: Initialize cache and TTL
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = timedelta(minutes=30) # Cache news for 30 minutes

    async def get_headlines(self, symbol: str) -> Optional[List[str]]:
        """
        Fetches the latest and most relevant news headlines for a given symbol,
        utilizing an intelligent caching system to avoid redundant API calls.
        """
        if not self.api_key:
            return None

        base_asset = symbol.split('/')[0]
        now = datetime.utcnow()

        # ✅ CACHING LOGIC: Check for fresh, cached data first
        if base_asset in self.cache:
            cached_data = self.cache[base_asset]
            if now - cached_data['timestamp'] < self.cache_ttl:
                logger.info(f"Returning cached news for {base_asset}. Cache is fresh.")
                return cached_data['headlines']
            else:
                logger.info(f"Cache for {base_asset} is stale. Fetching new data.")

        # --- If cache is empty or stale, proceed with API call ---
        macro_keywords = [
            "crypto regulation", "SEC", "inflation", "interest rate", "Fed",
            "Bitcoin ETF", "Ethereum ETF", "Elon Musk", "Donald Trump", 
            "war", "geopolitical", "conflict"
        ]
        
        query = f'("{base_asset}" OR "{symbol.split("/")[0]}") OR ({" OR ".join(macro_keywords)})'
        from_date = (now - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S')

        params = {
            'q': query,
            'apiKey': self.api_key,
            'language': 'en',
            'sortBy': 'relevancy',
            'pageSize': 20
        }

        try:
            logger.debug(f"Fetching news from API for query: {query}")
            response = await self.client.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            articles = data.get('articles', [])
            if not articles:
                logger.info(f"No recent news articles found for query: {query}")
                return []

            headlines: Set[str] = set()
            for article in articles:
                title = article.get('title')
                if title and "[Removed]" not in title:
                    headlines.add(title.strip())
            
            final_headlines = list(headlines)[:10]

            # ✅ CACHING LOGIC: Store the successful result before returning
            self.cache[base_asset] = {'headlines': final_headlines, 'timestamp': now}
            logger.info(f"Successfully fetched and cached {len(final_headlines)} unique headlines for {symbol}.")
            return final_headlines

        except httpx.HTTPStatusError as e:
            logger.error(f"NewsAPI request failed with status {e.response.status_code}: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred in NewsFetcher: {e}", exc_info=True)
            return None

    async def close(self):
        """Closes the HTTP client."""
        await self.client.aclose()

