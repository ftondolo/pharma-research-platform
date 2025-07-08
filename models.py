from pydantic import BaseModel, Field, field_serializer
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

# SQLAlchemy Model (for database)
class Article(Base):
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True, index=True)
    doi = Column(String, unique=True, index=True, nullable=True)
    title = Column(Text, nullable=False)
    abstract = Column(Text, nullable=True)
    authors = Column(JSON, nullable=True)
    publication_date = Column(String, nullable=True)
    journal = Column(String, nullable=True)
    url = Column(String, nullable=True)
    categories = Column(JSON, nullable=True)
    embedding = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# Pydantic Models
class SearchQuery(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)

class ArticleCreate(BaseModel):
    doi: Optional[str] = None
    title: str
    abstract: Optional[str] = None
    authors: Optional[List[str]] = None
    publication_date: Optional[str] = None
    journal: Optional[str] = None
    url: Optional[str] = None

APIArticle = ArticleCreate

def safe_parse_date(value: Optional[str]) -> Optional[str]:
    """
    Converts strings like '2025' or '2025-07' to full ISO date strings ('2025-01-01').
    Returns None if parsing fails.
    """
    if not value:
        return None
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
            try:
                parsed = datetime.strptime(value, fmt).date()
                return parsed.isoformat()
            except ValueError:
                continue
    return None

class ArticleResponse(BaseModel):
    id: str
    doi: Optional[str] = None
    title: str
    abstract: Optional[str] = None
    authors: Optional[List[str]] = None
    publication_date: Optional[str] = None  # Changed to str
    journal: Optional[str] = None
    url: Optional[str] = None
    categories: Optional[List[str]] = None
    embedding: Optional[List[float]] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_serializer('publication_date')
    def serialize_publication_date(self, pub_date, _info):
        return safe_parse_date(pub_date)

class SearchResponse(BaseModel):
    articles: List[ArticleResponse]
    total: int
    metadata: Optional[Dict[str, Any]] = None

class SummaryResponse(BaseModel):
    one_line: str
    key_findings: Optional[List[str]] = None
    clinical_implications: Optional[str] = None
    limitations: Optional[str] = None
