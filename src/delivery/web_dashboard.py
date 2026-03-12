import os
from loguru import logger
import copy
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Depends, HTTPException, BackgroundTasks
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from src.database.models import SessionLocal, DailyDigest, User, VerifiedNews, Subscription, \
    FlaggedArticle, RawNews, Advertisement, Newspaper
from sqlalchemy import or_
from src.config import settings
from src.config.firebase_config import verify_token
from src.analysis.chat_engine import NewsChatEngine
from src.collectors.universe_collector import UniverseCollector
from src.utils.translator import NewsTranslator
from pydantic import BaseModel
import requests

from src.analysis.student_classifier import StudentClassifier

chat_engine = NewsChatEngine()
universe_collector = UniverseCollector()
translator = NewsTranslator()
student_classifier = StudentClassifier()
# logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

# Multi-country in-memory cache for student news
_student_news_caches = {}


router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

FALLBACK_IMAGES = [
    "https://images.unsplash.com/photo-1504711434969-e33886168f5c?q=80&w=1000",
    "https://images.unsplash.com/photo-1495020689067-958852a7765e?q=80&w=1000",
    "https://images.unsplash.com/photo-1476242484419-cf5c1d4ee04b?q=80&w=1000",
    "https://images.unsplash.com/photo-1585829365294-bb7c63b3ecda?q=80&w=1000",
    "https://images.unsplash.com/photo-1502139214982-d0ad755a619d?q=80&w=1000",
    "https://images.unsplash.com/photo-1557683316-973673baf926?q=80&w=1000",
    "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=1000",
    "https://images.unsplash.com/photo-1518770660439-4636190af475?q=80&w=1000",
    "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?q=80&w=1000",
    "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?q=80&w=1000",
    "https://images.unsplash.com/photo-1526628953301-3e589a6a8b74?q=80&w=1000",
    "https://images.unsplash.com/photo-1460925895917-afdab827c52f?q=80&w=1000",
    "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?q=80&w=1000",
    "https://images.unsplash.com/photo-1519389950473-47ba0277781c?q=80&w=1000",
    "https://images.unsplash.com/photo-1486312338219-ce68d2c6f44d?q=80&w=1000",
    "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?q=80&w=1000",
    "https://images.unsplash.com/photo-1515378960530-7c0da6231fb1?q=80&w=1000",
    "https://images.unsplash.com/photo-1498050108023-c5249f4df085?q=80&w=1000",
    "https://images.unsplash.com/photo-1488590528505-98d2b5aba04b?q=80&w=1000",
    "https://images.unsplash.com/photo-1525547719571-a2d4ac8945e2?q=80&w=1000",
    "https://images.unsplash.com/photo-1531297484001-80022131f5a1?q=80&w=1000",
    "https://images.unsplash.com/photo-1510511459019-5dee2c127ffb?q=80&w=1000",
    "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?q=80&w=1000",
    "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?q=80&w=1000",
    "https://images.unsplash.com/photo-1531297484001-80022131f5a1?q=80&w=1000",
    "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?q=80&w=1000",
    "https://images.unsplash.com/photo-1519389950473-47ba0277781c?q=80&w=1000",
    "https://images.unsplash.com/photo-1486312338219-ce68d2c6f44d?q=80&w=1000",
    "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?q=80&w=1000",
    "https://images.unsplash.com/photo-1515378960530-7c0da6231fb1?q=80&w=1000",
    "https://images.unsplash.com/photo-1432888622747-4eb9a8f2c1d1?q=80&w=1000",
    "https://images.unsplash.com/photo-1461749280684-dccba630e2f6?q=80&w=1000",
    "https://images.unsplash.com/photo-1498050108023-c5249f4df085?q=80&w=1000",
    "https://images.unsplash.com/photo-1518770660439-4636190af475?q=80&w=1000",
    "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=1000",
    "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?q=80&w=1000",
    "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?q=80&w=1000",
    "https://images.unsplash.com/photo-1510915361894-db8b60106cb1?q=80&w=1000",
    "https://images.unsplash.com/photo-1515879218367-8466d910aaa4?q=80&w=1000",
    "https://images.unsplash.com/photo-1516116216624-53e697fedbea?q=80&w=1000",
    "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?q=80&w=1000",
    "https://images.unsplash.com/photo-1537432376769-00f5c2f4c8d2?q=80&w=1000",
    "https://images.unsplash.com/photo-1523961131990-5ea7c61b2107?q=80&w=1000",
    "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?q=80&w=1000",
    "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?q=80&w=1000",
    "https://images.unsplash.com/photo-1518770660439-4636190af475?q=80&w=1000",
    "https://images.unsplash.com/photo-1496065187959-7f07b8353c55?q=80&w=1000",
    "https://images.unsplash.com/photo-1531297484001-80022131f5a1?q=80&w=1000",
    "https://images.unsplash.com/photo-1519389950473-47ba0277781c?q=80&w=1000",
    "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?q=80&w=1000",
    "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?q=80&w=1000"
]

def get_fallback_image(seed: str) -> str:
    """Deterministically select a fallback image based on djb2 hash"""
    if not seed: return FALLBACK_IMAGES[0]
    hash_val = 5381
    for char in seed:
        hash_val = ((hash_val << 5) + hash_val) + ord(char)
    return FALLBACK_IMAGES[abs(hash_val) % len(FALLBACK_IMAGES)]

def normalize_country(c):
    if not c: return None, []
    mapping = {
        "jp": "Japan", "us": "USA", "in": "India", "gb": "UK",
        "ru": "Russia", "de": "Germany", "fr": "France", "sg": "Singapore",
        "au": "Australia", "ca": "Canada", "ae": "UAE", "de": "Germany"
    }
    # Reverse mapping: "India" -> "in"
    rev_mapping = {v.lower(): k for k, v in mapping.items()}
    rev_mapping["america"] = "us"
    rev_mapping["united states"] = "us"
    rev_mapping["united kingdom"] = "gb"
    rev_mapping["russia"] = "ru"
    rev_mapping["uae"] = "ae"
    
    val = c.lower().strip()
    # Find canonical name
    if val in mapping:
        name = mapping[val]
        code = val
    elif val in rev_mapping:
        name = val.capitalize()
        if val == "usa": name = "USA"
        if val == "uae": name = "UAE"
        if val == "uk": name = "UK"
        code = rev_mapping[val]
    else:
        name = c.capitalize()
        code = val # Fallback

    # Build exhaustive match keys
    match_keys = [val, val.upper(), val.capitalize(), name, name.lower(), name.upper(), code, code.upper()]
    return name, list(set(match_keys))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Define FIREBASE_CLIENT_CONFIG globally
FIREBASE_CLIENT_CONFIG = {
    "apiKey": settings.FIREBASE_API_KEY,
    "authDomain": settings.FIREBASE_AUTH_DOMAIN,
    "projectId": settings.FIREBASE_PROJECT_ID,
    "storageBucket": settings.FIREBASE_STORAGE_BUCKET,
    "messagingSenderId": settings.FIREBASE_MESSAGING_SENDER_ID,
    "appId": settings.FIREBASE_APP_ID
}

@router.get("/")
async def landing_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "firebase_config": FIREBASE_CLIENT_CONFIG})

@router.get("/dashboard")
async def dashboard(request: Request, category: str = None, country: str = None, lang: str = 'english', db: Session = Depends(get_db)):
    """Render the main intelligence portal"""
    try:
        # 0. Context & Initialization
        blueprint = None
        is_special_node = bool(category or country)
        
        # 1. Blueprint Fetching
        try:
            if not is_special_node:
                admin_api_url = os.getenv("ADMIN_API_URL", "http://localhost:5000")
                resp = requests.get(f"{admin_api_url}/api/blueprints/active", timeout=2)
                if resp.status_code == 200:
                    data = resp.json()
                    blueprint = data.get("structure")
                    logger.info(f"Blueprint Applied: {len(blueprint) if blueprint else 0} custom layout blocks")
                else:
                    blueprint = None
            else:
                logger.debug(f"Special node {category or country} active. Standard layout preferred.")
        except Exception as e:
            logger.debug(f"Blueprint fetch failed: {e}")

        # 2. Layout Styles processing
        if blueprint:
            for block in blueprint:
                if "styles" in block:
                    style_str = "; ".join([f"{k}: {v}" for k, v in block["styles"].items()])
                    block["style_attr"] = style_str

        # 3. Get latest published digest
        latest_digest = db.query(DailyDigest).filter(DailyDigest.is_published == True).order_by(DailyDigest.date.desc()).first()
        if not latest_digest:
            latest_digest = db.query(DailyDigest).order_by(DailyDigest.date.desc()).first()
        
        # 3.A AUTO-REPAIR: If news exists but no digest, generate one immediately
        from src.database.models import VerifiedNews
        if not latest_digest and db.query(VerifiedNews).count() > 0:
            logger.info("Auto-Repair: Verified news found but no digest. Generating now...")
            from src.digest.generator import DigestGenerator
            generator = DigestGenerator()
            # We await this synchronously to ensure the user gets a working page on the first hit
            await generator.create_daily_digest(db)
            latest_digest = db.query(DailyDigest).filter(DailyDigest.is_published == True).order_by(DailyDigest.date.desc()).first()

        # 4. Diagnostics & Status
        raw_count = db.query(RawNews).count()
        verified_count = db.query(VerifiedNews).count()
        
        # 4.B Filter Ads by Position
        all_ads = db.query(Advertisement).order_by(Advertisement.created_at.desc()).limit(30).all()
        # Ensure position field exists (fallback for old records)
        for ad in all_ads:
            if not hasattr(ad, 'position') or not ad.position:
                ad.position = 'both'
        
        left_ads = [a for a in all_ads if a.position in ["left", "both"]]
        right_ads = [a for a in all_ads if a.position in ["right", "both"]]
        mobile_ads = [a for a in all_ads if a.position in ["mobile", "both"]]

        papers = db.query(Newspaper).order_by(Newspaper.name.asc()).all()
        
        system_status = "Syncing"
        if not settings.NEWS_API_KEY:
            system_status = "Configuration Alert: API Keys Missing on Server"
        elif raw_count == 0:
            system_status = "Collecting: Scanning Global News Sources..."
        elif verified_count == 0:
            system_status = "Analyzing: AI is verifying collected intelligence..."
        elif not latest_digest:
            system_status = "Promoting: Finalizing intelligence dashboard..."

        # 5. Core Digest Data
        digest_data = copy.deepcopy(latest_digest.content_json) if latest_digest else {
            "top_stories": [], "breaking_news": [], "trending_news": [], "brief": [],
            "is_system_initializing": True,
            "is_empty_regional": True,
            "system_status_msg": system_status
        }
        
        # 5.B Freshness Filter (2 Hour Limit for high recency)
        now_utc = datetime.utcnow()
        two_hours_ago = now_utc - timedelta(hours=2)
        
        def is_fresh(item):
            # Try to parse published_at if it exists
            pub = item.get("published_at")
            if pub:
                try:
                    p_time = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                    return p_time > two_hours_ago
                except: return True
            return True

        if digest_data:
            if "top_stories" in digest_data:
                digest_data["top_stories"] = [s for s in digest_data["top_stories"] if is_fresh(s)]
            if "breaking_news" in digest_data:
                digest_data["breaking_news"] = [s for s in digest_data["breaking_news"] if is_fresh(s)]

        # Handle case where content_json is stringified
        if isinstance(digest_data, str):
            import json
            digest_data = json.loads(digest_data)

        # 6. Regional Logic
        selected_country_name = None
        country_match_keys = []
        trending_title = "Intelligence Feed"

        if country and digest_data:
            from .web_dashboard import normalize_country
            target_name, match_keys = normalize_country(country)
            selected_country_name = target_name
            country_match_keys = match_keys
            
            countries_data = digest_data.get("countries", {})
            country_stories = []
            
            # Match strictly
            for k, v in countries_data.items():
                if k.lower() in match_keys:
                    country_stories = v
                    break
            
            # Fallback for stories tagged specifically but not in node bucket
            if not country_stories and "top_stories" in digest_data:
                country_stories = [s for s in digest_data["top_stories"] if s.get("country") in match_keys]

            if country_stories:
                normalized_stories = []
                for s in country_stories:
                    normalized_stories.append({
                        "id": s.get("id"),
                        "title": s.get("title"),
                        "url": s.get("url"),
                        "image_url": s.get("image_url"),
                        "source_name": s.get("source_name"),
                        "bullets": s.get("bullets") or [s.get("why", "")],
                        "affected": s.get("affected", ""),
                        "why": s.get("why", ""),
                        "bias": s.get("bias", "Neutral"),
                        "tags": s.get("tags", []),
                        "category": s.get("category"),
                        "country": s.get("country"),
                        "time_ago": s.get("time_ago", "Just Now")
                    })
                digest_data["top_stories"] = normalized_stories
                trending_title = f"Trending in {target_name}"
            else:
                digest_data["is_empty_regional"] = True
                # Keep global as fallback
                for section in ["top_stories", "breaking_news", "trending_news"]:
                    if section in digest_data:
                        for s in digest_data[section]:
                            s["is_global_fallback"] = True
                trending_title = f"{target_name} Node: Regional Intel Pending"

            # Filter other sections strictly if regional exists
            if not digest_data.get("is_empty_regional"):
                for section in ["breaking_news", "brief", "trending_news"]:
                    if section in digest_data:
                        digest_data[section] = [
                            item for item in digest_data[section]
                            if (item.get("country") in match_keys) or (item.get("country_name") in match_keys)
                        ]
            
            # Global Node Translation
            # Map country name to target language
            country_langs = {
                "India": "hindi", # Or other regional if needed, but Hindi is common fallback
                "Japan": "japanese",
                "Russia": "russian",
                "Germany": "german",
                "France": "french",
                "UAE": "arabic",
                "Singapore": "chinese",
                "China": "chinese"
            }
            
            target_lang = lang if (lang and lang.lower() != 'english') else country_langs.get(selected_country_name)
            
            if selected_country_name in country_langs and target_lang and target_lang.lower() != 'english':
                logger.info(f"Translating node {selected_country_name} to {target_lang}")
                sections_to_translate = ["top_stories", "breaking_news", "trending_news", "brief"]
                for section in sections_to_translate:
                    if section in digest_data:
                        digest_data[section] = translator.translate_stories(digest_data[section], target_lang)
                trending_title = translator.translate_text(trending_title, target_lang)

        # 7. Category Logic
        elif category and digest_data:
            normalized_cat = category.lower().replace(" ", "_").strip()
            category_map = {
                "business": "Business & Economy", "economy": "Business & Economy",
                "tech": "Technology", "technology": "Technology",
                "science": "Science & Health", "health": "Science & Health",
                "world": "World News", "india": "India / Local News",
                "ai": "AI & Machine Learning"
            }
            target_key = category_map.get(normalized_cat, category.strip())
            
            categories = digest_data.get("categories", {})
            cat_stories = categories.get(target_key) or categories.get(normalized_cat)
            
            # Partial/Fuzzy match if direct lookup fails
            if not cat_stories:
                search_term = target_key.lower()
                for k, v in categories.items():
                    if search_term in k.lower() or k.lower() in search_term:
                        cat_stories = v
                        break
            
            if cat_stories:
                # IMPORTANT: Overwrite top_stories with the full category list
                digest_data["top_stories"] = cat_stories
            else:
                # Final fallback: filter existing top_stories
                all_stories = digest_data.get("top_stories", [])
                digest_data["top_stories"] = [s for s in all_stories if s.get("category") == category]

        # 8. Global Home View filtering
        if digest_data:
            non_english = [
                'jp', 'ru', 'de', 'fr', 'sg', 
                'Japan', 'Russia', 'Germany', 'France', 'Singapore'
            ]
            # ONLY filter non-english out if we are on the Home view (no country or category selected)
            if not country and not category:
                for section in ["breaking_news", "trending_news", "brief", "top_stories"]:
                    if section in digest_data:
                        digest_data[section] = [b for b in digest_data[section] if b.get("country") not in non_english]

        # 9. Fallback images
        if digest_data:
            for section in ["top_stories", "breaking_news", "trending_news"]:
                if section in digest_data:
                    for idx, item in enumerate(digest_data[section]):
                        if not item.get("image_url"):
                            seed = f"{item.get('title', '')}{idx}"
                            item["image_url"] = get_fallback_image(seed)

        # 10. Filter Newspapers by country (Guarantee Minimum 4)
        if country:
             # Normalize selected country name for newspaper matching
             target_name, _ = normalize_country(country)
             # Filter papers by country name or "Global"
             specific_papers = [
                 p for p in papers 
                 if p.country and (p.country.lower() in [key.lower() for key in match_keys] or p.country.lower() == target_name.lower())
             ]
             global_papers = [p for p in papers if p.country == "Global"]
             
             # If less than 4 specific papers, pad with global
             if len(specific_papers) < 4:
                 needed = 4 - len(specific_papers)
                 context_papers = specific_papers + global_papers[:needed]
             else:
                 context_papers = specific_papers
        else:
             context_papers = [p for p in papers if p.country == "Global"]

        # 11. Daily Short (Yesterday's Top Impact Articles)
        now_utc = datetime.utcnow() # Re-fetch or ensure it's current
        yesterday = now_utc - timedelta(days=1)
        yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # We query by created_at since published_at can be very unreliable
        daily_short_articles = db.query(VerifiedNews).filter(
            VerifiedNews.created_at >= yesterday_start,
            VerifiedNews.created_at < yesterday_start + timedelta(days=1)
        ).order_by(VerifiedNews.impact_score.desc()).limit(3).all()
        
        daily_short = {
            "date_str": yesterday.strftime("%B %d"),
            "articles": []
        }
        for article in daily_short_articles:
            impact_str = "Global trends"
            if article.impact_tags and isinstance(article.impact_tags, list) and len(article.impact_tags) > 0:
                impact_str = " + ".join(article.impact_tags[:2]).replace("#", "")
            elif article.category:
                impact_str = article.category.split(" ")[0]
                
            daily_short["articles"].append({
                "title": article.title,
                "impact": impact_str,
                "image_url": getattr(article, "image_url", None) or (article.raw_news.url_to_image if article.raw_news else None) or get_fallback_image(article.title)
            })

        context = {
            "request": request,
            "daily_short": daily_short,
            "digest": digest_data,
            "date": latest_digest.date.strftime("%Y-%m-%d") if latest_digest else "System Initializing",
            "firebase_config": FIREBASE_CLIENT_CONFIG,
            "left_ads": left_ads,
            "right_ads": right_ads,
            "mobile_ads": mobile_ads,
            "papers": context_papers,
            "vapid_public_key": settings.VAPID_PUBLIC_KEY,
            "selected_category": category,
            "selected_country": country,
            "trending_title": trending_title,
            "selected_country_name": selected_country_name,
            "country_match_keys": country_match_keys,
            "blueprint": blueprint,
            "admin_api_url": os.getenv("ADMIN_API_URL", "http://localhost:5000")
        }

        return templates.TemplateResponse("dashboard.html", context)

    except Exception as e:
        import traceback
        logger.error(f"DASHBOARD CRASH: {str(e)}")
        logger.error(traceback.format_exc())
        return templates.TemplateResponse("error.html", {"request": request, "message": f"Intelligence Node Error: {str(e)}", "stack": traceback.format_exc()})

@router.get("/saved")
async def saved_page(request: Request):
    return templates.TemplateResponse("saved.html", {"request": request, "firebase_config": FIREBASE_CLIENT_CONFIG})

@router.get("/history")
async def history(request: Request):
    return templates.TemplateResponse("history.html", {"request": request, "firebase_config": FIREBASE_CLIENT_CONFIG})

@router.get("/newspaper")
async def newspaper(request: Request):
    return templates.TemplateResponse("newspaper.html", {"request": request, "firebase_config": FIREBASE_CLIENT_CONFIG})

@router.get("/business-intelligence")
async def business_intelligence(request: Request, db: Session = Depends(get_db)):
    # This route is restricted
    
    # The actual enforcement happens client-side via Firebase for UX, 
    # but we will also pass the data only if we find a valid digest.
    latest_digest = db.query(DailyDigest).filter(DailyDigest.is_published == True).order_by(DailyDigest.date.desc()).first()
    
    premium_intel = []
    if latest_digest and "premium_intel" in latest_digest.content_json:
        premium_intel = latest_digest.content_json["premium_intel"]
        
    # Generate data for Visual Intelligence Dashboard
    import random
    
    trending_labels = ["AI Inference", "Geopolitical Friction", "Data Center Buildout", "Supply Chain", "Regulation Risk", "Interest Rates"]
    trending_data = [random.randint(60, 100) for _ in trending_labels]
    
    geo_labels = ["Day -6", "Day -5", "Day -4", "Day -3", "Day -2", "Yesterday", "Today"]
    geo_data = [random.randint(40, 95) for _ in geo_labels]
    
    economic_labels = ["Inflation Risk", "Yield Curves", "Job Growth", "Tech Cap-Ex", "Commodities", "Real Estate"]
    economic_data = [random.randint(30, 90) for _ in economic_labels]
    
    visual_intel = {
        "trending": {
            "labels": trending_labels,
            "data": trending_data
        },
        "geopolitical": {
            "labels": geo_labels,
            "data": geo_data
        },
        "economic": {
            "labels": economic_labels,
            "data": economic_data
        }
    }

    return templates.TemplateResponse("business_intel.html", {
        "request": request, 
        "firebase_config": FIREBASE_CLIENT_CONFIG,
        "premium_intel": premium_intel,  # Changed from premium_data
        "visual_intel": visual_intel,
        "restricted_email": "chaparapuashokreddy666@gmail.com"
    })

@router.get("/personal-agent")
async def personal_agent_page(request: Request):
    db = SessionLocal()
    try:
        # Fetch all unique categories from VerifiedNews for interest selection
        categories_raw = db.query(VerifiedNews.category).distinct().all()
        categories = [c[0] for c in categories_raw if c[0]]
        if not categories:
            categories = ["Technology", "AI", "Business", "Sports", "Politics", "World"]
        
        return templates.TemplateResponse("personal_agent.html", {
            "request": request, 
            "firebase_config": FIREBASE_CLIENT_CONFIG,
            "available_interests": sorted(categories)
        })
    finally:
        db.close()

@router.get("/api/article/{article_id}")
async def get_article_detail(article_id: int, db: Session = Depends(get_db)):
    """Fetch full intelligence detail for a specific article"""
    article = db.query(VerifiedNews).filter(VerifiedNews.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Intelligence artifact not found")
    
    data = article.to_dict()
    
    # Get image from raw news if missing
    if not data.get("image_url") and article.raw_news:
        data["image_url"] = article.raw_news.url_to_image
        
    # Apply fallback image if still missing
    if not data.get("image_url"):
        seed = f"{data.get('title', '')}{data.get('id', '')}"
        data["image_url"] = get_fallback_image(seed)
        
    # Ensure time_ago is present or calculated
    # For now, we'll just use a default or format the published_at
    if article.published_at:
        from datetime import datetime
        diff = datetime.utcnow() - article.published_at
        if diff.days > 0:
            data["time_ago"] = f"{diff.days}d ago"
        elif diff.seconds > 3600:
            data["time_ago"] = f"{diff.seconds // 3600}h ago"
        else:
            data["time_ago"] = f"{diff.seconds // 60}m ago"
    else:
        data["time_ago"] = "Just Now"

    return data

@router.get("/api/breaking-news")
async def get_breaking_news(country: str = None, db: Session = Depends(get_db)):
    """API endpoint for breaking news auto-refresh"""
    latest_digest = db.query(DailyDigest).filter(
        DailyDigest.is_published == True
    ).order_by(DailyDigest.date.desc()).first()
    
    breaking_news = []
    if latest_digest and "breaking_news" in latest_digest.content_json:
        breaking_news = latest_digest.content_json["breaking_news"]
        
        # 1. Standardized Filter
        if country:
            target_name, match_keys = normalize_country(country)
            breaking_news = [
                b for b in breaking_news 
                if (b.get("country") in match_keys) or (b.get("country_name") in match_keys)
            ]
        else:
            # HOME PAGE: Only English countries
            non_english = ['jp', 'cn', 'ru', 'de', 'fr', 'Japan', 'China', 'Russia', 'Germany', 'France']
            breaking_news = [b for b in breaking_news if b.get("country") not in non_english]

        # 2. Inject fallback images
        for idx, item in enumerate(breaking_news):
            if not item.get("image_url"):
                seed = f"{item.get('headline', '')}{item.get('title', '')}"
                item["image_url"] = get_fallback_image(seed)
    
    return {"breaking_news": breaking_news}

@router.get("/api/more-stories/{category}/{offset}")
async def get_more_stories(category: str, offset: int, country: str = None, db: Session = Depends(get_db)):
    """Fetch more stories for a specific category with offset"""
    latest_digest = db.query(DailyDigest).filter(DailyDigest.is_published == True).order_by(DailyDigest.date.desc()).first()
    
    if not latest_digest:
        return {"stories": []}

    digest_data = latest_digest.content_json
    stories = []
    
    if category == "top_stories":
        stories = digest_data.get("top_stories", [])
    elif category == "breaking_news" or category == "breaking":
        stories = digest_data.get("breaking_news", [])
    
    # Fast-track for specific keys
    if not stories and category in digest_data:
        stories = digest_data.get(category, [])

    if stories and not country:
        # HOME PAGE: Only English countries
        non_english = ['jp', 'cn', 'ru', 'de', 'fr', 'Japan', 'China', 'Russia', 'Germany', 'France']
        stories = [s for s in stories if s.get("country") not in non_english]
    else:
        # Normalize category to match backend keys 
        normalized_category = category.lower().replace(" ", "_").strip()
        
        # Explicit mappings for frontend-backend mismatches
        category_map = {
            "business": "Business & Economy",
            "economy": "Business & Economy",
            "business_&_economy": "Business & Economy",
            "science": "Science & Health",
            "health": "Science & Health",
            "science_&_health": "Science & Health",
            "tech": "Technology",
            "technology": "Technology",
            "world": "World News",
            "world_news": "World News",
            "india": "India / Local News",
            "local": "India / Local News",
            "india_/_local_news": "India / Local News",
            "sports": "Sports",
            "entertainment": "Entertainment",
            "ai": "AI & Machine Learning",
            "ai_&_machine_learning": "AI & Machine Learning"
        }
        
        target_key = category_map.get(normalized_category, category.strip())

        cat_stories = []
        categories = digest_data.get("categories", {})
        
        # 1. Try direct match with mapped key
        if target_key in categories:
            cat_stories = categories[target_key]
        # 2. Try direct match with original normalized key
        elif normalized_category in categories:
             cat_stories = categories[normalized_category]
        else:
            # 3. Fallback: Check keys case-insensitively
            for k, v in categories.items():
                if k.lower() == normalized_category or k.lower() == target_key.lower():
                    cat_stories = v
                    break
        
        stories = cat_stories
        
        # Apply English-only filter for Home Page (if country is null)
        if not country:
            non_english = ['jp', 'cn', 'ru', 'de', 'fr', 'Japan', 'China', 'Russia', 'Germany', 'France']
            stories = [s for s in stories if s.get("country") not in non_english]

        # Normalize if needed (same logic as dashboard)
        if stories:
            normalized = []
            for s in stories:
                normalized.append({
                    "id": s.get("id"),
                    "title": s.get("title"),
                    "url": s.get("url"),
                    "image_url": s.get("image_url"),
                    "source_name": s.get("source_name"),
                    "bullets": s.get("bullets") or [s.get("summary") or s.get("why", "")],
                    "affected": s.get("affected", ""),
                    "why": s.get("why", ""),
                    "bias": s.get("bias", "Neutral"),
                    "tags": s.get("tags", []),
                    "category": category,
                    "time_ago": s.get("time_ago", "Just Now")
                })
            stories = normalized
             
        # FINALLY: If country is provided, filter the results strictly to match
        if country and stories:
            target_name, match_keys = normalize_country(country)
            stories = [
                s for s in stories
                if (s.get("country") in match_keys) or (s.get("country_name") in match_keys)
            ]

    # Pagination logic
    start = offset
    limit = 20
    end = offset + limit
    
    # Check if there are more stories after this batch
    subset = stories[start:end]
    has_more = len(stories) > end
    
    return {
        "stories": subset,
        "has_more": has_more
    }

class LoginRequest(BaseModel):
    id_token: str

@router.post("/api/login")
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
    decoded_token = verify_token(payload.id_token)
    if not decoded_token:
        raise HTTPException(status_code=401, detail="Invalid Firebase Token")
    
    uid = decoded_token.get("uid")
    email = decoded_token.get("email")
    phone = decoded_token.get("phone_number")
    
    # Upsert User
    user = db.query(User).filter(User.firebase_uid == uid).first()
    if not user:
        user = User(firebase_uid=uid, email=email, phone=phone)
        db.add(user)
    else:
        # Update email/phone if they changed/populated
        if email: user.email = email
        if phone: user.phone = phone
        
    db.commit()
    return {"status": "success", "uid": uid}

class SubscribeRequest(BaseModel):
    firebase_uid: str
    category: str

@router.post("/api/subscribe")
async def subscribe_category(payload: SubscribeRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.firebase_uid == payload.firebase_uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already subscribed
    existing = db.query(Subscription).filter(
        Subscription.user_id == user.id,
        Subscription.category == payload.category
    ).first()
    
    if not existing:
        sub = Subscription(user_id=user.id, category=payload.category)
        db.add(sub)
        db.commit()
        return {"status": "success", "message": f"Subscribed to {payload.category}"}
    
    return {"status": "already_subscribed", "message": "Already on the list!"}

@router.get("/mock-test")
async def mock_test_page(request: Request):
    firebase_config = {
        "apiKey": settings.FIREBASE_API_KEY,
        "authDomain": settings.FIREBASE_AUTH_DOMAIN,
        "projectId": settings.FIREBASE_PROJECT_ID,
        "storageBucket": settings.FIREBASE_STORAGE_BUCKET,
        "messagingSenderId": settings.FIREBASE_MESSAGING_SENDER_ID,
        "appId": settings.FIREBASE_APP_ID
    }
    return templates.TemplateResponse("mock_test.html", {"request": request, "firebase_config": firebase_config})

@router.post("/api/sync-intelligence")
async def force_sync_intelligence(background_tasks: BackgroundTasks):
    """Manually trigger a full news collection and analysis cycle"""
    from src.scheduler.task_scheduler import run_news_cycle
    
    # Run helper to start the async cycle in background
    async def _run_cycle():
        try:
            await run_news_cycle()
        except Exception as e:
            logger.error(f"Manual Sync Failed: {e}")

    background_tasks.add_task(_run_cycle)
    return {"status": "success", "message": "Intelligence scan initiated in background."}

@router.post("/api/refresh-digest")
async def refresh_digest(db: Session = Depends(get_db)):
    """Manually regenerate the daily digest from existing verified news"""
    from src.digest.generator import DigestGenerator
    generator = DigestGenerator()
    try:
        digest = await generator.create_daily_digest(db)
        if digest:
            return {"status": "success", "message": "Live site updated successfully!"}
        return {"status": "error", "message": "Failed to generate digest"}
    except Exception as e:
        logger.error(f"Manual Digest Refresh Failed: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/api/system-check")
async def system_check(db: Session = Depends(get_db)):
    """A detailed health check for debugging deployment environments"""
    from src.database.models import RawNews, VerifiedNews, DailyDigest
    return {
        "raw_news_count": db.query(RawNews).count(),
        "verified_news_count": db.query(VerifiedNews).count(),
        "digest_count": db.query(DailyDigest).count(),
        "has_news_api_key": bool(settings.NEWS_API_KEY),
        "db_url_is_sqlite": settings.DATABASE_URL.startswith("sqlite")
    }


@router.post("/api/generate-exam")
async def generate_mock_exam(db: Session = Depends(get_db)):
    """Generate a quick mock test from recent news"""
    # Import here to avoid circular dependency if any
    from src.analysis.exam_generator import ExamGenerator
    
    generator = ExamGenerator()
    # For now, we simulate "yesterday's news" by just grabbing recent verified news
    # Ideally, ExamGenerator logic handles the time window
    
    # We need to construct a robust prompt in ExamGenerator
    # But first, let's fix the class method usage
    
    # Actually, we defined `generate_mock_test` in the class
    # We need to pass the DB session
    
    exam_data = generator.generate_mock_test(db)
    
    if "error" in exam_data:
        raise HTTPException(status_code=500, detail=exam_data["error"])
        
    return exam_data


class ChatRequest(BaseModel):
    query: str

@router.post("/api/chat")
async def chat_with_news(payload: ChatRequest, db: Session = Depends(get_db)):
    response = chat_engine.get_response(db, payload.query)
    return {"status": "success", "response": response}

class NoteRequest(BaseModel):
    text: str
    url: str

@router.post("/api/save-note")
async def save_note(payload: NoteRequest):
    # Log it for now as there is no DB table for notes yet
    logger.info(f"User Note: {payload.text} from {payload.url}")
    return {"status": "success", "message": "Note recorded"}

@router.get("/universe")
async def universe_page(request: Request):
    firebase_config = {
        "apiKey": settings.FIREBASE_API_KEY,
        "authDomain": settings.FIREBASE_AUTH_DOMAIN,
        "projectId": settings.FIREBASE_PROJECT_ID,
        "storageBucket": settings.FIREBASE_STORAGE_BUCKET,
        "messagingSenderId": settings.FIREBASE_MESSAGING_SENDER_ID,
        "appId": settings.FIREBASE_APP_ID
    }
    return templates.TemplateResponse("universe.html", {"request": request, "firebase_config": firebase_config})

class UniverseRequest(BaseModel):
    country: str

@router.post("/api/universe/news")
async def get_universe_news(payload: UniverseRequest):
    try:
        # Now returns a dictionary with top_stories, breaking_news, videos, newspaper_summary
        news_data = await universe_collector.fetch_country_news(payload.country)
        return {"status": "success", "news": news_data}
    except Exception as e:
        logger.error(f"Universe News Fetch Failed: {e}")
        return {"status": "error", "message": str(e)}
@router.get("/student-news")
def student_news_page(request: Request, category: str = None, profile: str = None, country: str = "India", db: Session = Depends(get_db)):
    """Render the standalone Student News portal."""
    from .web_dashboard import normalize_country
    target_name, _ = normalize_country(country)
    country_key = target_name.lower()
    
    # Process or get from cache
    _update_student_cache_if_needed(db, force=False, country=country)
    
    # Filter by category if requested
    cache = _student_news_caches.get(country_key, {})
    articles = cache.get("articles", [])
    if category and category != "All":
        articles = [a for a in articles if a["category"] == category]
        
    if profile:
        articles = [a for a in articles if profile in a.get("profiles", [])]
        
    trends = cache.get("trends", {})
    
    firebase_config = {
        "apiKey": settings.FIREBASE_API_KEY,
        "authDomain": settings.FIREBASE_AUTH_DOMAIN,
        "projectId": settings.FIREBASE_PROJECT_ID,
        "storageBucket": settings.FIREBASE_STORAGE_BUCKET,
        "messagingSenderId": settings.FIREBASE_MESSAGING_SENDER_ID,
        "appId": settings.FIREBASE_APP_ID
    }
    
    # Render template (which we will create next)
    return templates.TemplateResponse("student_news.html", {
        "request": request,
        "articles": articles,
        "trends": trends,
        "current_category": category or "All",
        "current_profile": profile,
        "current_country": country,
        "categories": list(student_classifier.CATEGORIES.keys()),
        "profiles": list(student_classifier.PROFILES.keys()),
        "firebase_config": firebase_config
    })

@router.get("/api/student-news")
def api_get_student_news(category: str = None, profile: str = None, country: str = "India", db: Session = Depends(get_db)):
    """API endpoint to get student news JSON."""
    from .web_dashboard import normalize_country
    _update_student_cache_if_needed(db, force=False, country=country)
    target_name, _ = normalize_country(country)
    country_key = target_name.lower()
    articles = _student_news_caches.get(country_key, {}).get("articles", [])
    if category and category != "All":
        articles = [a for a in articles if a["category"] == category]
    if profile:
        articles = [a for a in articles if profile in a.get("profiles", [])]
    return {"status": "success", "count": len(articles), "articles": articles}

@router.get("/api/student-trends")
def api_get_student_trends(country: str = "India", db: Session = Depends(get_db)):
    """API endpoint to get student news trends."""
    from .web_dashboard import normalize_country
    _update_student_cache_if_needed(db, force=False, country=country)
    target_name, _ = normalize_country(country)
    country_key = target_name.lower()
    return {"status": "success", "trends": _student_news_caches.get(country_key, {}).get("trends", {})}

import requests

def _fetch_live_scholarships_cache() -> list:
    """Fetch external scholarships live to prevent 0 counts in the UI."""
    api_key = settings.GNEWS_API_KEY
    if not api_key: return []
    
    # Highly specific query to enforce India scholarship results
    query = "scholarship OR fellowship AND student OR application"
    url = f"https://gnews.io/api/v4/search?q={query}&country=in&lang=en&max=5&apikey={api_key}"
    
    results = []
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            articles = resp.json().get("articles", [])
            for article in articles:
                # Force format it as Student Data
                student_data = {
                    "id": 0,
                    "title": article.get("title", "Live Scholarship"),
                    "summary": article.get("description", "Opportunity for students."),
                    "category": "Scholarships & Internships",
                    "tags": ["#Scholarship", "#LiveOpportunity"],
                    "profiles": ["General Student"],
                    "direct_links": [article.get("url", "#")],
                    "important_dates": ["Check Link"],
                    "authority": article.get("source", {}).get("name", "Various"),
                    "urgency": "High",
                    "trend_score": 95,
                    "url": article.get("url", "#"),
                    "source_name": article.get("source", {}).get("name", "GNews"),
                    "published_at": article.get("publishedAt", datetime.utcnow().isoformat()),
                    "image_url": article.get("image") or get_fallback_image(article.get("title", ""))
                }
                results.append(student_data)
    except Exception as e:
        logger.error(f"Live scholarship fetch failed: {e}")
        
    return results

def _update_student_cache_if_needed(db: Session, force: bool = False, country: str = "India"):
    """Internal helper to process country news into Student structure with caching."""
    from .web_dashboard import normalize_country
    target_name, match_keys = normalize_country(country)
    country_key = target_name.lower()
    
    if country_key not in _student_news_caches:
        _student_news_caches[country_key] = {"last_updated": None, "articles": [], "trends": {}}
        
    cache = _student_news_caches[country_key]
    now = datetime.utcnow()
    # Cache for 15 minutes
    if not force and cache["last_updated"] and (now - cache["last_updated"]).total_seconds() < 900:
        return cache
        
    logger.info(f"Updating Student News Cache by processing {target_name} articles...")
    
    # Fetch recent news (using specific country code in DB)
    # Relax lookback to 30 days to ensure we have content
    lookback_period = now - timedelta(days=30)
    
    if target_name == "Global" or not country or country.lower() == "global":
        raw_articles_query = db.query(VerifiedNews).filter(
            VerifiedNews.created_at >= lookback_period
        )
    else:
        from sqlalchemy import or_
        raw_articles_query = db.query(VerifiedNews).filter(
            or_(
                VerifiedNews.country.in_(match_keys),
                # If a query matches the headline text, it might be beneficial
            ),
            VerifiedNews.created_at >= lookback_period
        )
        
    raw_articles = raw_articles_query.order_by(VerifiedNews.created_at.desc()).limit(2000).all()
    
    processed_articles = []
    category_counts = {cat: 0 for cat in student_classifier.CATEGORIES.keys()}
    category_counts["General Student News"] = 0
    
    scholarship_count = 0
    exam_mentions = {}
    
    for article in raw_articles:
        # Pre-filter using fast string matching to avoid processing entirely unrelated news
        combined = f"{article.title} {article.content}".lower()
        # Relaxed pre-filter: catch more educational and student-relevant content
        student_keywords = ["student", "exam", "school", "university", "college", "scholarship", "syllabus", "ugc", "cbse", "nta", "placement", "job", "career", "admission", "startup", "grant", "hackathon", "funding", "education", "learning", "degree", "diploma", "research", "campus", "internship", "hiring", "recruitment", "youth", "academic", "tuition", "entrance", "vacancy", "intern", "campus", "test", "result", "admit", "coaching", "training"]
        if not any(kw in combined for kw in student_keywords):
            continue
            
        student_data = student_classifier.process_article(article.title, article.content)
        if not student_data:
            continue
        
        # Merge with existing article metadata for UI
        student_data["id"] = article.id
        student_data["url"] = article.raw_news.url if article.raw_news else "#"
        student_data["source_name"] = article.raw_news.source_name if article.raw_news else "Unknown"
        student_data["published_at"] = article.published_at.isoformat() if article.published_at else None
        student_data["image_url"] = article.raw_news.url_to_image if article.raw_news and article.raw_news.url_to_image else get_fallback_image(article.title)
        
        processed_articles.append(student_data)
        
        # Track trend stats
        category_counts[student_data["category"]] += 1
        if "Scholarship" in student_data["category"]:
            scholarship_count += 1
            
        # Track exams for trends
        if "Exam" in student_data["category"]:
            for tag in student_data["tags"]:
                if tag != "#Exam" and tag != "#CompetitiveExams" and tag != "#BoardExams":
                    exam_mentions[tag] = exam_mentions.get(tag, 0) + 1
                    
    # Inject LIVE scholarships if the DB returned 0
    if scholarship_count == 0:
        logger.info("0 scholarships found in DB. Fetching live from external sources...")
        live_scholarships = _fetch_live_scholarships_cache()
        for article in live_scholarships:
            processed_articles.append(article)
            scholarship_count += 1
            category_counts["Scholarships & Internships"] += 1

    # Sort by trend score (highest first)
    processed_articles.sort(key=lambda x: x["trend_score"], reverse=True)
    
    # Finalize trends
    top_exam = max(exam_mentions.items(), key=lambda x: x[1])[0] if exam_mentions else "N/A"
    
    # Most discussed topic
    most_discussed = "N/A"
    if processed_articles:
        top_tags = {}
        ignored_tags = {"#Exam", "#CompetitiveExams", "#BoardExams", "#Education", "#Update", "#News", "#Students", "#Scholarship", "#Job", "#Career", "#StudyAbroad", "#Result"}
        for a in processed_articles[:20]:
            for t in a.get("tags", []):
                if t not in ignored_tags:
                    top_tags[t] = top_tags.get(t, 0) + 1
        if top_tags:
            most_discussed = max(top_tags.items(), key=lambda x: x[1])[0]
    
    cache["articles"] = processed_articles
    cache["trends"] = {
        "total_articles": len(processed_articles),
        "scholarship_count": scholarship_count,
        "category_counts": category_counts,
        "most_discussed_topic": most_discussed,
        "top_trending_exam": top_exam
    }
    cache["last_updated"] = now
    
    # If no articles found for specific country, try to populate from Global for better UX
    if len(processed_articles) == 0 and target_name != "Global":
        logger.info(f"0 articles found for {target_name}. Attempting to fallback to Global student news.")
        return _update_student_cache_if_needed(db, force=True, country="Global")

    logger.info(f"Student Cache updated. Found {len(processed_articles)} relevant articles for {target_name}.")

# --- ADMIN MANAGEMENT API ENDPOINTS ---

@router.get("/api/articles")
async def get_all_articles(db: Session = Depends(get_db)):
    """Backend endpoint for admin panel to fetch all verified intelligence"""
    try:
        articles = db.query(VerifiedNews).order_by(VerifiedNews.published_at.desc()).all()
        return [a.to_dict() for a in articles]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/articles/{article_id}")
async def delete_article(article_id: int, db: Session = Depends(get_db)):
    """Admin endpoint to remove an intelligence node"""
    try:
        article = db.query(VerifiedNews).filter(VerifiedNews.id == article_id).first()
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        db.delete(article)
        db.commit()
        return {"status": "success", "message": f"Article {article_id} deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/ads")
async def get_all_ads(db: Session = Depends(get_db)):
    """Fetch all campaign nodes (advertisements)"""
    try:
        from src.database.models import Advertisement
        ads = db.query(Advertisement).order_by(Advertisement.created_at.desc()).all()
        return ads
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class AdCreateRequest(BaseModel):
    image_url: str
    caption: str
    position: str = "both"
    target_node: str = "Global"
    target_url: str = None

@router.post("/api/ads")
async def create_ad(payload: AdCreateRequest, db: Session = Depends(get_db)):
    """Admin endpoint to deploy a new campaign node"""
    try:
        from src.database.models import Advertisement
        new_ad = Advertisement(
            image_url=payload.image_url,
            caption=payload.caption,
            position=payload.position,
            target_node=payload.target_node,
            target_url=payload.target_url
        )
        db.add(new_ad)
        db.commit()
        db.refresh(new_ad)
        return {"success": True, "ad": new_ad}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/ads/{ad_id}")
async def delete_ad(ad_id: int, db: Session = Depends(get_db)):
    """Remove a campaign node"""
    try:
        from src.database.models import Advertisement
        ad = db.query(Advertisement).filter(Advertisement.id == ad_id).first()
        if not ad:
            raise HTTPException(status_code=404, detail="Ad not found")
        db.delete(ad)
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/newspapers")
async def get_all_newspapers(db: Session = Depends(get_db)):
    """Fetch all registered source nodes"""
    try:
        from src.database.models import Newspaper
        papers = db.query(Newspaper).order_by(Newspaper.name.asc()).all()
        return papers
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class NewspaperCreateRequest(BaseModel):
    name: str
    url: str
    country: str = "Global"
    logo_text: str = None
    logo_color: str = None

@router.post("/api/newspapers")
async def create_newspaper(payload: NewspaperCreateRequest, db: Session = Depends(get_db)):
    """Register a new newspaper source"""
    try:
        from src.database.models import Newspaper
        new_paper = Newspaper(
            name=payload.name,
            url=payload.url,
            country=payload.country,
            logo_text=payload.logo_text,
            logo_color=payload.logo_color
        )
        db.add(new_paper)
        db.commit()
        db.refresh(new_paper)
        return {"success": True, "paper": new_paper}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/newspapers/{paper_id}")
async def delete_newspaper(paper_id: int, db: Session = Depends(get_db)):
    """Unregister a source node"""
    try:
        from src.database.models import Newspaper
        paper = db.query(Newspaper).filter(Newspaper.id == paper_id).first()
        if not paper:
            raise HTTPException(status_code=404, detail="Newspaper not found")
        db.delete(paper)
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# --- PERSONAL AI NEWS AGENT ---

@router.get("/personal-agent")
async def personal_agent_page(request: Request):
    """Render the Personal AI News Agent UI."""
    from src.analysis.llm_analyzer import LLMAnalyzer
    analyzer = LLMAnalyzer()
    # Get categories from the mock analyzer's logic or DB
    available_interests = [
        "AI & Machine Learning", "Business & Economy", "Defense & Security",
        "Education", "Entertainment", "Environment & Climate", "General",
        "India / Local News", "Lifestyle & Wellness", "Other News", "Politics",
        "Science & Health", "Sports", "Technology", "Twitter 𝕏", "World News"
    ]
    return templates.TemplateResponse("personal_agent.html", {
        "request": request, 
        "available_interests": available_interests
    })

@router.get("/api/personal-news")
async def api_get_personal_news(interests: str, db: Session = Depends(get_db)):
    """Fetch relevant news based on comma-separated user interests."""
    if not interests:
        return {"status": "success", "articles": []}
        
    interest_list = [i.strip().lower() for i in interests.split(",")]
    
    # Simple query matching tags, category, or title
    from sqlalchemy import or_
    
    # We want to match all interests, but limit to recent high impact news
    now_utc = datetime.utcnow()
    lookback = now_utc - timedelta(days=5) # 5 days lookback
    
    all_articles = []
    
    for interest in interest_list:
        # Create a search term with wildcards for ILIKE
        search_term = f"%{interest}%"
        
        articles = db.query(VerifiedNews).filter(
            or_(
                VerifiedNews.category.ilike(search_term),
                VerifiedNews.title.ilike(search_term),
                VerifiedNews.why_it_matters.ilike(search_term)
            ),
            VerifiedNews.created_at >= lookback
        ).order_by(VerifiedNews.impact_score.desc(), VerifiedNews.created_at.desc()).limit(15).all()
        
        # Structure for frontend
        for a in articles:
            # Only add if not already in list
            if not any(existing["id"] == a.id for existing in all_articles):
                all_articles.append({
                    "id": a.id,
                    "title": a.title,
                    "summary": a.why_it_matters or "Key developments in this area.",
                    "url": a.raw_news.url if a.raw_news else "#",
                    "image_url": (a.raw_news.url_to_image if a.raw_news and a.raw_news.url_to_image else 
                                 get_fallback_image(a.title)),
                    "source_name": a.raw_news.source_name if a.raw_news else "Global Intelligence",
                    "published_at": a.created_at.isoformat() if a.created_at else None,
                    "matched_interest": interest.title()
                })
                
    # Sort mixed results by published date
    all_articles.sort(key=lambda x: x["published_at"] or "", reverse=True)
    
    return {"status": "success", "articles": all_articles[:30]}

@router.post("/api/chat-article")
async def api_chat_article(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    article_id = data.get("article_id")
    query = data.get("query")
    
    if not article_id or not query:
        raise HTTPException(status_code=400, detail="Missing article_id or query")
    
    chat_engine = NewsChatEngine()
    response = chat_engine.chat_with_article(db, article_id, query)
    return {"response": response}

@router.post("/api/flag-article")
async def api_flag_article(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    firebase_uid = data.get("firebase_uid")
    news_id = data.get("news_id")
    reason = data.get("reason", "Reported by user")
    
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already flagged by this user
    existing = db.query(FlaggedArticle).filter(
        FlaggedArticle.user_id == user.id,
        FlaggedArticle.news_id == news_id
    ).first()
    
    if existing:
        return {"status": "already_flagged", "message": "You have already flagged this article."}
    
    # Create flag record
    flag = FlaggedArticle(user_id=user.id, news_id=news_id, reason=reason)
    db.add(flag)
    
    # Update article flag count
    article = db.query(VerifiedNews).filter(VerifiedNews.id == news_id).first()
    if article:
        article.flag_count += 1
        db.commit() # Save flag count first
        
        # Trigger AI verification if flagged first time
        if article.flag_count == 1:
            from src.analysis.llm_analyzer import LLMAnalyzer
            analyzer = LLMAnalyzer()
            result = await analyzer.verify_news_factcheck(article.title, article.content or "")
            if result.get("is_fake"):
                article.is_fake = True
                # Award bounty points to the first reporter
                user.bounty_points += 50
                db.commit()
                return {"status": "success", "message": "Fake news verified! 50 Bounty Points awarded.", "points": user.bounty_points}
    
    db.commit()
    return {"status": "success", "message": "Report submitted. Our AI is verifying."}

@router.get("/api/geopolitics-prediction")
async def api_get_prediction(db: Session = Depends(get_db)):
    # Get top 10 recent headlines for context
    trends = db.query(VerifiedNews.title).order_by(VerifiedNews.created_at.desc()).limit(10).all()
    trend_list = [t[0] for t in trends]
    
    from src.analysis.llm_analyzer import LLMAnalyzer
    analyzer = LLMAnalyzer()
    prediction = await analyzer.generate_geopolitical_prediction(trend_list)
    return prediction

@router.get("/api/search-news")
async def api_search_news(
    q: str = "", 
    page: int = 1, 
    interests: str = None, 
    db: Session = Depends(get_db)
):
    offset = (page - 1) * 12
    query = db.query(VerifiedNews)
    
    if q:
        query = query.filter(
            or_(
                VerifiedNews.title.ilike(f"%{q}%"),
                VerifiedNews.why_it_matters.ilike(f"%{q}%")
            )
        )
    
    if interests:
        interest_list = [i.strip() for i in interests.split(',')]
        # More robust matching: handle both exact and partial
        filters = []
        for i in interest_list:
            # Case-insensitive partial match for category
            filters.append(VerifiedNews.category.ilike(f"%{i}%"))
            # Match in text as well if specifically searching interests
            filters.append(VerifiedNews.title.ilike(f"%{i}%"))
            filters.append(VerifiedNews.why_it_matters.ilike(f"%{i}%"))
            # If it's "Defense & Security", also try "Defense" 
            if " & " in i:
                parts = i.split(" & ")
                for p in parts:
                    if len(p) > 3:
                        filters.append(VerifiedNews.category.ilike(f"%{p}%"))
        
        query = query.filter(or_(*filters))
    
    # HF DEBUG: Expand lookback if no results found to avoid blank screen
    articles = query.order_by(VerifiedNews.impact_score.desc(), VerifiedNews.created_at.desc()).offset(offset).limit(12).all()
    
    if not articles and page == 1:
        # Retry with MUCH longer lookback (30 days) to ensure something shows up
        lookback_extended = datetime.utcnow() - timedelta(days=30)
        query_ext = db.query(VerifiedNews).filter(VerifiedNews.created_at >= lookback_extended)
        if q:
            query_ext = query_ext.filter(or_(VerifiedNews.title.ilike(f"%{q}%"), VerifiedNews.why_it_matters.ilike(f"%{q}%")))
        if interests:
            query_ext = query_ext.filter(or_(*filters))
        articles = query_ext.order_by(VerifiedNews.impact_score.desc(), VerifiedNews.created_at.desc()).offset(offset).limit(12).all()
    
    return {
        "status": "success",
        "articles": [{
            "id": a.id,
            "title": a.title,
            "summary": (a.why_it_matters or (" ".join(a.summary_bullets[:2]) if a.summary_bullets else ""))[:500],
            "url": a.url,
            "image_url": a.image_url or "https://images.unsplash.com/photo-1504711434969-e33886168f5c?q=80&w=1000",
            "source_name": a.source_name,
            "published_at": a.created_at.isoformat() if a.created_at else None,
            "matched_interest": a.category
        } for a in articles],
        "has_more": len(articles) == 12
    }
