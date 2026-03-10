import os
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
        self.cache_file = "translation_cache.json"
        self._load_cache()
        if not self.api_keys:
            logger.warning("No translation API keys found in settings.")

    def _load_cache(self):
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
            else:
                self.cache = {}
        except Exception as e:
            logger.error(f"Failed to load translation cache: {e}")
            self.cache = {}

    def _save_cache(self):
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save translation cache: {e}")

    def _get_client(self):
        if not self.api_keys:
            return None
        # Rotate keys randomly for simple load balancing/quota management
        key = random.choice(self.api_keys)
        return openai.OpenAI(api_key=key)

    def translate_text(self, text: str, target_lang: str) -> str:
        if not text or not target_lang or target_lang.lower() == 'english':
            return text
        
        # Check cache
        cache_key = f"{target_lang}:{text}"
        if cache_key in self.cache:
            return self.cache[cache_key]

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
            result = response.choices[0].message.content.strip()
            self.cache[cache_key] = result
            self._save_cache()
            return result
        except Exception as e:
            logger.error(f"Translation failed for '{text[:50]}...': {e}")
            return text

    def translate_stories(self, stories: List[Dict[str, Any]], target_lang: str) -> List[Dict[str, Any]]:
        if not stories or not target_lang or target_lang.lower() == 'english':
            return stories

        # Deep copy to avoid mutating original
        translated_stories = json.loads(json.dumps(stories))
        
        # Collect all unique texts that need translation and are NOT in cache
        texts_to_translate = []
        mapping = [] # (story_index, field_name, list_index)

        for i, story in enumerate(translated_stories):
            # Normal fields
            for field in ['title', 'why', 'affected', 'headline']:
                val = story.get(field)
                if val:
                    cache_key = f"{target_lang}:{val}"
                    if cache_key in self.cache:
                        story[field] = self.cache[cache_key]
                    else:
                        texts_to_translate.append(val)
                        mapping.append((i, field, None))
            
            # Bullet points
            if 'bullets' in story and story['bullets']:
                for idx, b in enumerate(story['bullets']):
                    if b:
                        cache_key = f"{target_lang}:{b}"
                        if cache_key in self.cache:
                            story['bullets'][idx] = self.cache[cache_key]
                        else:
                            texts_to_translate.append(b)
                            mapping.append((i, 'bullets', idx))

        if not texts_to_translate:
            return translated_stories

        # Batch translate
        client = self._get_client()
        if not client: return translated_stories

        try:
            prompt = f"Translate the following list of news snippets into {target_lang}. Return the translations as a JSON array of strings in the exact same order. Do not include any other text.\n\n"
            prompt += json.dumps(texts_to_translate, ensure_ascii=False)

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a batch translator. Always return a JSON object with a 'translations' key containing a list of strings."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )
            
            raw_content = response.choices[0].message.content.strip()
            if "```json" in raw_content:
                raw_content = raw_content.split("```json")[1].split("```")[0].strip()
            
            data = json.loads(raw_content)
            results = data.get("translations", [])

            if len(results) == len(texts_to_translate):
                for idx, translated_val in enumerate(results):
                    s_idx, field, b_idx = mapping[idx]
                    orig_val = texts_to_translate[idx]
                    
                    if field == 'bullets':
                        translated_stories[s_idx]['bullets'][b_idx] = translated_val
                    else:
                        translated_stories[s_idx][field] = translated_val
                    
                    self.cache[f"{target_lang}:{orig_val}"] = translated_val
                
                self._save_cache()
            else:
                logger.error(f"Batch translation count mismatch: {len(results)} vs {len(texts_to_translate)}")
                for i, text in enumerate(texts_to_translate):
                    translated_val = self.translate_text(text, target_lang)
                    s_idx, field, b_idx = mapping[i]
                    if field == 'bullets':
                        translated_stories[s_idx]['bullets'][b_idx] = translated_val
                    else:
                        translated_stories[s_idx][field] = translated_val
                
        except Exception as e:
            logger.error(f"Batch translation failed: {e}")
            for i, text in enumerate(texts_to_translate):
                translated_val = self.translate_text(text, target_lang)
                s_idx, field, b_idx = mapping[i]
                if field == 'bullets':
                    translated_stories[s_idx]['bullets'][b_idx] = translated_val
                else:
                    translated_stories[s_idx][field] = translated_val

        return translated_stories
