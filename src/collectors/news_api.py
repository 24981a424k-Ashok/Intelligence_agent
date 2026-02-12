from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any
from newsapi import NewsApiClient
from src.config.settings import NEWS_API_KEYS
from src.database.models import SessionLocal, RawNews

logger = logging.getLogger(__name__)

class NewsCollector:
    def __init__(self):
        self.api_keys = NEWS_API_KEYS
        if not self.api_keys:
            logger.warning("No NewsAPI Keys found!")
            self.clients = []
        else:
            self.clients = [NewsApiClient(api_key=key) for key in self.api_keys]

    def fetch_recent_news(self, query: str = None, domains: str = None, categories: str = None) -> int:
        """
        Fetch news from the last 24 hours using all available API keys.
        Returns total count of new articles saved.
        """
        if not self.clients:
            logger.error("No NewsAPI clients initialized.")
            return 0

        all_articles = []
        
        # Iterate through all available clients to collect more data
        for i, client in enumerate(self.clients):
            try:
                logger.info(f"Fetching news cycle with API Key {i+1}/{len(self.clients)}...")
                
                # Fetch top headlines
                response = client.get_top_headlines(language='en', page_size=100)
                if response.get('status') == 'ok':
                    all_articles.extend(response.get('articles', []))
                
                # Dedicated Business Fetch
                biz_response = client.get_top_headlines(language='en', category='business', country='in', page_size=100)
                if biz_response.get('status') == 'ok':
                    all_articles.extend(biz_response.get('articles', []))

                # Dedicated Technology/AI Fetch (Rotating queries for variety)
                tech_queries = ['technology', 'artificial intelligence', 'machine learning', 'crypto']
                q = tech_queries[i % len(tech_queries)]
                search_response = client.get_everything(q=q, language='en', sort_by='publishedAt', page_size=100)
                if search_response.get('status') == 'ok':
                    all_articles.extend(search_response.get('articles', []))

            except Exception as e:
                logger.error(f"Error fetching news with key {i+1}: {e}")
                continue

        saved_count = self._save_articles(all_articles)
        return saved_count
            
    def _save_articles(self, articles: List[Dict[str, Any]]) -> int:
        session = SessionLocal()
        count = 0
        seen_urls = set()
        try:
            for article in articles:
                url = article.get('url')
                if not url:
                    continue
                
                # Check for duplicates
                # Check for duplicates (DB + Current Batch)
                if url in seen_urls:
                    continue
                
                exists = session.query(RawNews).filter(RawNews.url == url).first()
                if exists:
                    continue
                
                seen_urls.add(url)
                
                # Parse date
                pub_date = article.get('publishedAt')
                if pub_date:
                    try:
                        # NewsAPI format: 2024-01-23T12:00:00Z
                        pub_dt = datetime.strptime(pub_date, "%Y-%m-%dT%H:%M:%SZ")
                    except ValueError:
                        pub_dt = datetime.utcnow()
                else:
                    pub_dt = datetime.utcnow()

                raw_news = RawNews(
                    source_id=article.get('source', {}).get('id'),
                    source_name=article.get('source', {}).get('name'),
                    author=article.get('author'),
                    title=article.get('title'),
                    description=article.get('description'),
                    url=url,
                    url_to_image=article.get('urlToImage'),
                    published_at=pub_dt,
                    content=article.get('content')
                )
                session.add(raw_news)
                count += 1
            
            session.commit()
            logger.info(f"Saved {count} new articles.")
            return count
        except Exception as e:
            logger.error(f"Database error: {e}")
            session.rollback()
            return 0
        finally:
            session.close()

if __name__ == "__main__":
    # Test run
    collector = NewsCollector()
    collector.fetch_recent_news()
