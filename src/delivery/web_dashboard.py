import os
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

# Fallback Image Pool (Expanded to 50+ to minimize repetition)
FALLBACK_IMAGES = [
    # Technology / AI / Modern
    'https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=800&q=80',
    'https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=800&q=80',
    'https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=800&q=80',
    'https://images.unsplash.com/photo-1485827404703-89b55fcc595e?auto=format&fit=crop&w=800&q=80',
    'https://images.unsplash.com/photo-1504384308090-c54be385263d?auto=format&fit=crop&w=800&q=80',
    'https://images.unsplash.com/photo-1555949963-ff9fe0c870eb?auto=format&fit=crop&w=800&q=80', # Code
    'https://images.unsplash.com/photo-1525547719571-a2d4ac8945e2?auto=format&fit=crop&w=800&q=80', # Phone
    'https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&w=800&q=80', # Cyber
    'https://images.unsplash.com/photo-1519389950473-47ba0277781c?auto=format&fit=crop&w=800&q=80', # Work
    'https://images.unsplash.com/photo-1531297484001-80022131f5a1?auto=format&fit=crop&w=800&q=80', # Laptop
    'https://images.unsplash.com/photo-1461749280684-dccba630e2f6?auto=format&fit=crop&w=800&q=80', # Code
    'https://images.unsplash.com/photo-1518773553398-650c184e0bb3?auto=format&fit=crop&w=800&q=80', # Network
    'https://images.unsplash.com/photo-1523961131990-5ea7c61b2107?auto=format&fit=crop&w=800&q=80', # Data
    'https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=800&q=80', # Chip
    'https://images.unsplash.com/photo-1544197150-b99a580bb7a8?auto=format&fit=crop&w=800&q=80', # Metro

    # Business / Market / Office
    'https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?auto=format&fit=crop&w=800&q=80', # Stocks
    'https://images.unsplash.com/photo-1611974765270-ca12586343bb?auto=format&fit=crop&w=800&q=80', # Graph
    'https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=800&q=80', # Laptop Graph
    'https://images.unsplash.com/photo-1556761175-b413da4baf72?auto=format&fit=crop&w=800&q=80', # Meeting
    'https://images.unsplash.com/photo-1507679799987-c73774573b8a?auto=format&fit=crop&w=800&q=80', # Suit
    'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=800&q=80', # Skyscraper
    'https://images.unsplash.com/photo-1454165833767-027ffea9e77b?auto=format&fit=crop&w=800&q=80', # Workspace
    'https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?auto=format&fit=crop&w=800&q=80', # Glasses
    'https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?auto=format&fit=crop&w=800&q=80', # Accounting
    'https://images.unsplash.com/photo-1462206092226-f46025ffe607?auto=format&fit=crop&w=800&q=80', # Minimal

    # World / News / General
    'https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=800&q=80', # Newspaper
    'https://images.unsplash.com/photo-1495020689067-958852a7765e?auto=format&fit=crop&w=800&q=80', # News Stack
    'https://images.unsplash.com/photo-1526778548025-fa2f459cd5c1?auto=format&fit=crop&w=800&q=80', # Globe
    'https://images.unsplash.com/photo-1521295121783-8a321d551ad2?auto=format&fit=crop&w=800&q=80', # Map
    'https://images.unsplash.com/photo-1489749798305-4fea3ae63d43?auto=format&fit=crop&w=800&q=80', # Earth
    'https://images.unsplash.com/photo-1529107386315-e1a2ed48a620?auto=format&fit=crop&w=800&q=80', # Parliament
    'https://images.unsplash.com/photo-1523995462485-3d171b5c8fa9?auto=format&fit=crop&w=800&q=80', # Justice
    'https://images.unsplash.com/photo-1504198266287-1659872e6590?auto=format&fit=crop&w=800&q=80', # City
    'https://images.unsplash.com/photo-1444723121867-c61e74ebf60a?auto=format&fit=crop&w=800&q=80', # Urban
    'https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?auto=format&fit=crop&w=800&q=80', # Skyline

    # Concept / Abstract
    'https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=800&q=80', # Nature
    'https://images.unsplash.com/photo-1469474968028-56623f02e42e?auto=format&fit=crop&w=800&q=80', # Mountain
    'https://images.unsplash.com/photo-1585829365234-78d2b5020164?auto=format&fit=crop&w=800&q=80', # Breaking Tape
    'https://images.unsplash.com/photo-1566378246598-5b11a0d486cc?auto=format&fit=crop&w=800&q=80', # Event
    'https://images.unsplash.com/photo-1550684848-fac1c5b4e853?auto=format&fit=crop&w=800&q=80', # Wallet
    'https://images.unsplash.com/photo-1579621970563-ebec7560ff3e?auto=format&fit=crop&w=800&q=80', # Money
    'https://images.unsplash.com/photo-1565514020176-dbf2277f0789?auto=format&fit=crop&w=800&q=80', # Food
    'https://images.unsplash.com/photo-1505751172876-fa1923c5c528?auto=format&fit=crop&w=800&q=80', # Health
    'https://images.unsplash.com/photo-1532094349884-543bc11b234d?auto=format&fit=crop&w=800&q=80', # Science
    'https://images.unsplash.com/photo-1507413245164-6160d8298b31?auto=format&fit=crop&w=800&q=80', # Lab
    'https://images.unsplash.com/photo-1453847668862-487637052f8a?auto=format&fit=crop&w=800&q=80', # Abstract
    'https://images.unsplash.com/photo-1550989460-0adf9ea622e2?auto=format&fit=crop&w=800&q=80', # Shopping
    'https://images.unsplash.com/photo-1504384764586-bb4cdc1707b0?auto=format&fit=crop&w=800&q=80', # Network 2
    'https://images.unsplash.com/photo-1593642532400-2682810df593?auto=format&fit=crop&w=800&q=80', # Modern
    'https://images.unsplash.com/photo-1518186285589-2f7649de83e0?auto=format&fit=crop&w=800&q=80'  # Coins
]

def get_fallback_image(seed: str) -> str:
    """Deterministically select a fallback image based on string hash"""
    if not seed: return FALLBACK_IMAGES[0]
    hash_val = sum(ord(c) for c in seed)
    return FALLBACK_IMAGES[hash_val % len(FALLBACK_IMAGES)]

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
async def dashboard(request: Request, category: str = None, db: Session = Depends(get_db)):
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

    digest_data = latest_digest.content_json if latest_digest else None
    
    # Inject Fallback Images Server-Side for Initial Render
    if digest_data:
        if "breaking_news" in digest_data:
            for item in digest_data["breaking_news"]:
                if not item.get("image_url"):
                    item["image_url"] = get_fallback_image(item.get("headline") or item.get("title") or "news")
        
        if "top_stories" in digest_data:
            for item in digest_data["top_stories"]:
                if not item.get("image_url"):
                    item["image_url"] = get_fallback_image(item.get("title") or "news")
    
    # Filter by Category if requested
    selected_category = category
    if digest_data and category:
        # Filter top stories
        all_stories = digest_data.get("top_stories", [])
        # We can also pull from the "categories" dictionary if we want more depth
        # Normalize category to match backend keys (typically lowercase/snake_case)
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
        # Direct match
        if target_key in categories:
             cat_stories = categories[target_key]
        elif normalized_category in categories:
            cat_stories = categories[normalized_category]
        else:
            # Fallback: Check keys case-insensitively
            for k, v in categories.items():
                if k.lower() == normalized_category or k.lower() == target_key.lower():
                    cat_stories = v
                    break
        
        # If we have specific category stories, use them. Otherwise filter top stories.
        if cat_stories:
             # Normalize format to match top_stories
             normalized_cat_stories = []
             for s in cat_stories:
                 normalized_cat_stories.append({
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
             digest_data["top_stories"] = normalized_cat_stories
        else:
             # Try to filter existing top_stories
             digest_data["top_stories"] = [s for s in all_stories if s.get("category") == category]

    context = {
        "request": request,
        "digest": digest_data,
        "date": latest_digest.date.strftime("%Y-%m-%d") if latest_digest else "System Initializing",
        "firebase_config": firebase_config,
        "vapid_public_key": settings.VAPID_PUBLIC_KEY,
        "selected_category": selected_category
    }
    
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
async def get_breaking_news(db: Session = Depends(get_db)):
    """API endpoint for breaking news auto-refresh"""
    latest_digest = db.query(DailyDigest).filter(
        DailyDigest.is_published == True
    ).order_by(DailyDigest.date.desc()).first()
    
    breaking_news = []
    if latest_digest and "breaking_news" in latest_digest.content_json:
        breaking_news = latest_digest.content_json["breaking_news"]
        
        # Inject Fallback Images Server-Side
        for item in breaking_news:
            if not item.get("image_url"):
                item["image_url"] = get_fallback_image(item.get("headline") or item.get("title") or "news")
    
    return {"breaking_news": breaking_news}

@router.get("/api/more-stories/{category}/{offset}")
async def get_more_stories(category: str, offset: int, db: Session = Depends(get_db)):
    """Fetch more stories for a specific category with offset"""
    latest_digest = db.query(DailyDigest).filter(DailyDigest.is_published == True).order_by(DailyDigest.date.desc()).first()
    
    if not latest_digest:
        return {"stories": []}

    digest_data = latest_digest.content_json
    stories = []
    
    if category == "top_stories":
        stories = digest_data.get("top_stories", [])
    elif category == "breaking_news":
        # Special case for ticker, though usually handled differently
         stories = digest_data.get("breaking_news", [])
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
