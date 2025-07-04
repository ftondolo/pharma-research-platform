from fastapi import FastAPI, HTTPException, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
import logging

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

@app.post("/search", response_model=SearchResponse)
async def search_articles(
    query: SearchQuery,
    db: Session = Depends(get_db)
):
    """Search for articles across multiple APIs with AI-powered ranking"""
    try:
        logger.info(f"Search request: {query.query}")
        
        # Search across all APIs
        results = await api_manager.search_all(query.query, limit=query.limit)
        
        if not results:
            logger.info("No results found for query")
            return SearchResponse(articles=[], total=0)
        
        logger.info(f"Found {len(results)} articles from APIs")
        
        # Process results with AI for categorization and ranking
        processed_articles = []
        for result in results:
            try:
                # Generate embedding for semantic search
                embedding = await ai_service.get_embedding(result.abstract)
                
                # Categorize article
                categories = await ai_service.categorize_article(result.abstract)
                
                # Create article with processed data
                article = ArticleResponse(
                    id=result.id,
                    doi=result.doi,
                    title=result.title,
                    authors=result.authors,
                    publication_date=result.publication_date,
                    journal=result.journal,
                    abstract=result.abstract,
                    url=result.url,
                    categories=categories,
                    embedding=embedding
                )
                processed_articles.append(article)
                
            except Exception as e:
                logger.error(f"Error processing article {result.id}: {str(e)}")
                # Continue with other articles if one fails
                continue
        
        # Store in database with duplicate handling and collect database IDs
        stored_articles = []
        for article in processed_articles:
            try:
                # Check if article already exists by DOI
                existing_article = None
                if article.doi:
                    existing_article = db.query(Article).filter(Article.doi == article.doi).first()
                
                if existing_article:
                    # Update existing article
                    existing_article.title = article.title
                    existing_article.authors = article.authors
                    existing_article.publication_date = article.publication_date
                    existing_article.journal = article.journal
                    existing_article.abstract = article.abstract
                    existing_article.url = article.url
                    existing_article.categories = article.categories
                    existing_article.embedding = article.embedding
                    stored_articles.append(existing_article)
                else:
                    # Insert new article
                    db_article = Article(
                        doi=article.doi,
                        title=article.title,
                        authors=article.authors,
                        publication_date=article.publication_date,
                        journal=article.journal,
                        abstract=article.abstract,
                        url=article.url,
                        categories=article.categories,
                        embedding=article.embedding
                    )
                    db.add(db_article)
                    db.flush()  # Get the ID without committing
                    stored_articles.append(db_article)
                    
            except Exception as e:
                logger.error(f"Error storing article {article.id}: {str(e)}")
                continue
        
        db.commit()
        logger.info(f"Stored {len(stored_articles)} articles in database")
        
        # Return articles with database IDs
        response_articles = []
        for db_article in stored_articles:
            response_article = ArticleResponse(
                id=str(db_article.id),  # Use database UUID
                doi=db_article.doi,
                title=db_article.title,
                authors=db_article.authors,
                publication_date=db_article.publication_date,
                journal=db_article.journal,
                abstract=db_article.abstract,
                url=db_article.url,
                categories=db_article.categories,
                embedding=db_article.embedding,
                created_at=db_article.created_at
            )
            response_articles.append(response_article)
        
        return SearchResponse(articles=response_articles, total=len(response_articles))
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)