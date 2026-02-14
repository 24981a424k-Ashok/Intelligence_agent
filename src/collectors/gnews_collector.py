import os
import requests
import logging
from datetime import datetime
from typing import List, Dict, Any
from src.database.models import SessionLocal, RawNews
from dotenv import load_dotenv

from src.config import settings

load_dotenv()
logger = logging.getLogger(__name__)

class GNewsCollector:
    def __init__(self):
        self.api_key = settings.GNEWS_API_KEY
        self.base_url = "https://gnews.io/api/v4"
        if not self.api_key:
            logger.warning("GNews API Key is missing!")

    def fetch_country_news(self, countries: List[str] = ['us', 'gb', 'jp', 'cn', 'in', 'ru', 'de', 'fr', 'au', 'sg', 'ae']) -> int:
        """
        Fetch specialized intelligence and top headlines for specific countries.
        """
        if not self.api_key:
            return 0

        total_saved = 0
        
        # Specialized Country Features Mapping
        specialized_features = {
            'us': '("Stock Market" OR "Fed News" OR "Corporate News" OR "AI" OR "Tech" OR "Startup")',
            'gb': '("Policy" OR "Regulation" OR "Global Finance" OR "UK–EU relations")',
            'cn': '("Economy" OR "Trade News" OR "Manufacturing" OR "Supply-chain" OR "Tech" OR "AI")',
            'de': '("EU economy" OR "Industry news" OR "Energy policy" OR "Climate policy")',
            'jp': '("Technology" OR "Robotics" OR "Market" OR "Currency")',
            'sg': '("Startup" OR "Fintech" OR "ASEAN economy")',
            'ae': '("Energy" OR "Oil markets" OR "Infrastructure" OR "Mega-projects" OR "Geopolitics")',
            'in': '("Policy" OR "Market" OR "Economy" OR "Tech" OR "Startup" OR "Infrastructure")'
        }

        # OPTIMIZATION: Rotate countries to avoid Rate Limits (100 req/day limit)
        # 15 min cycle = 96 runs/day. To stay under 100, we can only make ~1 request per run.
        # But we need density. Let's pick 2 random countries per cycle.
        # Over 24 hours, all countries will be covered multiple times.
        import random
        random.shuffle(countries)
        target_countries = countries[:2] # Pick top 2 after shuffle
        logger.info(f"GNews: Rotating targets for this cycle: {target_countries}")

        for country in target_countries:
            try:
                queries = [None] # Default to top headlines
                if country in specialized_features:
                    queries.append(specialized_features[country])

                for query in queries:
                    endpoint = "search" if query else "top-headlines"
                    logger.info(f"GNews: Fetching {endpoint} for {country} (Query: {query})...")
                    
                    params = {
                        "lang": "en" if country not in ['jp', 'cn', 'ru', 'de', 'fr'] else None,
                        "country": country,
                        "max": 10,
                        "apikey": self.api_key
                    }
                    
                    if query: params["q"] = query
                    
                    # For non-English countries, GNews often works better with localized lang or no lang constraint
                    if not query: # Only override lang for general top-headlines
                        if country == 'jp': params['lang'] = 'ja'
                        if country == 'cn': params['lang'] = 'zh'
                        if country == 'ru': params['lang'] = 'ru'
                        if country == 'de': params['lang'] = 'de'
                        if country == 'fr': params['lang'] = 'fr'
                    
                    response = requests.get(f"{self.base_url}/{endpoint}", params=params)
                    if response.status_code == 200:
                        articles = response.json().get('articles', [])
                        total_saved += self._save_articles(articles, country)
                    else:
                        logger.error(f"GNews error for {country} ({endpoint}): {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"GNews fetch failed for {country}: {e}")
        
        return total_saved

    def _save_articles(self, articles: List[Dict[str, Any]], country_code: str) -> int:
        session = SessionLocal()
        count = 0
        try:
            for article in articles:
                url = article.get('url')
                if not url:
                    continue
                
                # Check for duplicates
                exists = session.query(RawNews).filter(RawNews.url == url).first()
                if exists:
                    continue
                
                # GNews date format: 2024-02-13T12:00:00Z
                pub_date = article.get('publishedAt')
                try:
                    pub_dt = datetime.strptime(pub_date, "%Y-%m-%dT%H:%M:%SZ")
                except:
                    pub_dt = datetime.utcnow()

                raw_news = RawNews(
                    source_name=article.get('source', {}).get('name', 'GNews'),
                    author=None,
                    title=article.get('title'),
                    description=article.get('description'),
                    url=url,
                    url_to_image=article.get('image'),
                    published_at=pub_dt,
                    content=article.get('content'),
                    country=country_code
                )
                session.add(raw_news)
                count += 1
            
            session.commit()
            logger.info(f"GNews: Saved {count} articles for {country_code}.")
            return count
        except Exception as e:
            logger.error(f"GNews database error: {e}")
            session.rollback()
            return 0
        finally:
            session.close()

if __name__ == "__main__":
    collector = GNewsCollector()
    collector.fetch_country_news()
