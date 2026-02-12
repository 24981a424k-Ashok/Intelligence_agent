import json
import logging
import random
import os
from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy.orm import Session
from src.database.models import VerifiedNews, DailyDigest
from src.analysis.llm_analyzer import LLMAnalyzer

class ExamGenerator:
    def __init__(self):
        self.llm = LLMAnalyzer()

    def get_yesterday_news(self, db: Session) -> List[Dict]:
        """Fetch verified news from yesterday 12:00 PM to 9:00 PM IST"""
        # Calculate time window
        logging.basicConfig(filename='exam_gen.log', level=logging.INFO, 
                            format='%(asctime)s - %(levelname)s - %(message)s')
        
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        
        # approximate 12 PM - 9 PM IST in UTC
        # IST is UTC+5:30
        # 12:00 PM IST = 06:30 AM UTC
        # 09:00 PM IST = 03:30 PM UTC
        
        start_time = yesterday.replace(hour=6, minute=30, second=0, microsecond=0)
        end_time = yesterday.replace(hour=15, minute=30, second=0, microsecond=0)
        
        news = db.query(VerifiedNews).filter(
            VerifiedNews.published_at >= start_time,
            VerifiedNews.published_at <= end_time,
            VerifiedNews.impact_score >= 6
        ).all()
        
        return [n.to_dict() for n in news]

    def generate_mock_test(self, db: Session) -> Dict:
        """Generate a 15-20 question mock test from yesterday's news"""
        news_items = self.get_yesterday_news(db)
        
        if not news_items:
            # Fallback to latest digest if no specific window news found
            latest = db.query(DailyDigest).order_by(DailyDigest.date.desc()).first()
            if latest:
                news_items = latest.content_json.get('top_stories', [])

        if not news_items:
            return {"error": "No sufficient news found to generate exam."}

        # Prepare context for LLM
        news_text = "\n\n".join([f"- {n.get('title', 'Unknown')}: {n.get('summary', 'No summary')} (Category: {n.get('category', 'General')})" for n in news_items])
        news_text = "\n\n".join([f"- {n.get('title', 'Unknown')}: {n.get('summary', 'No summary')} (Category: {n.get('category', 'General')})" for n in news_items])
        logging.info(f"News text length: {len(news_text)}")
        logging.info(f"News text preview: {news_text[:500]}")
        
        prompt = f"""
        You are an AI Current Affairs Exam Expert specializing in Indian and global competitive exams (UPSC, SSC, Banking).
        
        Create a Daily Current Affairs Mock Test based on the following news:
        {news_text}
        
        RULES:
        1. Generate exactly 15 questions.
        2. Format: 
           - 9 MCQs (4 options)
           - 3 Statement-based (as MCQs with options like "Only 1", "Both 1 and 2")
           - 2 Match the Following (formatted as MCQ: "Which pair is correctly matched?" or "Choose the correct sequence")
           - 1 True/False
        3. Sections: National, International, Economy, Science, Sports.
        4. Output JSON format ONLY:
        {{
            "title": "Daily Mock Test - {datetime.now().strftime('%Y-%m-%d')}",
            "questions": [
                {{
                    "id": 1,
                    "type": "MCQ",
                    "section": "National Affairs",
                    "question": "...",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "A",
                    "explanation": "..."
                }}
            ]
        }}
        """
        
        try:
            response = self.llm.get_completion(prompt)
            # Clean JSON if needed
            response = response.replace("```json", "").replace("```", "").strip()
            return json.loads(response)
        except Exception as e:
            logging.error(f"Exam Generation Error: {e}")
            print(f"Exam Generation Error (LLM/Quota): {e}")
            
            # Fallback: Load from question bank
            try:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                bank_path = os.path.join(base_dir, 'data', 'question_bank.json')
                print(f"DEBUG: Attempting to load question bank from: {bank_path}")
                
                with open(bank_path, 'r', encoding='utf-8') as f:
                    all_questions = json.load(f)
                
                # Randomly select 15 questions
                selected_questions = random.sample(all_questions, min(len(all_questions), 15))
                
                # Re-index ids
                for idx, q in enumerate(selected_questions):
                    q['id'] = idx + 1
                    
                return {
                    "title": f"Daily Mock Test - General Awareness - {datetime.now().strftime('%d %b %Y')}",
                    "questions": selected_questions
                }
            except Exception as bank_error:
                logging.error(f"Fallback Bank Error: {bank_error}")
                # Ultimate fallback (if even the file fails)
                return {
                    "title": f"Daily Mock Test (Final Fallback)",
                    "questions": [
                         {
                            "id": 1,
                            "type": "MCQ",
                            "section": "General",
                            "question": "Which organization releases the 'World Economic Outlook'?",
                            "options": ["IMF", "World Bank", "WEF", "ADB"],
                            "correct_answer": "IMF",
                            "explanation": "The IMF releases the WEO report."
                         }
                    ]
                }

