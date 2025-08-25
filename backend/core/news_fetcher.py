# backend/core/news_fetcher.py (v1.1 - The Strategic Keyword Upgrade)
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
    It acts as the "Intelligence Reporter" for the AiSignalPro system, gathering
    raw data (headlines) for the Gemini-powered sentiment analysis engine.
    This version includes an upgraded, more strategic list of macro keywords.
    """

    def __init__(self):
        self.api_key = os.getenv("NEWS_API_KEY")
        if not self.api_key:
            logger.warning("NEWS_API_KEY not found in environment variables. NewsFetcher will be disabled.")
        self.base_url = "https://newsapi.org/v2/everything"
        self.client = httpx.AsyncClient(timeout=10.0)

    async def get_headlines(self, symbol: str) -> Optional[List[str]]:
        """
        Fetches the latest and most relevant news headlines for a given symbol
        by querying for both asset-specific and macro-economic keywords.

        Args:
            symbol (str): The symbol to fetch news for (e.g., 'BTC/USDT').

        Returns:
            Optional[List[str]]: A list of unique, relevant headlines, or None if fetching fails.
        """
        if not self.api_key:
            return None

        base_asset = symbol.split('/')[0]
        
        # ✅ STRATEGIC KEYWORD UPGRADE (v1.1)
        # The list is now categorized and includes new narrative and geopolitical keywords.
        macro_keywords = [
            # Economic & Regulatory
            "crypto regulation", "SEC", "inflation", "interest rate", "Fed",
            "Bitcoin ETF", "Ethereum ETF",
            
            # Narrative & Influencers
            "Elon Musk", "Donald Trump", 
            
            # Geopolitical
            "war", "geopolitical", "conflict"
        ]
        
        # Combine asset-specific keywords with macro keywords
        query = f'("{base_asset}" OR "{symbol.split("/")[0]}") OR ({" OR ".join(macro_keywords)})'
        
        # Fetch news from the last 24 hours
        from_date = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S')

        params = {
            'q': query,
            'apiKey': self.api_key,
            'language': 'en',
            'sortBy': 'relevancy',
            'pageSize': 20
        }

        try:
            logger.debug(f"Fetching news for query: {query}")
            response = await self.client.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            articles = data.get('articles', [])
            if not articles:
                logger.info(f"No recent news articles found for query: {query}")
                return []

            # Extract and deduplicate headlines
            headlines: Set[str] = set()
            for article in articles:
                title = article.get('title')
                if title and "[Removed]" not in title:
                    headlines.add(title.strip())
            
            logger.info(f"Successfully fetched {len(headlines)} unique headlines for {symbol}.")
            return list(headlines)[:10] # Return the top 10 unique headlines

        except httpx.HTTPStatusError as e:
            logger.error(f"NewsAPI request failed with status {e.response.status_code}: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred in NewsFetcher: {e}", exc_info=True)
            return None

    async def close(self):
        """Closes the HTTP client."""
        await self.client.aclose()

