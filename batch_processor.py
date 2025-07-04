# backend/batch_processor.py

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session

from models import Article
from ai_services import ai_service
from rate_limiter import rate_limiter
from database import SessionLocal

logger = logging.getLogger(__name__)

class BatchProcessor:
    def __init__(self):
        self.batch_size = 10
        self.processing_interval = 300  # 5 minutes
        self.is_running = False
    
    async def start(self):
        """Start the batch processor"""
        if self.is_running:
            logger.warning("Batch processor already running")
            return
        
        self.is_running = True
        logger.info("Starting batch processor")
        
        while self.is_running:
            try:
                await self.process_batch()
            except Exception as e:
                logger.error(f"Batch processing error: {e}")
            
            await asyncio.sleep(self.processing_interval)
    
    async def stop(self):
        """Stop the batch processor"""
        logger.info("Stopping batch processor")
        self.is_running = False
    
    async def process_batch(self):
        """Process a batch of articles"""
        db = SessionLocal()
        try:
            # Get usage stats first
            stats = await rate_limiter.get_usage_stats()
            embeddings_remaining = stats.get('embeddings', {}).get('hour', {}).get('limit', 0) - \
                                 stats.get('embeddings', {}).get('hour', {}).get('used', 0)
            
            if embeddings_remaining < 10:
                logger.info(f"Low on embedding quota ({embeddings_remaining} remaining), skipping batch")
                return
            
            # Find articles without embeddings
            unprocessed = db.query(Article).filter(
                Article.embedding == None,
                Article.created_at > datetime.now() - timedelta(days=7)
            ).limit(self.batch_size).all()
            
            if not unprocessed:
                logger.info("No unprocessed articles found")
                return
            
            logger.info(f"Processing batch of {len(unprocessed)} articles")
            
            # Process articles with delay between each
            processed_count = 0
            for article in unprocessed:
                # Check rate limit for each article
                if not await rate_limiter.can_make_request('embeddings'):
                    logger.warning("Rate limit reached during batch processing")
                    break
                
                # Generate embedding
                text = f"{article.title} {article.abstract[:1000]}"
                embedding = await ai_service.generate_embedding_safe(text)
                
                if embedding:
                    article.embedding = embedding
                    db.commit()
                    processed_count += 1
                    logger.info(f"Processed article {article.id}: {article.title[:50]}...")
                
                # Small delay between requests
                await asyncio.sleep(0.5)
                
                # Also try to categorize if we have quota
                if not article.categories and await rate_limiter.can_make_request('completions'):
                    categories = await ai_service.categorize_article_safe(article)
                    if categories:
                        article.categories = categories
                        db.commit()
                    await asyncio.sleep(0.5)
            
            logger.info(f"Batch processing complete: {processed_count} articles processed")
            
        except Exception as e:
            logger.error(f"Error in batch processing: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def process_article_priority(self, article_id: int):
        """Process a specific article with priority"""
        db = SessionLocal()
        try:
            article = db.query(Article).filter(Article.id == article_id).first()
            if not article:
                logger.warning(f"Article {article_id} not found")
                return
            
            # Check if already processed
            if article.embedding and article.categories:
                logger.info(f"Article {article_id} already fully processed")
                return
            
            # Process with rate limit checking
            if not article.embedding and await rate_limiter.can_make_request('embeddings'):
                text = f"{article.title} {article.abstract[:1000]}"
                embedding = await ai_service.generate_embedding_safe(text)
                if embedding:
                    article.embedding = embedding
                    db.commit()
            
            if not article.categories and await rate_limiter.can_make_request('completions'):
                categories = await ai_service.categorize_article_safe(article)
                if categories:
                    article.categories = categories
                    db.commit()
            
        except Exception as e:
            logger.error(f"Error processing priority article {article_id}: {e}")
            db.rollback()
        finally:
            db.close()

# Singleton instance
batch_processor = BatchProcessor()

# Function to start batch processor in background
async def start_batch_processor():
    """Start the batch processor as a background task"""
    asyncio.create_task(batch_processor.start())
