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

    def fetch_country_news(self, countries: List[str] = ['us', 'gb', 'jp', 'cn', 'in', 'ru', 'de', 'fr', 'au']) -> int:
        """
        Fetch top headlines for specific countries.
        GNews allows filtering by country code.
        """
        if not self.api_key:
            return 0

        total_saved = 0
        for country in countries:
            try:
                logger.info(f"GNews: Fetching headlines for {country}...")
                params = {
                    "lang": "en" if country not in ['jp', 'cn', 'ru', 'de', 'fr'] else None,
                    "country": country,
                    "max": 10,
                    "apikey": self.api_key
                }
                
                # For non-English countries, GNews often works better with localized lang or no lang constraint
                if country == 'jp': params['lang'] = 'ja'
                if country == 'cn': params['lang'] = 'zh'
                if country == 'ru': params['lang'] = 'ru'
                if country == 'de': params['lang'] = 'de'
                if country == 'fr': params['lang'] = 'fr'
                
                response = requests.get(f"{self.base_url}/top-headlines", params=params)
                if response.status_code == 200:
                    articles = response.json().get('articles', [])
                    total_saved += self._save_articles(articles, country)
                else:
                    logger.error(f"GNews error for {country}: {response.status_code} - {response.text}")
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
