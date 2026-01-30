from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any
from newsapi import NewsApiClient
from src.config.settings import NEWS_API_KEY
from src.database.models import SessionLocal, RawNews

logger = logging.getLogger(__name__)

class NewsCollector:
    def __init__(self):
        self.api_key = NEWS_API_KEY
        if not self.api_key:
            logger.warning("NewsAPI Key is missing!")
            self.client = None
        else:
            self.client = NewsApiClient(api_key=self.api_key)

    def fetch_recent_news(self, query: str = None, domains: str = None, categories: str = None) -> int:
        """
        Fetch news from the last 24 hours and save to DB.
        Returns count of new articles saved.
        """
        if not self.client:
            logger.error("NewsAPI client not initialized.")
            return 0

        # Time range: last 24 hours
        to_date = datetime.utcnow()
        from_date = to_date - timedelta(hours=24)
        
        try:
            # We can customize this to fetch top headlines or everything
            # For this agent, we might want 'everything' for breadth or 'top-headlines' for quality
            # Let's start with top headlines for major categories
            
            categories_list = ['business', 'technology', 'science', 'health']
            all_articles = []
            
            for cat in categories_list:
                response = self.client.get_top_headlines(
                    category=cat,
                    language='en',
                    page_size=100
                )
                if response['status'] == 'ok':
                    articles = response.get('articles', [])
                    # Tag them with category for initial filtering context (optional)
                    for a in articles:
                        a['_initial_category'] = cat
                    all_articles.extend(articles)
            
            # Also fetch general tech/AI specific via 'everything' endpoint if needed
            # But let's stick to headlines to save API calls for now
            
            saved_count = self._save_articles(all_articles)
            return saved_count
            
        except Exception as e:
            logger.error(f"Error fetching news: {e}")
            return 0

    def _save_articles(self, articles: List[Dict[str, Any]]) -> int:
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
