# agrisense/services/libretranslate.py
import requests
from functools import lru_cache
import time

class LibreTranslateService:
    """Free LibreTranslate API - No API Key Required"""
    
    # Public LibreTranslate endpoints (multiple for redundancy)
    ENDPOINTS = [
        "https://libretranslate.com/translate",
        "https://translate.astian.org/translate",
        "https://libretranslate.de/translate",
        "https://translate.argosopdracht.nl/translate"
    ]
    
    @classmethod
    @lru_cache(maxsize=500)
    def translate(cls, text, target_lang='ur', source_lang='en'):
        """
        Translate text using LibreTranslate
        Cached to avoid repeated API calls
        """
        if not text or text.strip() == '':
            return text
        
        if source_lang == target_lang:
            return text
        
        # Limit text length for performance
        if len(text) > 2000:
            text = text[:2000] + "..."
        
        payload = {
            "q": text,
            "source": source_lang,
            "target": target_lang,
            "format": "text"
        }
        
        headers = {"Content-Type": "application/json"}
        
        # Try each endpoint until one works
        for endpoint in cls.ENDPOINTS:
            try:
                response = requests.post(
                    endpoint, 
                    json=payload, 
                    headers=headers, 
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get("translatedText", text)
                    
            except Exception as e:
                print(f"LibreTranslate error on {endpoint}: {e}")
                continue
        
        # If all endpoints fail, return original text
        return text
    
    @classmethod
    def translate_batch(cls, texts, target_lang='ur'):
        """
        Translate multiple texts
        """
        results = []
        for text in texts:
            translated = cls.translate(text, target_lang)
            results.append(translated)
            time.sleep(0.1)  # Small delay to avoid rate limiting
        return results
    
    @classmethod
    def get_supported_languages(cls):
        """Get list of supported languages"""
        try:
            response = requests.get("https://libretranslate.com/languages", timeout=5)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return [
            {"code": "en", "name": "English"},
            {"code": "ur", "name": "Urdu"},
            {"code": "hi", "name": "Hindi"}
        ]