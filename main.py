from fastapi import FastAPI, HTTPException, Depends, Query, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import logging

from database import get_db, init_db
from models import Article, ArticleCreate, ArticleResponse, SearchQuery, SearchResponse
from api_services import APIManager
from ai_services import ai_service
from logging_config import setup_logging, APILogger

# Initialize logging
logger = setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database on startup
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    yield

app = FastAPI(title="Pharmaceutical Research Platform", lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
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
        int(response.headers.get("content-length", 0))
    )
    
    return response

# Initialize services
api_manager = APIManager()

@app.get("/")
async def root():
    return {"message": "Pharmaceutical Research Platform API"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "ai_enabled": ai_service.ai_enabled,
        "cache_enabled": ai_service.use_cache
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
        result = db.execute(text("SELECT 1")).fetchone()
        health_status["services"]["database"] = "healthy"
    except Exception as e:
        health_status["services"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Check OpenAI API (if enabled)
    if ai_service.ai_enabled:
        try:
            # Simple check without making actual API call
            health_status["services"]["openai"] = "configured"
        except Exception as e:
            health_status["services"]["openai"] = f"issue: {str(e)}"
            health_status["status"] = "degraded"
    else:
        health_status["services"]["openai"] = "disabled"
    
    return health_status

@app.post("/search")
async def search_articles(
    search_query: SearchQuery,
    require_abstract: bool = Query(False, description="Debug: Only show articles with abstracts"),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """
    Search for articles across multiple sources.
    AI features are disabled by default to avoid quota issues.
    """
    try:
        logger.info(f"Search request: {search_query.query} (require_abstract: {require_abstract}, limit: {search_query.limit})")
        
        # If filtering by abstract, we might need to fetch more articles
        # to reach the desired count after filtering
        target_count = search_query.limit
        fetch_multiplier = 2 if require_abstract else 1  # Fetch 2x if filtering
        max_fetch_limit = min(search_query.limit * 3, 100)  # Cap at 100 total
        
        # Search external APIs with higher limit if filtering
        initial_fetch_count = min(search_query.limit * fetch_multiplier, max_fetch_limit)
        articles = await api_manager.search_all(search_query.query, initial_fetch_count)
        logger.info(f"Found {len(articles)} articles from APIs")
        
        # Store and filter articles
        stored_articles = []
        filtered_count = 0
        total_processed = 0
        
        for article_data in articles:
            total_processed += 1
            
            # Debug filter: Skip articles without abstracts if flag is enabled
            if require_abstract:
                if not article_data.abstract or article_data.abstract.strip() in [
                    "", "No abstract available.", "Abstract not available", "N/A"
                ]:
                    filtered_count += 1
                    logger.debug(f"Filtered out article without abstract: {article_data.title[:50]}...")
                    continue
            
            # Check if article already exists by DOI or external ID
            existing = None
            if article_data.doi:
                existing = db.query(Article).filter(Article.doi == article_data.doi).first()
            
            if existing:
                # Apply abstract filter to existing articles too
                if require_abstract and (not existing.abstract or existing.abstract.strip() in [
                    "", "No abstract available.", "Abstract not available", "N/A"
                ]):
                    filtered_count += 1
                    continue
                stored_articles.append(existing)
            else:
                # Create new article without AI fields
                article = Article(
                    doi=article_data.doi,
                    title=article_data.title,
                    abstract=article_data.abstract,
                    authors=article_data.authors,
                    publication_date=article_data.publication_date,
                    journal=article_data.journal,
                    url=article_data.url,
                    # Skip AI fields for now
                    embedding=None,
                    categories=None
                )
                
                db.add(article)
                stored_articles.append(article)
            
            # Stop if we have enough articles
            if len(stored_articles) >= target_count:
                break
        
        # If we still don't have enough articles and filtering is enabled,
        # try to fetch more (up to our max limit)
        if len(stored_articles) < target_count and require_abstract and total_processed < max_fetch_limit:
            additional_needed = min(target_count - len(stored_articles), max_fetch_limit - total_processed)
            if additional_needed > 0:
                logger.info(f"Fetching {additional_needed} more articles to reach target of {target_count}")
                
                # Try to get more articles with a different search approach
                # Since most APIs don't support true offset, we'll fetch more and deduplicate
                additional_articles = await api_manager.search_all(
                    search_query.query, 
                    additional_needed + filtered_count,  # Account for expected filtering
                    offset=0  # Start from beginning but we'll deduplicate
                )
                
                # Filter out articles we already have
                existing_titles = {(article.title or "").lower().strip() for article in stored_articles}
                existing_dois = {article.doi for article in stored_articles if hasattr(article, 'doi') and article.doi}
                
                for article_data in additional_articles:
                    # Skip if we already have this article
                    if (article_data.doi and article_data.doi in existing_dois):
                        continue
                    if ((article_data.title or "").lower().strip() in existing_titles):
                        continue
                        
                    total_processed += 1
                    
                    if require_abstract:
                        if not article_data.abstract or article_data.abstract.strip() in [
                            "", "No abstract available.", "Abstract not available", "N/A"
                        ]:
                            filtered_count += 1
                            continue
                    
                    # Check for existing in database and add new ones
                    existing = None
                    if article_data.doi:
                        existing = db.query(Article).filter(Article.doi == article_data.doi).first()
                    
                    if existing:
                        if require_abstract and (not existing.abstract or existing.abstract.strip() in [
                            "", "No abstract available.", "Abstract not available", "N/A"
                        ]):
                            filtered_count += 1
                            continue
                        stored_articles.append(existing)
                    else:
                        article = Article(
                            doi=article_data.doi,
                            title=article_data.title,
                            abstract=article_data.abstract,
                            authors=article_data.authors,
                            publication_date=article_data.publication_date,
                            journal=article_data.journal,
                            url=article_data.url,
                            embedding=None,
                            categories=None
                        )
                        db.add(article)
                        stored_articles.append(article)
                    
                    if len(stored_articles) >= target_count:
                        break
        
        try:
            db.commit()
            logger.info(f"Stored {len(stored_articles)} articles in database")
            if filtered_count > 0:
                logger.info(f"Filtered out {filtered_count} articles without abstracts")
        except Exception as e:
            logger.error(f"Database commit error: {e}")
            db.rollback()
        
        # Limit results to requested count
        final_articles = stored_articles[:target_count]
        
        # Return articles with proper pagination info
        return SearchResponse(
            articles=[
                ArticleResponse(
                    id=str(article.id),
                    doi=article.doi,
                    title=article.title,
                    abstract=article.abstract[:500] + "..." if article.abstract and len(article.abstract) > 500 else article.abstract or "",
                    authors=article.authors or [],
                    publication_date=article.publication_date,
                    journal=article.journal,
                    url=article.url,
                    categories=article.categories or [],
                    created_at=article.created_at
                )
                for article in final_articles
            ],
            total=len(final_articles),
            # Add metadata about the search
            metadata={
                "requested_count": search_query.limit,
                "delivered_count": len(final_articles),
                "total_fetched": total_processed,
                "filtered_count": filtered_count,
                "require_abstract": require_abstract,
                "search_complete": len(final_articles) >= target_count or total_processed >= max_fetch_limit
            }
        )
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/articles/{article_id}")
async def get_article(article_id: str, db: Session = Depends(get_db)):
    """Get detailed article information"""
    try:
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        return ArticleResponse(
            id=str(article.id),
            doi=article.doi,
            title=article.title,
            abstract=article.abstract or "",
            authors=article.authors or [],
            publication_date=article.publication_date,
            journal=article.journal,
            url=article.url,
            categories=article.categories or [],
            embedding=article.embedding,
            created_at=article.created_at
        )
        
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
        
        summary = await ai_service.summarize_article_safe(article)
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
    require_abstract: bool = Query(True, description="Debug: Only include articles with abstracts"),
    db: Session = Depends(get_db)
):
    """Find similar articles using semantic search or basic similarity"""
    try:
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        similar_articles = []
        
        # Build base query to exclude current article
        base_query = db.query(Article).filter(
            Article.id != article_id,
            Article.title != article.title  # Also exclude by title to catch duplicates
        )
        
        # Debug flag: Filter out articles without abstracts
        if require_abstract:
            base_query = base_query.filter(
                Article.abstract != None,
                Article.abstract != "",
                Article.abstract != "No abstract available.",
                Article.abstract != "Abstract not available"
            )
        
        all_articles = base_query.limit(100).all()  # Get more for better filtering
        
        if not all_articles:
            message = "No other articles with abstracts found" if require_abstract else "No other articles in database yet"
            return {
                "similar_articles": [{
                    "id": "sample-1",
                    "title": f"{message} - search for more articles first",
                    "journal": "System Message",
                    "authors": [],
                    "similarity": 0.0,
                    "url": "#"
                }],
                "method": "no_data",
                "total_found": 0,
                "debug_info": {
                    "require_abstract_enabled": require_abstract,
                    "total_articles_in_db": db.query(Article).count()
                }
            }
        
        # Prepare current article data for comparison
        current_title_words = set((article.title or "").lower().split()) if article.title else set()
        current_journal = (article.journal or "").lower().strip()
        current_authors = set(article.authors) if article.authors else set()
        
        scored_articles = []
        seen_titles = set()  # Deduplication
        
        for other_article in all_articles:
            # Skip if we've seen this title before (deduplication)
            other_title_lower = (other_article.title or "").lower().strip()
            if other_title_lower in seen_titles or not other_title_lower:
                continue
            seen_titles.add(other_title_lower)
            
            # Skip if it's too similar to current article (likely duplicate)
            if other_title_lower == (article.title or "").lower().strip():
                continue
                
            score = 0
            other_title_words = set(other_title_lower.split())
            
            # Calculate similarity
            if current_title_words and other_title_words:
                # Jaccard similarity for title words
                intersection = current_title_words.intersection(other_title_words)
                union = current_title_words.union(other_title_words)
                if union:
                    word_similarity = len(intersection) / len(union)
                    score += word_similarity * 0.6  # Max 0.6 from title
            
            # Bonus for same journal (but not too much)
            if current_journal and other_article.journal:
                other_journal = other_article.journal.lower().strip()
                if current_journal == other_journal:
                    score += 0.2
            
            # Bonus for shared authors (but limit it)
            if current_authors and other_article.authors:
                other_authors = set(other_article.authors)
                shared_authors = current_authors.intersection(other_authors)
                if shared_authors:
                    author_bonus = min(len(shared_authors) * 0.1, 0.3)  # Max 0.3
                    score += author_bonus
            
            # Only include if there's meaningful similarity (but not too high)
            if 0.15 < score < 0.95:  # Avoid perfect matches and very low matches
                scored_articles.append({
                    "article": other_article,
                    "similarity": score
                })
        
        # Sort by similarity and take top results
        scored_articles.sort(key=lambda x: x["similarity"], reverse=True)
        
        # Build response
        for item in scored_articles[:limit]:
            similar_articles.append({
                "id": str(item["article"].id),
                "title": item["article"].title,
                "journal": item["article"].journal or "Unknown Journal",
                "authors": (item["article"].authors or [])[:3],  # Limit to 3 authors
                "similarity": round(item["similarity"], 3),  # Round to 3 decimal places
                "url": item["article"].url or "#"
            })
        
        # If still no results, provide helpful message
        if not similar_articles:
            similar_articles = [{
                "id": "no-results",
                "title": f"No similar articles found for '{(article.title or 'this article')[:50]}...'",
                "journal": "Search for more articles to improve recommendations",
                "authors": [],
                "similarity": 0.0,
                "url": "#"
            }]
        
        return {
            "similar_articles": similar_articles,
            "method": "text_similarity",
            "total_found": len(similar_articles),
            "debug_info": {
                "total_articles_checked": len(all_articles),
                "articles_after_filtering": len(scored_articles),
                "require_abstract_enabled": require_abstract
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding similar articles for {article_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to find similar articles: {str(e)}")

@app.get("/trends")
async def get_trends(days: int = Query(30, ge=1, le=90)):
    """Fast trends endpoint with sample data"""
    try:
        # Return immediate sample data - no database queries
        trends = {
            "frequent_topics": [
                "Cancer Research", "Drug Discovery", "Clinical Trials", 
                "Immunotherapy", "Gene Therapy"
            ],
            "emerging_themes": [
                "AI in Drug Discovery", "Personalized Medicine", "Digital Health",
                "CRISPR Applications", "Biomarker Research"
            ],
            "notable_shifts": [
                "Remote Clinical Trials", "Digital Therapeutics", 
                "Patient-Centric Design", "Real-World Evidence"
            ]
        }
        
        return {
            "trends": trends, 
            "period_days": days,
            "message": "Sample trends data - search for articles to see real trends"
        }
        
    except Exception as e:
        logger.error(f"Error in trends endpoint: {str(e)}")
        # Ultra-simple fallback
        return {
            "trends": {
                "frequent_topics": ["Oncology", "Immunology"],
                "emerging_themes": ["Digital Health"],
                "notable_shifts": ["AI Integration"]
            }
        }

@app.get("/usage")
async def get_usage_stats(db: Session = Depends(get_db)):
    """Get API usage statistics"""
    try:
        # Database stats
        db_stats = {
            "total_articles": db.query(Article).count(),
            "articles_with_embeddings": db.query(Article).filter(Article.embedding != None).count(),
            "articles_with_categories": db.query(Article).filter(Article.categories != None).count(),
            "articles_last_24h": db.query(Article).filter(
                Article.created_at > datetime.now() - timedelta(days=1)
            ).count()
        }
        
        return {
            "database": db_stats,
            "ai_status": {
                "enabled": ai_service.ai_enabled,
                "embedding_model": ai_service.embedding_model,
                "chat_model": ai_service.chat_model
            }
        }
    except Exception as e:
        logger.error(f"Error getting usage stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)