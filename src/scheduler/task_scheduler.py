import time
from typing import List, Dict, Any
# import logging
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from src.config.settings import SCHEDULE_TIME
from src.database.models import SessionLocal, RawNews
from src.collectors.news_api import NewsCollector
from src.verification.verifier import VerificationEngine
from src.analysis.llm_analyzer import LLMAnalyzer
from src.digest.generator import DigestGenerator
from src.database.models import VerifiedNews, RawNews
from src.delivery.notifications import NotificationManager

from loguru import logger

async def run_news_cycle():
    logger.info("Starting Daily News Cycle...")
    db = SessionLocal()
    
    try:
        # 1. Collect
        logger.info("Step 1: Collection")
        
        api_collector = NewsCollector()
        api_count = api_collector.fetch_recent_news()
        
        from src.collectors.rss_collector import RSSCollector
        rss_collector = RSSCollector()
        rss_count = rss_collector.fetch_recent_news()
        
        total_count = api_count + rss_count
        logger.info(f"Collected {total_count} new articles.")
        
        if total_count == 0 and db.query(RawNews).count() == 0:
            logger.warning("No news collected and DB is empty. Aborting cycle.")
            return

        # 2. Verify
        logger.info("Step 2: Verification")
        verifier = VerificationEngine()
        unprocessed = db.query(RawNews).filter(RawNews.processed == False).all()
        verified_count = verifier.verify_batch(db, [n.id for n in unprocessed])
        logger.info(f"Verified {verified_count} articles.")

        # 3. Analyze (Parallelized)
        logger.info("Step 3: Analysis (Parallel)")
        analyzer = LLMAnalyzer()
        unanalyzed = db.query(VerifiedNews).filter(VerifiedNews.impact_score == None).all()
        
        if unanalyzed:
            # Prepare batch
            articles_to_analyze = [{"title": n.title, "content": n.content} for n in unanalyzed]
            analysis_results = await analyzer.analyze_batch(articles_to_analyze)
            
            # Map results back
            for news, result in zip(unanalyzed, analysis_results):
                news.summary_bullets = result.get("summary_bullets", [])
                news.why_it_matters = result.get("why_it_matters", "")
                news.who_is_affected = result.get("who_is_affected", "")
                news.short_term_impact = result.get("short_term_impact", "")
                news.long_term_impact = result.get("long_term_impact", "")
                news.sentiment = result.get("sentiment", "Neutral")
                news.impact_tags = result.get("impact_tags", [])
                news.bias_rating = result.get("bias_rating", "Neutral")
                news.impact_score = result.get("impact_score", 5)
                
                # Classification logic
                cat = result.get("category", "General")
                if news.raw_news and news.raw_news.source_id:
                    sid = news.raw_news.source_id.lower()
                    # (Mapping logic remains same)
                    mapping = {
                        "sport": "Sports", "espn": "Sports", "tech": "Technology", "wired": "Technology",
                        "politics": "Politics", "politico": "Politics", "business": "Business & Economy",
                        "cnbc": "Business & Economy", "wsj": "Business & Economy", "world": "World News",
                        "aljazeera": "World News", "india": "India / Local News", "ndtv": "India / Local News",
                        "science": "Science & Health", "nasa": "Science & Health", "mit": "AI & Machine Learning",
                        "ai": "AI & Machine Learning"
                    }
                    for key, val in mapping.items():
                        if key in sid:
                            cat = val
                            break
                news.category = cat
            
            db.commit()
            logger.info(f"Analyzed {len(unanalyzed)} articles in parallel.")

        # 4. Generate Digest
        logger.info("Step 4: Digest Generation")
        generator = DigestGenerator()
        digest = generator.create_daily_digest(db)

        # 5. Deliver
        if digest:
            if "brief" in digest:
                NotificationManager.send_daily_brief(db, digest["brief"])
            if "top_stories" in digest:
                for story in digest["top_stories"][:2]:
                    NotificationManager.notify_subscribers(db, story.get("category", "General"), story["title"], story["url"])

    except Exception as e:
        logger.error(f"Error in news cycle: {e}", exc_info=True)
    finally:
        db.close()
        logger.info("News Cycle Completed.")

def start_scheduler():
    scheduler = BackgroundScheduler()
    
    # Run every 15 minutes (Balanced Update Cycle)
    from datetime import datetime, timedelta
    run_date = datetime.now() + timedelta(seconds=10)
    
    # helper to run async in background
    def _run_async_cycle():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_news_cycle())
        loop.close()

    scheduler.add_job(_run_async_cycle, 'interval', minutes=15, next_run_time=run_date)
    
    # Daily Newspaper Update
    scheduler.add_job(
        _run_async_cycle, 
        'cron', 
        hour=6, 
        minute=30, 
        timezone='Asia/Kolkata',
        id='daily_newspaper_update'
    )
    
    scheduler.start()
    return scheduler
