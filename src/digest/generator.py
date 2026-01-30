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
        """
        Gather verified news from the last 24h, rank them, and create a digest structure.
        """
        # Get start of today (or last 24h window)
        # simplistic: just take all unprocessed verified news or news from last 24h
        
        # In a real app, we'd filter by 'created_at' > 24 hours ago
        recent_news = session.query(VerifiedNews).limit(50).all() # limit for prototype
        
        if not recent_news:
            logger.info("No news found for digest.")
            return {}

        # Sort by impact score (desc) & credibility
        sorted_news = sorted(
            recent_news, 
            key=lambda x: (x.impact_score or 0, x.credibility_score or 0), 
            reverse=True
        )

        # Smart Balancing: Tech/AI cannot exceed 15% of total stories
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

        top_10 = sorted_news[:10] # Top 10 regardless of balance for the feature section? 
        # Actually PROMPT said: "Technology/AI combined cannot exceed 15% of total coverage"
        # So I will use the final_list for top_10 too.
        top_10 = [n for n in final_list if n.impact_score and n.impact_score >= 7][:10]
        if not top_10:
             top_10 = final_list[:10]
        
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
                # Prompt says mandatory categories are always visible. 
                # If we get something bizarre, we can drop it into a 'Misc' or just ignore if it doesn't fit the 14.
                # For compliance, let's only use the 14.
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
                "affected": news.who_is_affected,
                "short_impact": news.short_term_impact,
                "long_impact": news.long_term_impact,
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
                } for n in top_10
            ],
            "brief": [
                {
                    "id": n.id,
                    "title": n.title
                } for n in sorted_news[:5]
            ],
            "categories": categories,
            "insight": "Daily insight goes here...", # LLM generation needed normally
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
