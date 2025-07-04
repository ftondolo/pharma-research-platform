from fastapi import FastAPI, HTTPException, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
import logging
import rate_limiter
import batch_processor
from fastapi import FastAPI, Query, BackgroundTasks, HTTPException
from typing import Optional, List
import logging
from datetime import datetime

from database import get_db, init_db
from models import Article, ArticleCreate, ArticleResponse, SearchQuery, SearchResponse
from api_services import APIManager
from ai_services import AIService
from logging_config import setup_logging, APILogger

# Initialize logging
logger = setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database on startup
    init_db()
    yield

app = FastAPI(title="Pharmaceutical Research Platform", lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Error handling middleware
@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(f"Unhandled error: {str(e)}", extra={
            'path': request.url.path,
            'method': request.method,
            'error_type': type(e).__name__
        })
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)}
        )

# Request logging middleware
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    start_time = datetime.now()
    
    # Log request
    APILogger.log_request(
        f"{request.method} {request.url.path}",
        dict(request.query_params)
    )
    
    response = await call_next(request)
    
    # Log response
    process_time = (datetime.now() - start_time).total_seconds()
    APILogger.log_response(
        f"{request.method} {request.url.path}",
        response.status_code,
        response.headers.get("content-length", 0)
    )
    
    return response

# Initialize services
api_manager = APIManager()
ai_service = AIService()

@app.get("/")
async def root():
    return {"message": "Pharmaceutical Research Platform API"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """Detailed health check with dependencies"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "services": {}
    }
    
    # Check database
    try:
        db.execute("SELECT 1")
        health_status["services"]["database"] = "healthy"
    except Exception as e:
        health_status["services"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Check OpenAI API
    try:
        ai_service.client.models.list()
        health_status["services"]["openai"] = "healthy"
    except Exception as e:
        health_status["services"]["openai"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    return health_status

logger = logging.getLogger(__name__)

@app.post("/search")
async def search_articles(
    query: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=100),
    use_ai: bool = Query(False, description="Enable AI features (embeddings/categorization)"),
    background_tasks: BackgroundTasks = None
):
    """
    Search for articles across multiple sources.
    AI features are disabled by default to avoid quota issues.
    """
    try:
        logger.info(f"Search request: {query} (AI: {use_ai})")
        
        # Search external APIs
        articles = await api_manager.search_all(query, limit)
        logger.info(f"Found {len(articles)} articles from APIs")
        
        # Store articles WITHOUT AI processing
        stored_articles = []
        for article_data in articles:
            # Check if article already exists
            existing = db.query(Article).filter(
                Article.external_id == article_data['external_id'],
                Article.source == article_data['source']
            ).first()
            
            if existing:
                stored_articles.append(existing)
                continue
            
            # Create new article without AI fields
            article = Article(
                external_id=article_data['external_id'],
                title=article_data['title'],
                abstract=article_data.get('abstract', ''),
                authors=article_data.get('authors', []),
                published_date=article_data.get('published_date'),
                source=article_data['source'],
                url=article_data.get('url', ''),
                metadata=article_data.get('metadata', {}),
                # Skip AI fields
                embedding=None,
                categories=None,
                summary=None
            )
            
            db.add(article)
            stored_articles.append(article)
        
        db.commit()
        logger.info(f"Stored {len(stored_articles)} articles in database")
        
        # Queue AI processing only if requested
        if use_ai and background_tasks:
            for article in stored_articles:
                background_tasks.add_task(
                    process_article_ai_safe, 
                    article.id,
                    skip_if_processed=True
                )
            logger.info(f"Queued {len(stored_articles)} articles for AI processing")
        
        # Return articles immediately
        return {
            "articles": [
                {
                    "id": article.id,
                    "title": article.title,
                    "abstract": article.abstract[:500] + "..." if len(article.abstract) > 500 else article.abstract,
                    "authors": article.authors,
                    "published_date": article.published_date,
                    "source": article.source,
                    "url": article.url,
                    "has_ai_features": bool(article.embedding or article.categories),
                    "categories": article.categories,
                    "relevance_score": article.metadata.get('relevance_score', 1.0)
                }
                for article in stored_articles
            ],
            "total": len(stored_articles),
            "ai_processing": use_ai
        }
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_article_ai_safe(article_id: int, skip_if_processed: bool = True):
    """
    Process article with AI features, with proper error handling
    """
    try:
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            return
        
        # Skip if already processed
        if skip_if_processed and (article.embedding or article.categories):
            logger.info(f"Article {article_id} already processed, skipping")
            return
        
        # Check rate limits before making requests
        if not await rate_limiter.can_make_request('embeddings'):
            logger.warning(f"Rate limit reached for embeddings, skipping article {article_id}")
            return
        
        # Generate embedding with error handling
        if not article.embedding:
            try:
                embedding = await ai_service.generate_embedding_safe(
                    f"{article.title} {article.abstract[:1000]}"
                )
                if embedding:
                    article.embedding = embedding
                    db.commit()
                    logger.info(f"Generated embedding for article {article_id}")
            except Exception as e:
                logger.error(f"Failed to generate embedding for article {article_id}: {e}")
        
        # Generate categories with error handling
        if not article.categories and await rate_limiter.can_make_request('completions'):
            try:
                categories = await ai_service.categorize_article_safe(article)
                if categories:
                    article.categories = categories
                    db.commit()
                    logger.info(f"Generated categories for article {article_id}")
            except Exception as e:
                logger.error(f"Failed to categorize article {article_id}: {e}")
                
    except Exception as e:
        logger.error(f"Error processing article {article_id}: {e}")

@app.get("/articles/{article_id}")
async def get_article(article_id: str, db: Session = Depends(get_db)):
    """Get detailed article information"""
    try:
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        return article
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching article {article_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch article: {str(e)}")

@app.post("/articles/{article_id}/summarize")
async def summarize_article(article_id: str, db: Session = Depends(get_db)):
    """Generate AI summary of an article"""
    try:
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        summary = await ai_service.summarize_article(article.abstract)
        return {"summary": summary}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error summarizing article {article_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")

@app.get("/articles/{article_id}/similar")
async def get_similar_articles(
    article_id: str, 
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """Find similar articles using semantic search"""
    try:
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        if not article.embedding:
            return {"similar_articles": []}
        
        similar_articles = await ai_service.find_similar_articles(
            article.embedding, 
            db, 
            limit=limit,
            exclude_id=article_id
        )
        
        return {"similar_articles": similar_articles}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding similar articles for {article_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to find similar articles: {str(e)}")

@app.get("/trends")
async def get_trends(
    days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db)
):
    """Analyze trends in recent articles"""
    try:
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_articles = db.query(Article).filter(
            Article.publication_date >= cutoff_date
        ).all()
        
        if not recent_articles:
            return {"trends": [], "message": "No recent articles found"}
        
        trends = await ai_service.analyze_trends([
            article.abstract for article in recent_articles
        ])
        
        return {"trends": trends, "period_days": days}
        
    except Exception as e:
        logger.error(f"Error analyzing trends: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze trends: {str(e)}")

# Add these endpoints to backend/main.py

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "ai_enabled": ai_service.ai_enabled,
        "cache_enabled": ai_service.use_cache
    }

@app.get("/usage")
async def get_usage_stats():
    """Get API usage statistics"""
    stats = await rate_limiter.get_usage_stats()
    
    # Add database stats
    db_stats = {
        "total_articles": db.query(Article).count(),
        "articles_with_embeddings": db.query(Article).filter(Article.embedding != None).count(),
        "articles_with_categories": db.query(Article).filter(Article.categories != None).count(),
        "articles_last_24h": db.query(Article).filter(
            Article.created_at > datetime.now() - timedelta(days=1)
        ).count()
    }
    
    return {
        "api_usage": stats,
        "database": db_stats,
        "ai_status": {
            "enabled": ai_service.ai_enabled,
            "embedding_model": ai_service.embedding_model,
            "chat_model": ai_service.chat_model
        }
    }

@app.post("/admin/toggle-ai")
async def toggle_ai(enable: bool = False):
    """Toggle AI features on/off"""
    ai_service.ai_enabled = enable
    return {
        "ai_enabled": ai_service.ai_enabled,
        "message": f"AI features {'enabled' if enable else 'disabled'}"
    }

@app.post("/admin/process-batch")
async def trigger_batch_processing():
    """Manually trigger batch processing"""
    asyncio.create_task(batch_processor.process_batch())
    return {"message": "Batch processing started"}

@app.get("/articles/{article_id}/status")
async def get_article_processing_status(article_id: int):
    """Check processing status of a specific article"""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    return {
        "id": article.id,
        "title": article.title,
        "has_embedding": bool(article.embedding),
        "has_categories": bool(article.categories),
        "has_summary": bool(article.summary),
        "created_at": article.created_at,
        "processing_complete": bool(article.embedding and article.categories)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)