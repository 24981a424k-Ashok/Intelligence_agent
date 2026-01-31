import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from src.database.models import VerifiedNews
from src.analysis.llm_analyzer import LLMAnalyzer
import openai
from src.config.settings import OPENAI_API_KEY

logger = logging.getLogger(__name__)

class NewsChatEngine:
    def __init__(self):
        self.api_key = OPENAI_API_KEY
        if self.api_key:
            self.client = openai.OpenAI(api_key=self.api_key)
        else:
            self.client = None

    def get_response(self, session: Session, query: str) -> str:
        """
        Simple RAG: Find relevant news and answer based on it.
        """
        if not self.client:
            return "I'm sorry, I cannot answer questions right now as no AI API key is configured."

        # 1. Search DB for relevant keywords (Naive search for now)
        # In a real app, use Vector Search (FAISS) which is in requirements
        keywords = query.split()
        if not keywords:
            results = session.query(VerifiedNews).order_by(VerifiedNews.published_at.desc()).limit(3).all()
        else:
            # Simple keyword search with multiple words
            filters = [VerifiedNews.title.contains(k) | VerifiedNews.content.contains(k) for k in keywords[:3]]
            from sqlalchemy import or_
            results = session.query(VerifiedNews).filter(or_(*filters)).limit(5).all()

        if not results:
            # Fallback to general latest news
            results = session.query(VerifiedNews).order_by(VerifiedNews.published_at.desc()).limit(3).all()

        context = "\n---\n".join([
            f"Title: {n.title}\nSummary: {n.summary_bullets}\nWhy it matters: {n.why_it_matters}\nWho is affected: {n.who_is_affected}"
            for n in results
        ])

        system_prompt = """
        You are a Conversational News Intelligence Assistant.
        Answer user questions ONLY based on the provided news context.
        Always cite the source/title.

        CRITICAL SAFETY RULES:
        1. NEVER claim absolute accuracy.
        2. NO hallucinated facts. If information is missing, say so politely.
        3. Maintain a neutral, factual tone.
        4. If the information is not in the context, state "Based on current data, I do not have information on this."
        """

        user_prompt = f"User Question: {query}\n\nContext:\n{context}"

        try:
            # Check if API key is a placeholder
            if not self.api_key or self.api_key.startswith("your_"):
                return self._mock_response(query, results)

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.4
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return self._mock_response(query, results)

    def _mock_response(self, query: str, results: List[VerifiedNews]) -> str:
        """
        Fallback response using keyword matching and context.
        """
        if not results:
            return "I couldn't find any news related to your query. Try asking something else!"
        
        response = f"I found several relevant stories in our system:\n\n"
        for n in results:
            response += f"• {n.title} (Category: {n.category})\n"
            response += f"  - Impact: {n.why_it_matters}\n"
            response += f"  - Affected: {n.who_is_affected}\n\n"
        
        response += "Note: Real-time conversational analysis is currently in mock mode due to API configuration."
        return response
