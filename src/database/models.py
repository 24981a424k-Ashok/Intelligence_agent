from datetime import datetime
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from src.config.settings import DATABASE_URL

Base = declarative_base()

class RawNews(Base):
    __tablename__ = "raw_news"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(String, index=True)
    source_name = Column(String)
    author = Column(String, nullable=True)
    title = Column(String)
    description = Column(Text, nullable=True)
    url = Column(String, unique=True, index=True)
    url_to_image = Column(String, nullable=True)
    published_at = Column(DateTime)
    content = Column(Text, nullable=True)
    collected_at = Column(DateTime, default=datetime.utcnow)
    
    # Metadata for processing status
    is_verified = Column(Boolean, default=False)
    verification_score = Column(Float, default=0.0)
    processed = Column(Boolean, default=False)

class VerifiedNews(Base):
    __tablename__ = "verified_news"

    id = Column(Integer, primary_key=True, index=True)
    raw_news_id = Column(Integer, ForeignKey("raw_news.id"))
    title = Column(String)
    content = Column(Text)
    summary_bullets = Column(JSON) # List of strings
    
    # Analysis Fields
    analysis = Column(JSON, nullable=True) # Flexible storage for extra metadata
    impact_tags = Column(JSON) # e.g. ["Jobs", "Market"]
    bias_rating = Column(String) # e.g. "Neutral", "Slightly Biased"
    
    category = Column(String, index=True)
    credibility_score = Column(Float)
    impact_score = Column(Integer) # 1-10
    why_it_matters = Column(Text)
    who_is_affected = Column(Text, nullable=True)
    short_term_impact = Column(Text, nullable=True)
    long_term_impact = Column(Text, nullable=True)
    sentiment = Column(String)
    
    published_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    raw_news = relationship("RawNews")

class DailyDigest(Base):
    __tablename__ = "daily_digests"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, default=datetime.utcnow)
    content_json = Column(JSON) # Full structured digest
    is_published = Column(Boolean, default=False)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    firebase_uid = Column(String, unique=True, index=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    push_token = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    subscriptions = relationship("Subscription", back_populates="user")
    folders = relationship("Folder", back_populates="user")
    saved_articles = relationship("SavedArticle", back_populates="user")
    read_history = relationship("ReadHistory", back_populates="user")

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    category = Column(String) # e.g. "Technology", "All"
    
    user = relationship("User", back_populates="subscriptions")

class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="folders")
    saved_articles = relationship("SavedArticle", back_populates="folder")

class SavedArticle(Base):
    __tablename__ = "saved_articles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    news_id = Column(Integer, ForeignKey("verified_news.id"))
    saved_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="saved_articles")
    folder = relationship("Folder", back_populates="saved_articles")
    news = relationship("VerifiedNews")

class ReadHistory(Base):
    __tablename__ = "read_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    news_id = Column(Integer, ForeignKey("verified_news.id"))
    read_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="read_history")
    news = relationship("VerifiedNews")
    
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
