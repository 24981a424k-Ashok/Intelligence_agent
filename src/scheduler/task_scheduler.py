import time
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

def run_news_cycle():
    logger.info("Starting Daily News Cycle...")
    db = SessionLocal()
    
    try:
        # 1. Collect
        logger.info("Step 1: Collection")
        
        # NewsAPI
        api_collector = NewsCollector()
        api_count = api_collector.fetch_recent_news()
        
        # RSS
        from src.collectors.rss_collector import RSSCollector
        rss_collector = RSSCollector()
        rss_count = rss_collector.fetch_recent_news()
        
        total_count = api_count + rss_count
        logger.info(f"Collected {total_count} new articles ({api_count} API, {rss_count} RSS).")
        
        if total_count == 0 and db.query(RawNews).count() == 0:
            logger.warning("No news collected and DB is empty. Aborting cycle.")
            return

        # 2. Verify
        logger.info("Step 2: Verification")
        verifier = VerificationEngine()
        # Get unprocessed raw news
        unprocessed = db.query(RawNews).filter(RawNews.processed == False).all()
        verified_count = verifier.verify_batch(db, [n.id for n in unprocessed])
        logger.info(f"Verified {verified_count} articles.")

        # 3. Analyze
        logger.info("Step 3: Analysis")
        analyzer = LLMAnalyzer()
        # Get verified but unanalyzed news (assuming we check impacts or newly created verified items)
        # For simplicity, we just check items without analysis fields (e.g. impact_score is None)
        unanalyzed = db.query(VerifiedNews).filter(VerifiedNews.impact_score == None).all()
        
        for news in unanalyzed:
            result = analyzer.analyze_article(news.title, news.content)
            
            news.summary_bullets = result.get("summary_bullets", [])
            news.why_it_matters = result.get("why_it_matters", "")
            news.who_is_affected = result.get("who_is_affected", "")
            news.short_term_impact = result.get("short_term_impact", "")
            news.long_term_impact = result.get("long_term_impact", "")
            news.sentiment = result.get("sentiment", "Neutral")
            news.impact_tags = result.get("impact_tags", [])
            news.bias_rating = result.get("bias_rating", "Neutral")
            news.impact_score = result.get("impact_score", 5)
            
            # Robust Classification: Override LLM category based on Source ID if known
            cat = result.get("category", "General")
            if news.raw_news and news.raw_news.source_id:
                sid = news.raw_news.source_id.lower()
                if "sport" in sid or "espn" in sid:
                    cat = "Sports"
                elif "tech" in sid or "wired" in sid:
                    cat = "Technology"
                elif "politics" in sid or "politico" in sid:
                    cat = "Politics"
                elif "business" in sid or "cnbc" in sid or "wsj" in sid:
                    cat = "Business & Economy"
                elif "world" in sid or "aljazeera" in sid:
                    cat = "World News"
                elif "india" in sid or "ndtv" in sid:
                    cat = "India / Local News"
                elif "science" in sid or "webmd" in sid or "nasa" in sid:
                    cat = "Science & Health"
                elif "education" in sid or "chronicle" in sid:
                    cat = "Education"
                elif "variety" in sid or "hollywood" in sid:
                    cat = "Entertainment"
                elif "mit" in sid or "ai" in sid:
                    cat = "AI & Machine Learning"
                elif "grist" in sid or "natgeo" in sid or "earth" in sid:
                    cat = "Environment & Climate"
                elif "lifestyle" in sid or "travel" in sid:
                    cat = "Lifestyle & Wellness"
                elif "defense" in sid or "military" in sid:
                    cat = "Defense & Security"
            
            news.category = cat
            
        db.commit()
        logger.info(f"Analyzed {len(unanalyzed)} articles.")

        # 4. Generate Digest
        logger.info("Step 4: Digest Generation")
        generator = DigestGenerator()
        digest = generator.create_daily_digest(db)
        logger.info("Digest generated.")

        # 5. Deliver
        logger.info("Step 5: Delivery - sending notifications...")
        from src.delivery.notifications import NotificationManager
        
        # 5a. Send Daily Brief
        if digest and "brief" in digest:
            NotificationManager.send_daily_brief(db, digest["brief"])

        # 5b. Notify for top stories in the digest
        if digest and "top_stories" in digest:
             for story in digest["top_stories"][:2]: # Notify top 2 for brevity
                 NotificationManager.notify_subscribers(db, story.get("category", "General"), story["title"], story["url"])

    except Exception as e:
        logger.error(f"Error in news cycle: {e}", exc_info=True)
    finally:
        db.close()
        logger.info("News Cycle Completed.")

def start_scheduler():
    scheduler = BackgroundScheduler()
    # Parse time "06:00"
    hour, minute = map(int, SCHEDULE_TIME.split(":"))
    
    # Run every 2 minutes (Frequent Update Cycle)
    from datetime import datetime, timedelta
    # Run immediately (after 10s buffer) + every 2 minutes
    run_date = datetime.now() + timedelta(seconds=10)
    scheduler.add_job(run_news_cycle, 'interval', minutes=2, next_run_time=run_date)
    
    # Daily Newspaper Update at 6:30 AM IST
    scheduler.add_job(
        run_news_cycle, 
        'cron', 
        hour=6, 
        minute=30, 
        timezone='Asia/Kolkata',
        id='daily_newspaper_update'
    )
    
    # Also add a one-off job to run immediately on startup if DB is empty for demo purposes?
    # Or just rely on manual trigger.
    
    scheduler.start()
    return scheduler
