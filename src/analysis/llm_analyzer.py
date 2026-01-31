import os
import json
import logging
from typing import Dict, Any
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

    def analyze_article(self, title: str, content: str) -> Dict[str, Any]:
        """
        Analyze an article to extract structured intelligence.
        """
        if not self.client:
            return self._mock_analysis(title)

        prompt = f"""
        Analyze the following news article:
        Title: {title}
        Content: {content[:2000]} # Truncate to avoid huge context

        Provide the output in valid JSON format with the following keys:
        - "summary_bullets": [array of 3-5 strings, bullet points, 15-25 words each]
        - "category": "one of the 14 mandatory categories"
        - "impact_score": integer 1-10
        - "why_it_matters": "string explaining impact"
        - "who_is_affected": "stakeholders affected"
        - "short_term_impact": "immediate consequences"
        - "long_term_impact": "broader effects"
        - "sentiment": "Positive/Negative/Neutral"
        - "certainty_flag": "High/Medium/Low based on source clarity"

        CRITICAL SAFETY RULES:
        1. NEVER claim absolute accuracy.
        2. NO hallucinated facts. If information is missing, state "Data not provided".
        3. If information is uncertain or evolving, use "Evolving" or "Uncertain" in impacts.
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo", # Use 4 for better quality if affordable
                messages=[
                    {"role": "system", "content": "You are an expert news analyst. Output ONLY JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            raw_content = response.choices[0].message.content
            # Clean up potential markdown code blocks
            if "```json" in raw_content:
                raw_content = raw_content.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_content:
                raw_content = raw_content.split("```")[1].strip()
                
            return json.loads(raw_content)

        except Exception as e:
            if "insufficient_quota" in str(e) or (hasattr(e, 'code') and e.code == 'insufficient_quota'):
                logger.error("OpenAI Quota Exceeded! Switching to mock analysis for this cycle. Please check your billing/plan.")
            else:
                logger.error(f"LLM Analysis failed: {e}")
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
