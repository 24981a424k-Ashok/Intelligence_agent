import os
import copy
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from src.database.models import SessionLocal, DailyDigest, User, VerifiedNews, Subscription
from src.config import settings
from src.config.firebase_config import verify_token
from src.analysis.chat_engine import NewsChatEngine
from pydantic import BaseModel

chat_engine = NewsChatEngine()

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
        "jp": "Japan", "cn": "China", "us": "USA", "in": "India", "gb": "UK",
        "ru": "Russia", "de": "Germany", "fr": "France", "au": "Australia", "sg": "Singapore", "ae": "UAE"
    }
    # Reverse mapping: "India" -> "in"
    rev_mapping = {v.lower(): k for k, v in mapping.items()}
    
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

@router.get("/")
async def landing_page(request: Request):
    firebase_config = {
        "apiKey": settings.FIREBASE_API_KEY,
        "authDomain": settings.FIREBASE_AUTH_DOMAIN,
        "projectId": settings.FIREBASE_PROJECT_ID,
        "storageBucket": settings.FIREBASE_STORAGE_BUCKET,
        "messagingSenderId": settings.FIREBASE_MESSAGING_SENDER_ID,
        "appId": settings.FIREBASE_APP_ID
    }
    return templates.TemplateResponse("login.html", {"request": request, "firebase_config": firebase_config})

@router.get("/dashboard")
async def dashboard(request: Request, category: str = None, country: str = None, db: Session = Depends(get_db)):
    # Get latest published digest
    latest_digest = db.query(DailyDigest).filter(DailyDigest.is_published == True).order_by(DailyDigest.date.desc()).first()
    
    # Fallback to ANY digest if no explicitly published one exists (backwards compatibility)
    if not latest_digest:
        latest_digest = db.query(DailyDigest).order_by(DailyDigest.date.desc()).first()

    firebase_config = {
        "apiKey": settings.FIREBASE_API_KEY,
        "authDomain": settings.FIREBASE_AUTH_DOMAIN,
        "projectId": settings.FIREBASE_PROJECT_ID,
        "storageBucket": settings.FIREBASE_STORAGE_BUCKET,
        "messagingSenderId": settings.FIREBASE_MESSAGING_SENDER_ID,
        "appId": settings.FIREBASE_APP_ID
    }

    digest_data = copy.deepcopy(latest_digest.content_json) if latest_digest else None
    
    # 1. Standardize Country Context
    selected_country = country
    selected_category = category
    selected_country_name = None
    
    if digest_data and country:
        target_name, match_keys = normalize_country(country)
        selected_country_name = target_name
        
        # 2. Filter Top Stories
        countries_data = digest_data.get("countries", {})
        country_stories = []
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
            # NO regional stories? 
            # Smart Fallback: Show global but label as such
            for section in ["top_stories", "breaking_news", "trending_news"]:
                if section in digest_data:
                    for s in digest_data[section]:
                        s["is_global_fallback"] = True
            
            digest_data["is_empty_regional"] = True
            trending_title = f"{target_name} Node: Regional Intel Pending"
            
        # 3. Filter ALL OTHER SECTIONS strictly (Breaking/Trending/Brief)
        # ONLY if we actually found regional stories. If we are in fallback mode, 
        # we want to keep the global articles visible.
        if not digest_data.get("is_empty_regional"):
            for section in ["breaking_news", "brief", "trending_news"]:
                if section in digest_data:
                    filtered = [
                        item for item in digest_data[section]
                        if (item.get("country") in match_keys) or (item.get("country_name") in match_keys)
                    ]
                    digest_data[section] = filtered
        
        # 4. Check for Cold Start (No global fallback either)
        if digest_data.get("is_empty_regional") and not digest_data.get("top_stories"):
            digest_data["is_system_initializing"] = True


    # Filter by Category if requested (if country is null)
    elif digest_data and category:
        # Filter top stories
        all_stories = digest_data.get("top_stories", [])
        normalized_category = category.lower().replace(" ", "_").strip()
        
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
        
        if target_key in categories:
             cat_stories = categories[target_key]
        elif normalized_category in categories:
            cat_stories = categories[normalized_category]
        else:
            for k, v in categories.items():
                if k.lower() == normalized_category or k.lower() == target_key.lower():
                    cat_stories = v
                    break
        
        if cat_stories:
             normalized_cat_stories = []
             for s in cat_stories:
                 normalized_cat_stories.append({
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
                     "category": category,
                     "time_ago": s.get("time_ago", "Just Now")
                 })
             digest_data["top_stories"] = normalized_cat_stories
        else:
             digest_data["top_stories"] = [s for s in all_stories if s.get("category") == category]

    context = {
        "request": request,
        "digest": digest_data,
        "date": latest_digest.date.strftime("%Y-%m-%d") if latest_digest else "System Initializing",
        "firebase_config": firebase_config,
        "vapid_public_key": settings.VAPID_PUBLIC_KEY,
        "selected_category": selected_category,
        "selected_country": selected_country,
        "trending_title": locals().get("trending_title", "Trending Feed"),
        "selected_country_name": selected_country_name
    }
    
    # Filter Global View (Home) for English only
    if digest_data and not country:
        non_english = ['jp', 'cn', 'ru', 'de', 'fr', 'Japan', 'China', 'Russia', 'Germany', 'France']
        if "breaking_news" in digest_data:
             digest_data["breaking_news"] = [b for b in digest_data["breaking_news"] if b.get("country") not in non_english]
        if "trending_news" in digest_data:
             digest_data["trending_news"] = [t for t in digest_data["trending_news"] if t.get("country") not in non_english]
        if "brief" in digest_data:
             digest_data["brief"] = [f for f in digest_data["brief"] if f.get("country") not in non_english]
        if "top_stories" in digest_data:
             digest_data["top_stories"] = [s for s in digest_data["top_stories"] if s.get("country") not in non_english]

    # Inject fallback images for ALL sections for consistency
    if digest_data:
        for section in ["top_stories", "breaking_news", "trending_news"]:
            if section in digest_data:
                for idx, item in enumerate(digest_data[section]):
                    if not item.get("image_url"):
                        seed = f"{item.get('headline', '')}{item.get('title', '')}{idx}"
                        item["image_url"] = get_fallback_image(seed)

    return templates.TemplateResponse("dashboard.html", context)

@router.get("/saved")
async def saved_page(request: Request):
    firebase_config = {
        "apiKey": settings.FIREBASE_API_KEY,
        "authDomain": settings.FIREBASE_AUTH_DOMAIN,
        "projectId": settings.FIREBASE_PROJECT_ID,
        "storageBucket": settings.FIREBASE_STORAGE_BUCKET,
        "messagingSenderId": settings.FIREBASE_MESSAGING_SENDER_ID,
        "appId": settings.FIREBASE_APP_ID
    }
    return templates.TemplateResponse("saved.html", {"request": request, "firebase_config": firebase_config})

@router.get("/history")
async def history(request: Request):
    firebase_config = {
        "apiKey": settings.FIREBASE_API_KEY,
        "authDomain": settings.FIREBASE_AUTH_DOMAIN,
        "projectId": settings.FIREBASE_PROJECT_ID,
        "storageBucket": settings.FIREBASE_STORAGE_BUCKET,
        "messagingSenderId": settings.FIREBASE_MESSAGING_SENDER_ID,
        "appId": settings.FIREBASE_APP_ID
    }
    return templates.TemplateResponse("history.html", {"request": request, "firebase_config": firebase_config})

@router.get("/newspaper")
async def newspaper(request: Request):
    firebase_config = {
        "apiKey": settings.FIREBASE_API_KEY,
        "authDomain": settings.FIREBASE_AUTH_DOMAIN,
        "projectId": settings.FIREBASE_PROJECT_ID,
        "storageBucket": settings.FIREBASE_STORAGE_BUCKET,
        "messagingSenderId": settings.FIREBASE_MESSAGING_SENDER_ID,
        "appId": settings.FIREBASE_APP_ID
    }
    return templates.TemplateResponse("newspaper.html", {"request": request, "firebase_config": firebase_config})

@router.get("/business-intelligence")
async def business_intelligence(request: Request, db: Session = Depends(get_db)):
    # This route is restricted
    firebase_config = {
        "apiKey": settings.FIREBASE_API_KEY,
        "authDomain": settings.FIREBASE_AUTH_DOMAIN,
        "projectId": settings.FIREBASE_PROJECT_ID,
        "storageBucket": settings.FIREBASE_STORAGE_BUCKET,
        "messagingSenderId": settings.FIREBASE_MESSAGING_SENDER_ID,
        "appId": settings.FIREBASE_APP_ID
    }
    
    # The actual enforcement happens client-side via Firebase for UX, 
    # but we will also pass the data only if we find a valid digest.
    latest_digest = db.query(DailyDigest).filter(DailyDigest.is_published == True).order_by(DailyDigest.date.desc()).first()
    
    premium_intel = []
    if latest_digest and "premium_intel" in latest_digest.content_json:
        premium_intel = latest_digest.content_json["premium_intel"]
        
    return templates.TemplateResponse("business_intel.html", {
        "request": request, 
        "firebase_config": firebase_config,
        "premium_intel": premium_intel,  # Changed from premium_data
        "restricted_email": "chaparapuashokreddy581@gmail.com"
    })

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
    limit = 12
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
