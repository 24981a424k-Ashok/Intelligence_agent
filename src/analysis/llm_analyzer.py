import os
import json
import logging
import asyncio
from typing import List, Dict, Any
import openai
from src.config.settings import OPENAI_API_KEY

logger = logging.getLogger(__name__)

class LLMAnalyzer:
    def __init__(self):
        self.api_key = OPENAI_API_KEY
        if not self.api_key:
            logger.warning("OpenAI API Key missing! LLM analysis will be skipped/mocked.")
            self.client = None
        else:
            self.client = openai.OpenAI(api_key=self.api_key)

    async def analyze_batch(self, articles: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Analyze multiple articles in parallel.
        """
        if not self.client:
            return [self._mock_analysis(a["title"]) for a in articles]

        # Use AsyncOpenAI client for parallel calls
        from openai import AsyncOpenAI
        async_client = AsyncOpenAI(api_key=self.api_key)

        async def _analyze_single(article):
            title = article["title"]
            content = article.get("content", "")
            prompt = f"""
            Analyze the following news article:
            Title: {title}
            Content: {content[:2000]}

            Provide the output in valid JSON format with the following keys:
            - "summary_bullets": [array of 3-5 strings]
            - "category": "one of the 14 mandatory categories"
            - "impact_score": integer 1-10
            - "why_it_matters": "string"
            - "who_is_affected": "string"
            - "short_term_impact": "string"
            - "long_term_impact": "string"
            - "sentiment": "Positive/Negative/Neutral"
            - "certainty_flag": "High/Medium/Low"
            """
            try:
                response = await async_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are an expert news analyst. Output ONLY JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3
                )
                raw_content = response.choices[0].message.content
                if "```json" in raw_content:
                    raw_content = raw_content.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_content:
                    raw_content = raw_content.split("```")[1].strip()
                
                result = json.loads(raw_content)
                result["title"] = title # Keep track for mapping back
                return result
            except Exception as e:
                logger.error(f"LLM Analysis failed for '{title}': {e}")
                return self._mock_analysis(title)

        results = await asyncio.gather(*[_analyze_single(a) for a in articles])
        return results

    def analyze_article(self, title: str, content: str) -> Dict[str, Any]:
        """
        Analyze a single article to extract structured intelligence.
        (Sync wrapper for compatibility)
        """
        if not self.client:
            return self._mock_analysis(title)
            
        # Re-using the same logic but sync
        prompt = f"""
        Analyze the following news article:
        Title: {title}
        Content: {content[:2000]}

        Provide the output in valid JSON format with keys: summary_bullets, category, impact_score, why_it_matters, who_is_affected, short_term_impact, long_term_impact, sentiment, certainty_flag.
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert news analyst. Output ONLY JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            raw_content = response.choices[0].message.content
            if "```json" in raw_content:
                raw_content = raw_content.split("```json")[1].split("```")[0].strip()
            return json.loads(raw_content)
        except Exception:
            return self._mock_analysis(title)

    def _mock_analysis(self, title: str) -> Dict[str, Any]:
        """Fallback if no API key or error: Keyword-based classification"""
        title_lower = title.lower()
        category = "Other News"
        
        # Simple keyword mapping for the 11 categories
        keywords = {
            "Technology": ["tech", "apple", "google", "microsoft", "cyber", "software", "app", "digital"],
            "AI & Machine Learning": ["ai", "gpt", "llm", "intelligence", "neural", "robot", "algorithm"],
            "Sports": ["sport", "cricket", "football", "nba", "score", "cup", "match", "league", "racing"],
            "Politics": ["election", "parliament", "senate", "minister", "president", "policy", "vote", "congress", "law"],
            "Business & Economy": ["market", "stock", "economy", "trade", "bank", "finance", "ceo", "startup", "inflation"],
            "World News": ["war", "un", "global", "china", "europe", "ukraine", "gaza", "russia", "international"],
            "India / Local News": ["india", "delhi", "mumbai", "modi", "bjp", "cricket", "bollywood"],
            "Science & Health": ["space", "nasa", "doctor", "virus", "cancer", "health", "science", "discovery", "planet"],
            "Education": ["school", "university", "student", "college", "exam", "education", "teacher"],
            "Entertainment": ["movie", "film", "star", "celebrity", "actor", "music", "cinema", "show"],
            "Environment & Climate": ["climate", "environment", "global warming", "sustainability", "green", "carbon", "renewable", "nature"],
            "Lifestyle & Wellness": ["travel", "wellness", "lifestyle", "health", "culture", "fashion", "food", "leisure"],
            "Defense & Security": ["defense", "military", "security", "navy", "army", "warfare", "pentagon", "weapon", "nato"],
            "Breaking News": ["breaking", "urgent", "just in", "emergency", "crisis"]
        }
        
        for cat, keys in keywords.items():
            if any(k in title_lower for k in keys):
                category = cat
                break
                
        # Impact Tags Logic
        impact_tags = []
        if category in ["Business & Economy", "Technology"]:
            impact_tags.append("Market Impact")
            impact_tags.append("Jobs")
        elif category in ["Politics", "World News"]:
            impact_tags.append("Policy Impact")
        elif category in ["Education"]:
            impact_tags.append("Exam Relevance")
        elif category in ["India / Local News"]:
            impact_tags.append("Public Impact")
        elif category in ["Environment & Sustainability"]:
            impact_tags.append("Climate Risk")
            impact_tags.append("Sustainability")
        elif category in ["Defense & Security"]:
            impact_tags.append("National Security")
            impact_tags.append("Geopolitical Impact")
        elif category in ["Lifestyle & Wellness"]:
            impact_tags.append("Personal Wellness")
            
        # Bias Simulation
        bias = "Neutral"
        if category == "Politics":
            bias = "Mixed Perspectives"

        impact = 7 # Default mock impact
        why = f"This update regarding '{title}' is significant for the {category} sector."
        who = "General Public and Stakeholders"
        st = "Immediate awareness and local discussions."
        lt = "Potential policy shifts or long-term behavioral changes."

        return {
            "summary_bullets": [f"Key update regarding {title[:25]}...", "Details on the event implications.", "Expert consensus summary."],
            "category": category,
            "impact_score": impact,
            "impact_tags": impact_tags,
            "bias_rating": bias,
            "why_it_matters": why,
            "who_is_affected": who,
            "short_term_impact": st,
            "long_term_impact": lt,
            "sentiment": "Neutral"
        }
