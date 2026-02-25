import logging
import random
import json
from typing import List, Dict, Any, Union
import openai
from src.config import settings

logger = logging.getLogger(__name__)

class NewsTranslator:
    def __init__(self):
        self.api_keys = settings.TRANSLATION_KEYS
        if not self.api_keys:
            logger.warning("No translation API keys found in settings.")

    def _get_client(self):
        if not self.api_keys:
            return None
        # Rotate keys randomly for simple load balancing/quota management
        key = random.choice(self.api_keys)
        return openai.OpenAI(api_key=key)

    def translate_text(self, text: str, target_lang: str) -> str:
        if not text or not target_lang or target_lang.lower() == 'english':
            return text
        
        client = self._get_client()
        if not client:
            return text

        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"You are a professional news translator. Translate the following news text into {target_lang}. Maintain the tone and nuances. Only return the translated text."},
                    {"role": "user", "content": text}
                ],
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Translation failed for '{text[:50]}...': {e}")
            return text

    def translate_stories(self, stories: List[Dict[str, Any]], target_lang: str) -> List[Dict[str, Any]]:
        if not stories or not target_lang or target_lang.lower() == 'english':
            return stories

        # Deep copy to avoid mutating original
        translated_stories = json.loads(json.dumps(stories))
        
        # Batching would be better, but for now simple loop
        # We only translate key fields to save on tokens/time
        for story in translated_stories:
            # Fields to translate
            fields = ['title', 'why', 'affected', 'headline']
            
            # For bullets, it's a list
            if 'bullets' in story and story['bullets']:
                story['bullets'] = [self.translate_text(b, target_lang) for b in story['bullets']]
            
            for field in fields:
                if field in story and story[field]:
                    story[field] = self.translate_text(story[field], target_lang)

        return translated_stories
