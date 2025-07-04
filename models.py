from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Text, Date, DateTime, Integer, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from typing import List, Optional, Dict, Any
from datetime import datetime, date
import uuid

Base = declarative_base()

# SQLAlchemy Models
class Article(Base):
    __tablename__ = "articles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doi = Column(String(255), unique=True, index=True)
    title = Column(Text, nullable=False)
    authors = Column(JSONB)  # Store as JSON array
    publication_date = Column(Date)
    journal = Column(String(255))
    abstract = Column(Text)
    url = Column(Text)
    categories = Column(JSONB)  # Store as JSON array
    embedding = Column(JSONB)   # Store embeddings as JSON array (more compatible)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# Pydantic Models
class ArticleBase(BaseModel):
    doi: Optional[str] = None
    title: str
    authors: List[str] = []
    publication_date: Optional[date] = None
    journal: Optional[str] = None
    abstract: str
    url: str

class ArticleCreate(ArticleBase):
    pass

class ArticleResponse(ArticleBase):
    id: str
    categories: List[str] = []
    embedding: Optional[List[float]] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class SearchQuery(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=50)

class SearchResponse(BaseModel):
    articles: List[ArticleResponse]
    total: int

class APIArticle(BaseModel):
    """Raw article data from external APIs"""
    id: str
    doi: Optional[str] = None
    title: str
    authors: List[str] = []
    publication_date: Optional[date] = None
    journal: Optional[str] = None
    abstract: str
    url: str
    source: str  # API source identifier

class Categories(BaseModel):
    primary_area: str
    research_type: str
    key_topics: List[str]

class Summary(BaseModel):
    one_line: str
    key_findings: List[str]
    clinical_implications: str
    limitations: Optional[str] = None

class TrendAnalysis(BaseModel):
    frequent_topics: List[str]
    emerging_themes: List[str]
    notable_shifts: List[str]