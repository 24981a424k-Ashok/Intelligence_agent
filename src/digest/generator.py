from datetime import datetime
import json
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from src.database.models import VerifiedNews, DailyDigest

logger = logging.getLogger(__name__)

class DigestGenerator:
    def __init__(self):
        pass
    def create_daily_digest(self, session: Session) -> Dict[str, Any]:
        # Get the 100 most recent verified articles for better variety
        recent_news = session.query(VerifiedNews).order_by(VerifiedNews.created_at.desc()).limit(100).all()
        
        if not recent_news:
            logger.info("No news found for digest.")
            return {}

        # Dynamic Ranking Logic: Impact + Credibility + Freshness Boost
        def calculate_rank_score(news_item):
            # Heavy weight on credibility and impact
            base_score = (news_item.impact_score or 0) * 0.7 + (news_item.credibility_score or 0) * 3
            
            # Freshness Boost: bonus points for articles published recently
            now = datetime.utcnow()
            if news_item.published_at:
                age_hours = (now - news_item.published_at).total_seconds() / 3600
                if age_hours < 3:
                    base_score += 6 # Massive boost for very fresh news
                elif age_hours < 8:
                    base_score += 3
            return base_score

        # Sort all by rank
        sorted_news = sorted(recent_news, key=calculate_rank_score, reverse=True)

        # 1. Headline Rotation: Pick top 10 from top 20 for variety on refresh
        potential_headlines = sorted_news[:20]
        import random
        top_10_pool = random.sample(potential_headlines, min(10, len(potential_headlines)))
        
        # 2. Trending Section (Live Focus): Pick high-momentum stories, specifically India if available
        india_news = [n for n in sorted_news if n.category == "India / Local News"]
        trending_pool = india_news[:10] if india_news else sorted_news[10:20]
        
        # Smart Balancing logic for the rest of the coverage (already existence)
        total_limit = 50
        tech_ai_limit = int(total_limit * 0.15)
        final_list = []
        tech_ai_count = 0
        
        for news in sorted_news:
            if len(final_list) >= total_limit:
                break
            is_tech_ai = news.category in ["Technology", "AI & Machine Learning"]
            if is_tech_ai:
                if tech_ai_count < tech_ai_limit:
                    final_list.append(news)
                    tech_ai_count += 1
            else:
                final_list.append(news)

        # Categorize
        mandatory_categories = [
            "Breaking News", "Politics", "Business & Economy", "Sports", 
            "Technology", "AI & Machine Learning", "World News", "India / Local News",
            "Science & Health", "Education", "Entertainment",
            "Environment & Climate", "Lifestyle & Wellness", "Defense & Security"
        ]
        categories = {cat: [] for cat in mandatory_categories}

        for news in final_list:
            cat = news.category or "Other"
            if cat not in categories:
                continue
            
            categories[cat].append({
                "id": news.id,
                "title": news.title,
                "url": news.raw_news.url if news.raw_news else "#",
                "source_name": news.raw_news.source_name if news.raw_news else "Unknown",
                "published_at": news.published_at.isoformat() if news.published_at else None,
                "image_url": news.raw_news.url_to_image if news.raw_news and news.raw_news.url_to_image else None,
                "summary": news.summary_bullets,
                "why": news.why_it_matters,
                "tags": news.impact_tags,
                "bias": news.bias_rating
            })
            
        digest_data = {
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "top_stories": [
                {
                    "id": n.id,
                    "title": n.title,
                    "url": n.raw_news.url if n.raw_news else "#",
                    "source_name": n.raw_news.source_name if n.raw_news else "Unknown",
                    "published_at": n.published_at.isoformat() if n.published_at else None,
                    "image_url": n.raw_news.url_to_image if n.raw_news and n.raw_news.url_to_image else None,
                    "bullets": n.summary_bullets,
                    "why": n.why_it_matters,
                    "affected": n.who_is_affected,
                    "short_impact": n.short_term_impact,
                    "long_impact": n.long_term_impact,
                    "tags": n.impact_tags,
                    "bias": n.bias_rating,
                    "category": n.category or "General"
                } for n in top_10_pool
            ],
            "trending_news": [
                {
                    "id": n.id,
                    "title": n.title,
                    "summary": n.why_it_matters[:150] + "...", # Short summary for trending card
                    "source_name": n.raw_news.source_name if n.raw_news else "Unknown",
                    "engagement": f"{random.randint(50, 500)}K+ views", # Simulated real-time engagement
                    "time_ago": "Live Now" 
                } for n in trending_pool
            ],
            "brief": [
                {
                    "id": n.id,
                    "title": n.title
                } for n in sorted_news[:5]
            ],
            "categories": categories,
            "insight": "Live Intelligence: High-impact developments detected in real-time.",
            "generated_at": datetime.utcnow().isoformat()
        }
        
        # Save to DB
        digest_entry = DailyDigest(
            content_json=digest_data,
            is_published=False
        )
        session.add(digest_entry)
        session.commit()
        
        return digest_data
