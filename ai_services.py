# backend/ai_services.py

import os
import json
import hashlib
import logging
from typing import Optional, List, Dict
from openai import OpenAI, OpenAIError
import redis

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.client = OpenAI(api_key="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")
        self.redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        
        # Use cheaper models by default
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
        self.chat_model = os.getenv("CHAT_MODEL", "gpt-3.5-turbo")
        
        # Cache settings
        self.embedding_cache_ttl = 86400 * 30  # 30 days
        self.category_cache_ttl = 86400 * 7    # 7 days
        
        # Feature flags
        self.ai_enabled = os.getenv("AI_ENABLED", "true").lower() == "true"
        self.use_cache = os.getenv("USE_AI_CACHE", "true").lower() == "true"
    
    def get_cache_key(self, prefix: str, text: str) -> str:
        """Generate cache key from text"""
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return f"{prefix}:{text_hash}"
    
    async def generate_embedding_safe(self, text: str) -> Optional[List[float]]:
        """Generate embedding with caching and error handling"""
        if not self.ai_enabled:
            logger.info("AI features disabled, skipping embedding generation")
            return None
        
        if not text or not text.strip():
            return None
        
        # Check cache first
        if self.use_cache:
            cache_key = self.get_cache_key("embedding", text)
            try:
                cached = self.redis_client.get(cache_key)
                if cached:
                    logger.info("Using cached embedding")
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Cache read error: {e}")
        
        # Generate new embedding
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text[:8000]  # Limit input length
            )
            
            embedding = response.data[0].embedding
            
            # Cache the result
            if self.use_cache:
                try:
                    cache_key = self.get_cache_key("embedding", text)
                    self.redis_client.setex(
                        cache_key,
                        self.embedding_cache_ttl,
                        json.dumps(embedding)
                    )
                except Exception as e:
                    logger.warning(f"Cache write error: {e}")
            
            return embedding
            
        except OpenAIError as e:
            if "insufficient_quota" in str(e):
                logger.error("OpenAI quota exceeded - please check billing")
            else:
                logger.error(f"OpenAI API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating embedding: {e}")
            return None
    
    async def categorize_article_safe(self, article) -> Optional[Dict]:
        """Categorize article with caching and error handling"""
        if not self.ai_enabled:
            logger.info("AI features disabled, skipping categorization")
            return None
        
        # Check cache first
        if self.use_cache:
            cache_key = self.get_cache_key("category", article.title)
            try:
                cached = self.redis_client.get(cache_key)
                if cached:
                    logger.info("Using cached categories")
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Cache read error: {e}")
        
        try:
            # Simplified prompt to reduce tokens
            prompt = f"""Categorize this research article:
Title: {article.title}
Abstract: {article.abstract[:1000]}

Return JSON:
{{"primary_area": "...", "secondary_areas": ["...", "..."], "keywords": ["...", "..."]}}"""
            
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0
            )
            
            content = response.choices[0].message.content
            categories = json.loads(content)
            
            # Cache the result
            if self.use_cache:
                try:
                    cache_key = self.get_cache_key("category", article.title)
                    self.redis_client.setex(
                        cache_key,
                        self.category_cache_ttl,
                        json.dumps(categories)
                    )
                except Exception as e:
                    logger.warning(f"Cache write error: {e}")
            
            return categories
            
        except OpenAIError as e:
            if "insufficient_quota" in str(e):
                logger.error("OpenAI quota exceeded - please check billing")
            else:
                logger.error(f"OpenAI API error: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error categorizing article: {e}")
            return None
    
    async def summarize_article_safe(self, article) -> Optional[str]:
        """Generate article summary with error handling"""
        if not self.ai_enabled:
            # Return a basic summary without AI
            return f"{article.title}. {article.abstract[:200]}..."
        
        try:
            prompt = f"""Summarize this research article in less than 4 sentences for someone who is already medically knwoledgeable:
Title: {article.title}
Abstract: {article.abstract[:1500]}"""
            
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Failed to summarize article: {e}")
            # Fallback to first sentences of abstract
            return article.abstract[:200] + "..."

# Singleton instance
ai_service = AIService()