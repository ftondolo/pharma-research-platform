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
    search_database: bool = Query(True, description="Include existing database articles in search"),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """
    Hybrid search combining database search with external API scraping.
    Accurately tracks final source counts after all filtering.
    """
    try:
        logger.info(f"Hybrid search request: {search_query.query} (require_abstract: {require_abstract}, search_db: {search_database}, limit: {search_query.limit})")
        
        target_count = search_query.limit
        all_articles = []  # Will track source for each article
        filtered_count = 0
        total_api_calls = 0
        
        # PHASE 1: Search existing database first
        database_articles = []
        if search_database:
            logger.info("Phase 1: Searching existing database...")
            db_articles = await search_database_articles(db, search_query.query, target_count * 2, require_abstract)  # Get more for better selection
            database_articles = db_articles
            logger.info(f"Found {len(database_articles)} relevant articles in database")
            
            # Mark database articles with source
            for article in database_articles:
                all_articles.append({
                    'article': article,
                    'source': 'database'
                })
        
        # PHASE 2: Supplement with external APIs if needed
        remaining_needed = target_count - len(all_articles)
        external_articles_added = 0
        
        if remaining_needed > 0:
            logger.info(f"Phase 2: Fetching {remaining_needed} additional articles from external APIs...")
            
            max_fetch_attempts = 2
            fetch_attempt = 0
            total_processed = 0
            
            # Get article identifiers we already have to avoid duplicates
            existing_dois = set()
            existing_titles = set()
            for item in all_articles:
                article = item['article']
                if article.doi:
                    existing_dois.add(article.doi.lower().strip())
                if article.title:
                    existing_titles.add(article.title.lower().strip())
            
            while len(all_articles) < target_count and fetch_attempt < max_fetch_attempts:
                fetch_attempt += 1
                
                still_needed = target_count - len(all_articles)
                # Fetch more when abstract filtering to compensate for filtering
                fetch_multiplier = 3 if require_abstract else 1.5
                fetch_count = min(int(still_needed * fetch_multiplier), 50)
                
                logger.info(f"External fetch attempt {fetch_attempt}: requesting {fetch_count} articles")
                
                # Use enhanced API manager
                external_articles = await enhanced_api_manager.search_all(
                    search_query.query, fetch_count, offset=total_processed
                )
                total_api_calls += 1
                
                if not external_articles:
                    logger.info(f"No more external articles found on attempt {fetch_attempt}")
                    break
                
                logger.info(f"External APIs returned {len(external_articles)} articles")
                
                # Process external articles
                for article_data in external_articles:
                    total_processed += 1
                    
                    # Skip if we've reached our target
                    if len(all_articles) >= target_count:
                        break
                    
                    # Abstract filtering
                    if require_abstract:
                        if not article_data.abstract or len(article_data.abstract.strip()) < 100:
                            filtered_count += 1
                            continue
                    
                    # Deduplication against existing results
                    is_duplicate = False
                    
                    if article_data.doi:
                        doi_clean = article_data.doi.lower().strip()
                        if doi_clean in existing_dois:
                            is_duplicate = True
                    
                    if not is_duplicate and article_data.title:
                        title_clean = article_data.title.lower().strip()
                        if title_clean in existing_titles:
                            is_duplicate = True
                    
                    if is_duplicate:
                        logger.debug(f"Skipping duplicate: {article_data.title[:50]}...")
                        continue
                    
                    # Check if exists in database (for potential enhancement)
                    existing = None
                    if article_data.doi:
                        existing = db.query(Article).filter(Article.doi == article_data.doi).first()
                    
                    if not existing and article_data.title:
                        title_normalized = article_data.title.strip().lower()
                        existing = db.query(Article).filter(
                            text("LOWER(TRIM(title)) = :title")
                        ).params(title=title_normalized).first()
                    
                    if existing:
                        # Use existing article but count as external since it came from external API
                        if require_abstract and (not existing.abstract or len(existing.abstract.strip()) < 100):
                            filtered_count += 1
                            continue
                        
                        all_articles.append({
                            'article': existing,
                            'source': 'external'  # Count as external since external API found it
                        })
                        
                        # Update deduplication sets
                        if existing.doi:
                            existing_dois.add(existing.doi.lower().strip())
                        if existing.title:
                            existing_titles.add(existing.title.lower().strip())
                    else:
                        # Create new article
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
                        
                        all_articles.append({
                            'article': article,
                            'source': 'external'
                        })
                        external_articles_added += 1
                        
                        # Update deduplication sets
                        if article.doi:
                            existing_dois.add(article.doi.lower().strip())
                        if article.title:
                            existing_titles.add(article.title.lower().strip())
                
                # Break if external APIs seem exhausted
                if len(external_articles) < fetch_count // 3:
                    logger.info("External APIs returned fewer articles than expected")
                    break
        
        # Commit new articles
        try:
            db.commit()
            logger.info(f"Committed {external_articles_added} new articles to database")
        except Exception as e:
            logger.error(f"Database commit error: {e}")
            db.rollback()
            for item in all_articles:
                article = item['article']
                if hasattr(article, 'id'):
                    db.refresh(article)
        
        # Calculate final accurate counts
        final_articles = all_articles[:target_count]
        
        # Count sources in final results
        final_database_count = sum(1 for item in final_articles if item['source'] == 'database')
        final_external_count = sum(1 for item in final_articles if item['source'] == 'external')
        
        logger.info(f"Final results: {final_database_count} database + {final_external_count} external = {len(final_articles)} total")
        
        return SearchResponse(
            articles=[
                ArticleResponse(
                    id=str(item['article'].id) if item['article'].id is not None else f"temp-{idx}",
                    doi=item['article'].doi,
                    title=item['article'].title,
                    abstract=item['article'].abstract[:800] + "..." if item['article'].abstract and len(item['article'].abstract) > 800 else item['article'].abstract or "",
                    authors=item['article'].authors or [],
                    publication_date=safe_parse_date(item['article'].publication_date),
                    journal=item['article'].journal,
                    url=item['article'].url,
                    categories=item['article'].categories or [],
                    created_at=item['article'].created_at
                )
                for idx, item in enumerate(final_articles)
            ],
            total=len(final_articles),
            metadata={
                "requested_count": search_query.limit,
                "delivered_count": len(final_articles),
                "database_results": final_database_count,  # Accurate count of final database articles
                "external_results": final_external_count,  # Accurate count of final external articles
                "filtered_count": filtered_count,
                "require_abstract": require_abstract,
                "search_database": search_database,
                "hybrid_search": True,
                "search_complete": len(final_articles) >= target_count or total_api_calls >= 2,
                "api_calls_made": total_api_calls,
                "sources": {
                    "database": final_database_count,
                    "external_apis": final_external_count
                },
                "api_sources": ["Database", "PubMed", "Europe PMC", "Semantic Scholar", "ClinicalTrials.gov", "ArXiv"]
            }
        )
        
    except Exception as e:
        logger.error(f"Hybrid search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def search_database_articles(db: Session, query: str, limit: int, require_abstract: bool = False) -> List[Article]:
    """
    Search existing database articles using multiple strategies
    """
    try:
        # Prepare search terms
        query_lower = query.lower().strip()
        query_words = [word for word in query_lower.split() if len(word) >= 3]
        
        if not query_words:
            return []
        
        # Build base query
        base_query = db.query(Article)
        
        # Apply abstract filter if required
        if require_abstract:
            base_query = base_query.filter(
                Article.abstract != None,
                Article.abstract != "",
                text("LENGTH(TRIM(articles.abstract)) >= 100")
            )
        
        # Strategy 1: Title keyword matching (most relevant)
        title_conditions = []
        for word in query_words:
            title_conditions.append(text("LOWER(title) LIKE :word").params(word=f"%{word}%"))
        
        if title_conditions:
            title_query = base_query.filter(
                *title_conditions
            ).order_by(Article.created_at.desc()).limit(limit // 2)  # Half from title matches
            
            title_results = title_query.all()
        else:
            title_results = []
        
        # Strategy 2: Abstract keyword matching (supplementary)
        remaining_limit = limit - len(title_results)
        if remaining_limit > 0:
            abstract_conditions = []
            for word in query_words:
                abstract_conditions.append(text("LOWER(abstract) LIKE :word").params(word=f"%{word}%"))
            
            if abstract_conditions:
                # Exclude articles already found by title search
                title_ids = [article.id for article in title_results]
                abstract_query = base_query.filter(
                    *abstract_conditions
                )
                
                if title_ids:
                    abstract_query = abstract_query.filter(~Article.id.in_(title_ids))
                
                abstract_query = abstract_query.order_by(Article.created_at.desc()).limit(remaining_limit)
                abstract_results = abstract_query.all()
            else:
                abstract_results = []
        else:
            abstract_results = []
        
        # Strategy 3: Journal/author matching (if still need more)
        combined_results = title_results + abstract_results
        remaining_limit = limit - len(combined_results)
        
        if remaining_limit > 0:
            # Search in journal names
            existing_ids = [article.id for article in combined_results]
            
            journal_conditions = []
            for word in query_words:
                journal_conditions.append(text("LOWER(journal) LIKE :word").params(word=f"%{word}%"))
            
            if journal_conditions:
                other_query = base_query.filter(
                    *journal_conditions
                )
                
                if existing_ids:
                    other_query = other_query.filter(~Article.id.in_(existing_ids))
                
                other_query = other_query.order_by(Article.created_at.desc()).limit(remaining_limit)
                other_results = other_query.all()
            else:
                other_results = []
            
            combined_results.extend(other_results)
        
        logger.info(f"Database search found: {len(title_results)} title matches, {len(abstract_results)} abstract matches, {len(combined_results) - len(title_results) - len(abstract_results)} other matches")
        
        return combined_results[:limit]
        
    except Exception as e:
        logger.error(f"Database search error: {e}")
        return []
    
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
async def get_trends(days: int = Query(30, ge=1, le=90), db: Session = Depends(get_db)):
    """Real trends analysis from database articles"""
    try:
        from trends_analyzer import trends_analyzer
        
        # Get real trends from database
        trends_data = trends_analyzer.analyze_comprehensive_trends(db, days)
        
        return {
            "trends": {
                "frequent_topics": trends_data.get("frequent_topics", []),
                "emerging_themes": trends_data.get("emerging_themes", []),
                "notable_shifts": trends_data.get("notable_shifts", [])
            },
            "search_suggestions": trends_data.get("search_suggestions", []),
            "period_days": days,
            "metadata": {
                "generated_at": trends_data.get("generated_at"),
                "data_source": trends_data.get("data_source", "database"),
                "confidence": trends_data.get("confidence", "medium"),
                "period_stats": trends_data.get("period_stats", {}),
                "enhanced": True,
                "real_data": True
            }
        }
        
    except Exception as e:
        logger.error(f"Error in real trends analysis: {str(e)}")
        # Fallback to basic trends
        return {
            "trends": {
                "frequent_topics": ["Cancer Research", "Drug Discovery", "Clinical Trials"],
                "emerging_themes": ["AI in Medicine", "Digital Health", "Gene Therapy"],
                "notable_shifts": ["Personalized Medicine", "Remote Trials"]
            },
            "search_suggestions": ["Cancer Immunotherapy", "AI Drug Discovery", "Clinical Trials"],
            "period_days": days,
            "metadata": {
                "data_source": "fallback",
                "confidence": "low",
                "enhanced": True,
                "real_data": False
            }
        }

@app.get("/trending-searches")
async def get_trending_searches(db: Session = Depends(get_db)):
    """Get trending search terms for quick access"""
    try:
        from trends_analyzer import trends_analyzer
        
        # Get trending terms that make good searches
        trending_terms = trends_analyzer.get_trending_searches(db, days=7)
        
        return {
            "trending_searches": trending_terms,
            "generated_at": datetime.now().isoformat(),
            "period": "last_7_days",
            "source": "database_analysis"
        }
        
    except Exception as e:
        logger.error(f"Error getting trending searches: {str(e)}")
        return {
            "trending_searches": [
                "Cancer Immunotherapy", "CRISPR Gene Editing", "mRNA Vaccines",
                "AI Drug Discovery", "Digital Biomarkers", "Precision Medicine"
            ],
            "generated_at": datetime.now().isoformat(),
            "period": "last_7_days", 
            "source": "fallback"
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