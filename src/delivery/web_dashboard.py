from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session
from src.database.models import SessionLocal, DailyDigest, VerifiedNews
from src.analysis.chat_engine import NewsChatEngine

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/")
async def landing_page(request: Request):
    from src.config import settings
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
async def dashboard(request: Request, db: Session = Depends(get_db)):
    from src.config import settings
    # Get latest digest
    latest_digest = db.query(DailyDigest).order_by(DailyDigest.date.desc()).first()
    
    firebase_config = {
        "apiKey": settings.FIREBASE_API_KEY,
        "authDomain": settings.FIREBASE_AUTH_DOMAIN,
        "projectId": settings.FIREBASE_PROJECT_ID,
        "storageBucket": settings.FIREBASE_STORAGE_BUCKET,
        "messagingSenderId": settings.FIREBASE_MESSAGING_SENDER_ID,
        "appId": settings.FIREBASE_APP_ID
    }
    
    context = {
        "request": request,
        "digest": latest_digest.content_json if latest_digest else None,
        "date": latest_digest.date.strftime("%B %d, %Y") if latest_digest else "No Digest Available",
        "firebase_config": firebase_config,
        "vapid_public_key": settings.VAPID_PUBLIC_KEY
    }
    return templates.TemplateResponse("dashboard.html", context)

@router.get("/archive")
async def archive(request: Request, db: Session = Depends(get_db)):
    topic_list = db.query(DailyDigest).order_by(DailyDigest.date.desc()).limit(10).all()
    return templates.TemplateResponse("archive.html", {"request": request, "digests": topic_list})

@router.get("/saved")
async def saved_items_page(request: Request):
    from src.config import settings
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
async def history_page(request: Request):
    from src.config import settings
    firebase_config = {
        "apiKey": settings.FIREBASE_API_KEY,
        "authDomain": settings.FIREBASE_AUTH_DOMAIN,
        "projectId": settings.FIREBASE_PROJECT_ID,
        "storageBucket": settings.FIREBASE_STORAGE_BUCKET,
        "messagingSenderId": settings.FIREBASE_MESSAGING_SENDER_ID,
        "appId": settings.FIREBASE_APP_ID
    }
    return templates.TemplateResponse("history.html", {"request": request, "firebase_config": firebase_config})

class ChatRequest(BaseModel):
    message: str

@router.post("/api/chat")
async def chat_endpoint(payload: ChatRequest, db: Session = Depends(get_db)):
    chat_engine = NewsChatEngine()
    response = chat_engine.get_response(db, payload.message)
    return {"response": response}

class NoteRequest(BaseModel):
    text: str
    url: str
    timestamp: str

@router.post("/api/save-note")
async def save_note_endpoint(payload: NoteRequest, db: Session = Depends(get_db)):
    # For now, just acknowledge the note
    # In a full implementation, you would save this to the database
    # associated with the authenticated user
    return {"status": "success", "message": "Note saved"}

class AIQueryRequest(BaseModel):
    query: str
    context: str

@router.post("/api/ai-query")
async def ai_query_endpoint(payload: AIQueryRequest, db: Session = Depends(get_db)):
    chat_engine = NewsChatEngine()
    full_query = f"{payload.query}\n\nContext: {payload.context}"
    response = chat_engine.get_response(db, full_query)
    return {"response": response}

class AuthRequest(BaseModel):
    id_token: str

@router.post("/api/login")
async def login_endpoint(payload: AuthRequest, db: Session = Depends(get_db)):
    from src.config.firebase_config import verify_token
    from src.database.models import User
    
    decoded = verify_token(payload.id_token)
    if not decoded:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    uid = decoded['uid']
    user = db.query(User).filter(User.firebase_uid == uid).first()
    if not user:
        user = User(
            firebase_uid=uid,
            email=decoded.get('email'),
            phone=decoded.get('phone_number')
        )
        db.add(user)
        db.commit()
    
    return {"status": "success", "uid": uid}

class SubscribeRequest(BaseModel):
    uid: str
    push_token: str
    categories: list # e.g. ["Technology", "All"]

@router.post("/api/subscribe")
async def subscribe_endpoint(payload: SubscribeRequest, db: Session = Depends(get_db)):
    from src.database.models import User, Subscription
    
    user = db.query(User).filter(User.firebase_uid == payload.uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.push_token = payload.push_token
    
    # Simple clear and re-add for subscriptions
    db.query(Subscription).filter(Subscription.user_id == user.id).delete()
    for cat in payload.categories:
        sub = Subscription(user_id=user.id, category=cat)
        db.add(sub)
    
    db.commit()
    return {"status": "subscribed"}
