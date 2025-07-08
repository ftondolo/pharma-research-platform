from pydantic import BaseModel, Field, field_validator, field_serializer
from typing import List, Optional, Dict, Any, Union
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
    publication_date = Column(String, nullable=True)  # Store as string in DB
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

def safe_parse_date(value) -> Optional[str]:
    """
    Converts various date formats to string.
    Handles: strings, datetime.date, datetime.datetime, integers (years)
    """
    if value is None:
        return None
    
    # If it's already a string, return it
    if isinstance(value, str):
        return value.strip() if value.strip() else None
    
    # If it's a date or datetime object
    if isinstance(value, (date, datetime)):
        return str(value.year)  # Just return the year as string
    
    # If it's an integer (year)
    if isinstance(value, int):
        if 1900 <= value <= 2100:  # Reasonable year range
            return str(value)
    
    # Try to convert to string as fallback
    try:
        return str(value)
    except:
        return None

class ArticleResponse(BaseModel):
    id: str
    doi: Optional[str] = None
    title: str
    abstract: Optional[str] = None
    authors: Optional[List[str]] = None
    publication_date: Optional[str] = None
    journal: Optional[str] = None
    url: Optional[str] = None
    categories: Optional[List[str]] = None
    embedding: Optional[List[float]] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_validator('publication_date', mode='before')
    @classmethod
    def validate_publication_date(cls, v):
        """Convert any date format to string before validation"""
        return safe_parse_date(v)

    @field_serializer('publication_date')
    def serialize_publication_date(self, pub_date, _info):
        """Ensure publication date is always serialized as string"""
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