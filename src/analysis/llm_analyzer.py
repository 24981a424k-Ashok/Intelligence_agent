import os
import json
import logging
import asyncio
from datetime import datetime
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

    async def analyze_batch(self, articles: List[Dict[str, str]], is_sports: bool = False) -> List[Dict[str, Any]]:
        """
        Analyze multiple articles in parallel.
        Uses a fresh client per batch to avoid loop mismatch and closure issues.
        """
        if not self.api_key:
            return [self._mock_analysis(a["title"]) for a in articles]

        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=self.api_key)
        
        try:
            if is_sports:
                tasks = [self._analyze_sports_single(a, client) for a in articles]
            else:
                tasks = [self._analyze_single(a, client) for a in articles]
            results = await asyncio.gather(*tasks)
            return results
        except Exception as e:
            logger.error(f"Batch analysis crash: {e}")
            return [self._mock_analysis(a["title"]) for a in articles]
        finally:
            await client.close()

    async def _analyze_sports_single(self, article: Dict[str, str], client) -> Dict[str, Any]:
        """Specialized Sports News Editor AI analysis."""
        title = article["title"]
        content = article.get("content", "")
        source = article.get("source_name", "Source")
        timestamp = datetime.utcnow().isoformat()

        prompt = f"""
You are a Sports News Editor AI for a professional news platform.

Your task is to identify, classify, and structure news that strictly belongs
to the Sports category.

────────────────────────────
INPUT
────────────────────────────
Article Title: {title}
Article Content: {content[:3000]}
Source: {source}
Published Time (UTC): {timestamp}

────────────────────────────
SPORTS CLASSIFICATION RULES
────────────────────────────
Classify the news as "Sports" ONLY if it directly relates to:
- Matches, tournaments, or competitions
- Athletes or teams (performance, selection, injuries)
- Sports events, schedules, or results
- Transfers, auctions, contracts, or signings
- Coaching or management decisions
- Sports rules, governance, or disciplinary actions

Do NOT classify as Sports if the article is:
- Celebrity gossip or personal life
- General politics or entertainment
- Social media drama without sports relevance

────────────────────────────
TASKS
────────────────────────────

A) CATEGORY VALIDATION
- Decide if this article belongs to the Sports section
- If not, clearly mark: "Not Sports News"

B) SPORTS NEWS TYPE (if Sports)
Classify into ONE of the following:
- Match Result / Live Update
- Tournament / Event News
- Player Performance / Records
- Team & Squad News
- Transfer / Auction / Contract
- Injury / Fitness Update
- Coaching / Management Change
- Sports Governance / Rules
- Sports Business (sponsorship, broadcasting)

C) URGENCY TAG
Assign ONE tag:
- Breaking Sports News (only for rare, urgent events)
- Top Sports Headline
- Regular Sports Update

D) STRUCTURED OUTPUT
Generate JSON with:
1. classification_status: "Sports" | "Not Sports News"
2. sports_type: String
3. headline: String (factual, neutral)
4. key_facts: List of 2–4 bullet points
5. why_it_matters: String (Impact on team, player, tournament, or fans)
6. next_update: String (label uncertainty clearly)
7. urgency_tag: String (from rules above)
10. category: "Sports" (if sports)
11. impact_score: 1-10
12. primary_geography: "India" | "Japan" | "China" | "USA" | "UK" | "Global"

IMPORTANT: Output ONLY valid JSON.
"""
        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a professional Sports News Editor AI. Output ONLY JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )
            raw_content = response.choices[0].message.content
            if "```json" in raw_content:
                raw_content = raw_content.split("```json")[1].split("```")[0].strip()
            
            result = json.loads(raw_content)
            
            # Map back to standard fields for UI compatibility
            if result.get("classification_status") == "Sports":
                result["summary_bullets"] = result.get("key_facts", [])
                result["why_it_matters"] = f"Sports Type: {result.get('sports_type')}\n\n{result.get('why_it_matters')}"
                result["who_is_affected"] = f"Next Update: {result.get('next_update', 'TBD')}"
                result["impact_tags"] = [result.get("urgency_tag", "Regular Update")]
                result["category"] = "Sports"
                result["country"] = result.get("primary_geography", "Global")
            
            return result
        except Exception as e:
            logger.error(f"Sports analysis failed for '{title}': {e}")
            return self._mock_analysis(title)


    async def _analyze_single(self, article: Dict[str, str], client) -> Dict[str, Any]:
        title = article["title"]
        content = article.get("content", "")
        
        prompt = f"""
        Analyze the following news article:
        Title: {title}
        Content: {content[:3000]}

        TASK:
        Generate a JSON output with:
        PART 1: INDUSTRY INTELLIGENCE REPORT
        - regulatory_changes, market_impact_short, market_impact_long, competitors, strategic_signals, recommendations, confidence_level.
        
        PART 2: DASHBOARD METADATA
        - category, impact_score (1-10), sentiment, summary_bullets (5-7 points), bias_rating, primary_geography (e.g. India, USA, China, Japan, Global).
        
        Output ONLY valid JSON.
        """
        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a professional industry analyst. Output ONLY JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            raw_content = response.choices[0].message.content
            
            # Clean up markdown if present
            if "```json" in raw_content:
                raw_content = raw_content.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_content:
                raw_content = raw_content.split("```")[1].strip()
            else:
                raw_content = raw_content.strip()
            
            result = json.loads(raw_content)
            
            # Ensure mandatory fields for UI compatibility
            result["why_it_matters"] = f"Strategy: {result.get('strategic_signals', '')}\n\nPolicy: {result.get('regulatory_changes', '')}"
            result["who_is_affected"] = result.get('competitors', 'General Public')
            result["short_term_impact"] = result.get('market_impact_short', 'Immediate awareness.')
            result["long_term_impact"] = result.get('market_impact_long', 'Future policy shifts.')
            result["country"] = result.get('primary_geography', 'Global')
            
            return result
        except Exception as e:
            if "quota" in str(e).lower() or "429" in str(e):
                logger.info(f"OpenAI Quota reached. Using mock for: {title}")
            else:
                logger.error(f"Analysis failed for '{title}': {e}")
            return self._mock_analysis(title)

    async def analyze_premium_business(self, articles: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Specialized High-Impact Business Intelligence Report.
        Persona: Senior Business Intelligence Analyst
        """
        if not self.api_key:
            return [self._mock_premium_business(a["title"]) for a in articles]

        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=self.api_key)
        
        try:
            tasks = [self._analyze_premium_single(a, client) for a in articles]
            results = await asyncio.gather(*tasks)
            return results
        except Exception as e:
            logger.error(f"Premium analysis crash: {e}")
            return [self._mock_premium_business(a["title"]) for a in articles]
        finally:
            await client.close()

    async def _analyze_premium_single(self, article: Dict[str, str], client) -> Dict[str, Any]:
        title = article["title"]
        content = article.get("content", "")
        
        system_prompt = """
        You are a senior business intelligence analyst.
        Collect and analyze only HIGH-IMPACT news relevant to business decision-making.
        Ignore political drama, celebrity news, crime, and sensational headlines.

        Focus strictly on the following categories:

        1. Industry-Specific News
           - Regulations, policy changes
           - Competitor activities (funding, mergers, product launches)
           - Technology disruptions
           - Supply chain or pricing changes

        2. Market & Economic Signals
           - Interest rate changes (RBI / global)
           - Inflation, GDP, currency (USD-INR)
           - Stock market trends that affect businesses

        3. Government & Policy Updates (India-focused)
           - Budget announcements
           - Taxation (GST, income tax, customs)
           - MSME schemes, subsidies, incentives
           - State and central business policies

        4. Consumer & Market Trends
           - Shifts in customer behavior
           - Emerging demand patterns
           - Digital, AI, and regional market trends

        5. Global Events (Only if business-impacting)
           - Oil prices
           - Trade policies
           - Wars or conflicts affecting supply chains

        For each news item:
        - Provide a 2–3 line summary
        - Explain **business impact**
        - Mention **who is affected** (startups, MSMEs, enterprises, consumers)
        - Add a **risk or opportunity insight**

        Output format (JSON ONLY):
        {
            "category": "One of the 5 categories above",
            "headline": "Professional Headline",
            "summary": "2-3 line summary",
            "business_impact": "Explanation of impact",
            "actionable_insight": "Risk or opportunity",
            "who_is_affected": "Target audience",
            "primary_geography": "Primary country involved (e.g. India, China, Japan, Global)"
        }

        Language:
        - Simple, professional
        - Avoid jargon
        - Use Indian business context where applicable
        """
        
        prompt = f"""
        Analyze this article as a Senior Intelligence Analyst:
        Title: {title}
        Content: {content[:3000]}
        
        Output ONLY valid JSON matching the structure defined in the system prompt.
        """
        
        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )
            raw_content = response.choices[0].message.content
            if "```json" in raw_content:
                raw_content = raw_content.split("```json")[1].split("```")[0].strip()
            
            return json.loads(raw_content)
        except Exception as e:
            logger.error(f"Premium single analysis failed: {e}")
            return self._mock_premium_business(title)

    def _mock_premium_business(self, title: str) -> Dict[str, Any]:
        return {
            "category": "Market & Economic Signals",
            "headline": title,
            "summary": f"Strategic update on {title[:50]}. Market shifts indicate increasing volatility or opportunity.",
            "business_impact": "Affects MSMEs and startups through supply chain adjustments and capital flow shifts.",
            "actionable_insight": "Monitor regional policy changes for early-mover advantage."
        }

    def analyze_article(self, title: str, content: str) -> Dict[str, Any]:
        """Synchronous analysis fallback."""
        if not self.client:
            return self._mock_analysis(title)
        return self._mock_analysis(title) # Default to mock for sync to keep it simple and robust

    def get_completion(self, prompt: str) -> str:
        """Synchronous generation for internal tools like ExamGenerator."""
        if not self.client:
            raise Exception("OpenAI Client not initialized")
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM Completion failed: {e}")
            raise e

    def _mock_analysis(self, title: str) -> Dict[str, Any]:
        """High-quality keyword fallback."""
        title_lower = title.lower()
        category = "Other News"
        
        keywords = {
            "Technology": ["tech", "apple", "google", "microsoft", "cyber", "software", "app", "chip", "semiconductor"],
            "AI & Machine Learning": ["ai", "gpt", "llm", "intelligence", "neural", "robot", "deep learning"],
            "Sports": ["sport", "cricket", "football", "nba", "score", "cup", "match", "t20", "ipl", "tennis"],
            "Politics": ["election", "parliament", "senate", "minister", "president", "policy", "vote", "govt"],
            "Business & Economy": ["market", "stock", "economy", "trade", "bank", "finance", "ceo", "startup", "funding"],
            "World News": ["war", "un", "global", "china", "europe", "ukraine", "gaza", "russia", "israel", "nuclear"],
            "India / Local News": ["india", "delhi", "mumbai", "modi", "bjp", "bollywood", "indian"],
            "Science & Health": ["space", "nasa", "doctor", "virus", "cancer", "health", "discovery", "asteroid", "bennu", "mars", "medical"],
            "Education": ["school", "university", "student", "college", "exam", "learning", "degree"],
            "Entertainment": ["movie", "film", "star", "celebrity", "actor", "music", "award", "oscar"],
            "Environment & Climate": ["climate", "environment", "global warming", "sustainability", "emission", "green"],
            "Lifestyle & Wellness": ["travel", "wellness", "lifestyle", "fashion", "food", "health tips"],
            "Defense & Security": ["defense", "military", "security", "warfare", "pentagon", "nato", "army", "navy"]
        }
        
        for cat, keys in keywords.items():
            if any(k in title_lower for k in keys):
                category = cat
                break
                
        # Differentiate affected groups based on category
        affected_groups = {
            "Sports": "Athletes, Teams, Coaches, and Sports Fans",
            "Politics": "Government Officials, Policy Makers, and Citizens",
            "Technology": "Tech Developers, Industry Competitors, and Early Adopters",
            "Business & Economy": "Investors, Corporate Leaders, and Market Analysts",
            "Science & Health": "Scientific Researchers, Healthcare Professionals, and the Global Community",
            "World News": "Diplomats, Global Organizations, and Affected Communities",
            "Entertainment": "Media Producers, Fans, and Industry Stakeholders",
            "Environment & Climate": "Environmentalists, Policy Makers, and Future Generations",
            "Education": "Students, Educators, and Academic Institutions",
            "Defense & Security": "Military Personnel, Defense Analysts, and Security Experts"
        }
        who_is_affected = affected_groups.get(category, "General Public, Analysts, and Industry Observers")
        
        # Dynamic why it matters based on category type
        if category in ["Business & Economy", "Technology", "AI & Machine Learning"]:
            why_it_matters = f"The development of '{title[:60]}...' signals a major shift in {category} that could redefine current industry standards."
        elif category == "Sports":
            why_it_matters = f"This update on '{title[:60]}...' is critical for tournament standings and team strategic planning."
        elif category == "Politics":
            why_it_matters = f"The implications of '{title[:60]}...' are being closely watched by legislative bodies and international observers."
        elif category == "Science & Health":
            why_it_matters = f"This discovery concerning '{title[:60]}...' significantly advances our understanding of {category} and its future applications."
        elif category == "Environment & Climate":
            why_it_matters = f"The findings in '{title[:60]}...' highlight urgent environmental shifts and the necessity for sustainable policy changes."
        else:
             why_it_matters = f"This update regarding '{title[:60]}...' provides essential context for ongoing developments within the {category} sector."

        return {
            "summary_bullets": [
                f"Core development: {title[:80]}...",
                f"This update highlights a pivotal moment for {category} stakeholders.",
                "Observers are noting significant implications for future planning and policy.",
                f"Potential for extensive ripple effects across the {category} landscape.",
                "Long-term structural changes are anticipated as a result of this development."
            ],
            "category": category,
            "impact_score": 8,
            "impact_tags": [category, "Analytical Insight"],
            "bias_rating": "Neutral",
            "why_it_matters": why_it_matters,
            "who_is_affected": who_is_affected,
            "short_term_impact": f"Immediate tactical adjustments and heightened awareness in {category}.",
            "long_term_impact": f"Strategic re-alignment and fundamental shifts within the {category} ecosystem.",
            "sentiment": "Neutral"
        }
