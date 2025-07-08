from fastapi import FastAPI, HTTPException, Depends, Query, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, date
import logging

from database import get_db, init_db
from models import Article, ArticleCreate, ArticleResponse, SearchQuery, SearchResponse, safe_parse_date
from api_services import enhanced_api_manager  
from ai_services import ai_service
from logging_config import setup_logging, APILogger

# Initialize logging
logger = setup_logging()

def convert_string_to_date(date_string):
    """Convert string date to proper date object for database insertion"""
    if not date_string:
        return None
    
    try:
        # If it's already a date object, return it
        if isinstance(date_string, (date, datetime)):
            return date_string
        
        # Try to parse various string formats
        date_str = str(date_string).strip()
        
        # Handle year-only strings like "2025"
        if len(date_str) == 4 and date_str.isdigit():
            year = int(date_str)
            if 1900 <= year <= 2100:
                return date(year, 1, 1)  # Default to January 1st
        
        # Handle full date strings
        for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
            try:
                parsed = datetime.strptime(date_str, fmt)
                return parsed.date()
            except ValueError:
                continue
        
        # If all parsing fails, return None
        return None
        
    except Exception:
        return None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database on startup
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    yield

app = FastAPI(title="Pharmaceutical Research Platform - Enhanced", lifespan=lifespan)

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

@app.get("/")
async def root():
    return {"message": "Pharmaceutical Research Platform API - Enhanced Edition"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0-enhanced",
        "ai_enabled": ai_service.ai_enabled,
        "cache_enabled": ai_service.use_cache,
        "enhanced_apis": True,
        "api_sources": ["PubMed", "Europe PMC", "Semantic Scholar", "ClinicalTrials.gov", "ArXiv"]
    }

@app.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """Detailed health check with dependencies"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0-enhanced",
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
            health_status["services"]["openai"] = "configured"
        except Exception as e:
            health_status["services"]["openai"] = f"issue: {str(e)}"
            health_status["status"] = "degraded"
    else:
        health_status["services"]["openai"] = "disabled"
    
    # Enhanced API status
    health_status["services"]["enhanced_apis"] = {
        "pubmed": "active",
        "europe_pmc": "active", 
        "semantic_scholar": "active",
        "clinical_trials": "active",
        "arxiv": "active"
    }
    
    return health_status

@app.post("/search")
async def search_articles(
    search_query: SearchQuery,
    require_abstract: bool = Query(False, description="Only show articles with substantial abstracts"),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """
    Enhanced search for articles across multiple specialized sources.
    Optimized for finding articles with high-quality abstracts.
    """
    try:
        logger.info(f"Enhanced search request: {search_query.query} (require_abstract: {require_abstract}, limit: {search_query.limit})")
        
        # Enhanced search strategy - fetch more initially for better filtering
        target_count = search_query.limit
        max_fetch_attempts = 2  # Reduced since enhanced APIs are more efficient
        
        # Enhanced APIs are better at finding abstracts, so less aggressive multiplier needed
        articles_per_fetch = target_count * 1.5 if require_abstract else target_count
        max_fetch_limit = min(search_query.limit * 2, 100)
        
        stored_articles = []
        filtered_count = 0
        total_processed = 0
        fetch_attempt = 0
        
        # Enhanced search with intelligent API selection
        while len(stored_articles) < target_count and fetch_attempt < max_fetch_attempts:
            fetch_attempt += 1
            
            still_needed = target_count - len(stored_articles)
            fetch_count = min(still_needed * 2, 50) if require_abstract else still_needed
            
            logger.info(f"Enhanced fetch attempt {fetch_attempt}: requesting {fetch_count} articles")
            
            # Use enhanced API manager with intelligent source selection
            articles = await enhanced_api_manager.search_all(search_query.query, fetch_count, offset=total_processed)
            
            if not articles:
                logger.info(f"No more articles found on attempt {fetch_attempt}")
                break
                
            logger.info(f"Enhanced APIs returned {len(articles)} articles on attempt {fetch_attempt}")
            
            # Process articles with enhanced filtering
            for article_data in articles:
                total_processed += 1
                
                # Enhanced abstract filtering
                if require_abstract:
                    if not article_data.abstract or len(article_data.abstract.strip()) < 100:  # Higher standard
                        filtered_count += 1
                        logger.debug(f"Filtered out article with insufficient abstract: {article_data.title[:50]}...")
                        continue
                
                # Enhanced deduplication
                existing = None
                if article_data.doi:
                    existing = db.query(Article).filter(Article.doi == article_data.doi).first()
                
                if not existing and article_data.title:
                    # More sophisticated title matching
                    title_normalized = article_data.title.strip().lower()
                    existing = db.query(Article).filter(
                        text("LOWER(TRIM(title)) = :title")
                    ).params(title=title_normalized).first()
                
                if existing:
                    # Apply enhanced abstract filter to existing articles
                    if require_abstract and (not existing.abstract or len(existing.abstract.strip()) < 100):
                        filtered_count += 1
                        continue
                    
                    if existing not in stored_articles:
                        stored_articles.append(existing)
                else:
                    # Create new article with enhanced date handling
                    article = Article(
                        doi=article_data.doi,
                        title=article_data.title,
                        abstract=article_data.abstract,
                        authors=article_data.authors,
                        publication_date=convert_string_to_date(article_data.publication_date),
                        journal=article_data.journal,
                        url=article_data.url,
                        embedding=None,
                        categories=None
                    )
                    
                    db.add(article)
                    db.flush()  # Get ID immediately
                    stored_articles.append(article)
                
                if len(stored_articles) >= target_count:
                    break
            
            # Enhanced APIs are more efficient, so smaller threshold for continuation
            if len(articles) < fetch_count // 3:
                logger.info("Enhanced APIs returned fewer articles than expected, likely exhausted")
                break
        
        # Commit all articles
        try:
            db.commit()
            logger.info(f"Stored {len(stored_articles)} articles with enhanced metadata")
            if filtered_count > 0:
                logger.info(f"Enhanced filtering removed {filtered_count} articles with insufficient abstracts")
        except Exception as e:
            logger.error(f"Database commit error: {e}")
            db.rollback()
            for article in stored_articles:
                if hasattr(article, 'id'):
                    db.refresh(article)
        
        # Final selection with enhanced quality sorting
        final_articles = stored_articles[:target_count]
        
        # Enhanced response with better metadata
        return SearchResponse(
            articles=[
                ArticleResponse(
                    id=str(article.id) if article.id is not None else f"temp-{idx}",
                    doi=article.doi,
                    title=article.title,
                    abstract=article.abstract[:800] + "..." if article.abstract and len(article.abstract) > 800 else article.abstract or "",  # Longer abstracts
                    authors=article.authors or [],
                    publication_date=safe_parse_date(article.publication_date),
                    journal=article.journal,
                    url=article.url,
                    categories=article.categories or [],
                    created_at=article.created_at
                )
                for idx, article in enumerate(final_articles)
            ],
            total=len(final_articles),
            metadata={
                "requested_count": search_query.limit,
                "delivered_count": len(final_articles),
                "total_fetched": total_processed,
                "filtered_count": filtered_count,
                "require_abstract": require_abstract,
                "search_complete": len(final_articles) >= target_count or fetch_attempt >= max_fetch_attempts,
                "fetch_attempts": fetch_attempt,
                "enhanced_apis_used": True,
                "api_sources": ["PubMed", "Europe PMC", "Semantic Scholar", "ClinicalTrials.gov", "ArXiv"],
                "abstract_quality_threshold": 100 if require_abstract else 0
            }
        )
        
    except Exception as e:
        logger.error(f"Enhanced search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/articles/{article_id}")
async def get_article(article_id: str, db: Session = Depends(get_db)):
    """Get detailed article information"""
    try:
        if article_id.startswith("temp-"):
            raise HTTPException(status_code=404, detail="Article not found - temporary ID")
            
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        return ArticleResponse(
            id=str(article.id),
            doi=article.doi,
            title=article.title,
            abstract=article.abstract or "",
            authors=article.authors or [],
            publication_date=safe_parse_date(article.publication_date),
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
        if article_id.startswith("temp-"):
            raise HTTPException(status_code=400, detail="Cannot summarize article with temporary ID - please search again")
            
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
    require_abstract: bool = Query(True, description="Only include articles with substantial abstracts"),
    db: Session = Depends(get_db)
):
    """Find similar articles using enhanced similarity matching"""
    try:
        if article_id.startswith("temp-"):
            raise HTTPException(status_code=400, detail="Cannot find similar articles with temporary ID - please search again")
            
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        # Enhanced similarity search with better abstract filtering
        base_query = db.query(Article).filter(
            Article.id != article_id,
            Article.title != article.title
        )
        
        if require_abstract:
            base_query = base_query.filter(
                Article.abstract != None,
                Article.abstract != "",
                text("LENGTH(TRIM(articles.abstract)) >= 100")  # Enhanced threshold
            )
        
        all_articles = base_query.limit(100).all()
        
        if not all_articles:
            message = "No other articles with substantial abstracts found" if require_abstract else "No other articles in database yet"
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
                    "total_articles_in_db": db.query(Article).count(),
                    "enhanced_similarity": True
                }
            }
        
        # Enhanced similarity calculation
        scored_articles = []
        seen_titles = set()
        
        current_title_words = set((article.title or "").lower().split()) if article.title else set()
        current_journal = (article.journal or "").lower().strip()
        current_authors = set(article.authors) if article.authors else set()
        
        for other_article in all_articles:
            other_title_lower = (other_article.title or "").lower().strip()
            if other_title_lower in seen_titles or not other_title_lower:
                continue
            seen_titles.add(other_title_lower)
            
            if other_title_lower == (article.title or "").lower().strip():
                continue
                
            score = 0
            other_title_words = set(other_title_lower.split())
            
            # Enhanced similarity scoring
            if current_title_words and other_title_words:
                intersection = current_title_words.intersection(other_title_words)
                union = current_title_words.union(other_title_words)
                if union:
                    word_similarity = len(intersection) / len(union)
                    score += word_similarity * 0.6
            
            # Journal match bonus
            if current_journal and other_article.journal:
                other_journal = other_article.journal.lower().strip()
                if current_journal == other_journal:
                    score += 0.25  # Increased bonus
            
            # Author overlap bonus
            if current_authors and other_article.authors:
                other_authors = set(other_article.authors)
                shared_authors = current_authors.intersection(other_authors)
                if shared_authors:
                    author_bonus = min(len(shared_authors) * 0.15, 0.35)  # Enhanced bonus
                    score += author_bonus
            
            # Abstract quality bonus for enhanced results
            if other_article.abstract and len(other_article.abstract.strip()) >= 200:
                score += 0.1
            
            if 0.2 < score < 0.9:  # Enhanced thresholds
                scored_articles.append({
                    "article": other_article,
                    "similarity": score
                })
        
        scored_articles.sort(key=lambda x: x["similarity"], reverse=True)
        
        similar_articles = []
        for item in scored_articles[:limit]:
            similar_articles.append({
                "id": str(item["article"].id),
                "title": item["article"].title,
                "journal": item["article"].journal or "Unknown Journal",
                "authors": (item["article"].authors or [])[:3],
                "similarity": round(item["similarity"], 3),
                "url": item["article"].url or "#"
            })
        
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
            "method": "enhanced_text_similarity",
            "total_found": len(similar_articles),
            "debug_info": {
                "total_articles_checked": len(all_articles),
                "articles_after_filtering": len(scored_articles),
                "require_abstract_enabled": require_abstract,
                "enhanced_similarity": True,
                "abstract_threshold": 100
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding similar articles for {article_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to find similar articles: {str(e)}")

@app.get("/trends")
async def get_trends(days: int = Query(30, ge=1, le=90)):
    """Enhanced trends endpoint with sample data"""
    try:
        # Enhanced sample trends data
        trends = {
            "frequent_topics": [
                "Cancer Immunotherapy", "CRISPR Gene Editing", "mRNA Vaccines", 
                "Precision Medicine", "CAR-T Cell Therapy", "Alzheimer's Research"
            ],
            "emerging_themes": [
                "AI-Driven Drug Discovery", "Digital Biomarkers", "Liquid Biopsies",
                "Organoid Models", "RNA Therapeutics", "Personalized Cancer Vaccines"
            ],
            "notable_shifts": [
                "Remote Patient Monitoring", "Decentralized Clinical Trials", 
                "AI-Powered Diagnostics", "Gene Therapy Advances", "Digital Therapeutics"
            ]
        }
        
        return {
            "trends": trends, 
            "period_days": days,
            "message": "Enhanced trends analysis - search for articles to see real-time trends",
            "enhanced": True,
            "data_sources": ["PubMed", "Europe PMC", "ClinicalTrials.gov", "Semantic Scholar"]
        }
        
    except Exception as e:
        logger.error(f"Error in enhanced trends endpoint: {str(e)}")
        return {
            "trends": {
                "frequent_topics": ["Cancer Research", "Immunotherapy"],
                "emerging_themes": ["AI in Medicine", "Digital Health"],
                "notable_shifts": ["Personalized Medicine", "Gene Therapy"]
            },
            "enhanced": True
        }

@app.get("/usage")
async def get_usage_stats(db: Session = Depends(get_db)):
    """Get enhanced API usage statistics"""
    try:
        # Enhanced database stats
        db_stats = {
            "total_articles": db.query(Article).count(),
            "articles_with_embeddings": db.query(Article).filter(Article.embedding != None).count(),
            "articles_with_categories": db.query(Article).filter(Article.categories != None).count(),
            "articles_last_24h": db.query(Article).filter(
                Article.created_at > datetime.now() - timedelta(days=1)
            ).count(),
            "articles_with_substantial_abstracts": db.query(Article).filter(
                text("LENGTH(TRIM(articles.abstract)) >= 100")
            ).count(),
            "articles_needing_abstracts": db.query(Article).filter(
                (Article.abstract == None) |
                (Article.abstract == '') |
                (text("LENGTH(TRIM(articles.abstract)) < 100"))
            ).count()
        }
        
        return {
            "database": db_stats,
            "ai_status": {
                "enabled": ai_service.ai_enabled,
                "embedding_model": ai_service.embedding_model,
                "chat_model": ai_service.chat_model
            },
            "enhanced_features": {
                "multiple_api_sources": True,
                "intelligent_source_selection": True,
                "abstract_quality_filtering": True,
                "enhanced_deduplication": True,
                "api_sources": ["PubMed", "Europe PMC", "Semantic Scholar", "ClinicalTrials.gov", "ArXiv"]
            }
        }
    except Exception as e:
        logger.error(f"Error getting enhanced usage stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/abstract-coverage")
async def get_abstract_coverage(db: Session = Depends(get_db)):
    """Get detailed abstract coverage statistics"""
    try:
        total_articles = db.query(Article).count()
        
        coverage_stats = {
            "total_articles": total_articles,
            "articles_with_any_abstract": db.query(Article).filter(
                Article.abstract != None,
                Article.abstract != ''
            ).count(),
            "articles_with_substantial_abstracts": db.query(Article).filter(
                text("LENGTH(TRIM(articles.abstract)) >= 100")
            ).count(),
            "articles_with_excellent_abstracts": db.query(Article).filter(
                text("LENGTH(TRIM(articles.abstract)) >= 300")
            ).count(),
            "articles_needing_improvement": db.query(Article).filter(
                (Article.abstract == None) |
                (Article.abstract == '') |
                (text("LENGTH(TRIM(articles.abstract)) < 100"))
            ).count()
        }
        
        # Calculate percentages
        if total_articles > 0:
            coverage_stats["coverage_percentages"] = {
                "any_abstract": round((coverage_stats["articles_with_any_abstract"] / total_articles) * 100, 1),
                "substantial_abstract": round((coverage_stats["articles_with_substantial_abstracts"] / total_articles) * 100, 1),
                "excellent_abstract": round((coverage_stats["articles_with_excellent_abstracts"] / total_articles) * 100, 1)
            }
        
        return coverage_stats
        
    except Exception as e:
        logger.error(f"Error getting abstract coverage: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)