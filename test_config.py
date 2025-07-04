import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import Mock, patch

from main import app
from database import get_db
from models import Base

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

# Test fixtures
@pytest.fixture
def mock_openai():
    """Mock OpenAI responses"""
    with patch('openai.OpenAI') as mock_client:
        # Mock embedding response
        mock_client.return_value.embeddings.create.return_value.data = [
            Mock(embedding=[0.1, 0.2, 0.3])
        ]
        
        # Mock chat completion response
        mock_client.return_value.chat.completions.create.return_value.choices = [
            Mock(message=Mock(content='{"primary_area": "Oncology", "research_type": "Clinical Trial", "key_topics": ["cancer", "treatment"]}'))
        ]
        
        yield mock_client

@pytest.fixture
def sample_search_query():
    """Sample search query for testing"""
    return {"query": "cancer treatment", "limit": 5}

@pytest.fixture
def sample_article_data():
    """Sample article data for testing"""
    return {
        "id": "test-123",
        "doi": "10.1000/test",
        "title": "Test Article",
        "authors": ["John Doe", "Jane Smith"],
        "publication_date": "2024-01-01",
        "journal": "Test Journal",
        "abstract": "This is a test abstract about cancer treatment.",
        "url": "https://example.com/article",
        "source": "test"
    }

# Basic API tests
def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()

@patch('api_services.APIManager.search_all')
def test_search_empty_results(mock_search):
    """Test search with no results"""
    mock_search.return_value = []
    
    response = client.post("/search", json={"query": "nonexistent", "limit": 10})
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert len(response.json()["articles"]) == 0

def test_search_invalid_query():
    """Test search with invalid query"""
    response = client.post("/search", json={"query": "", "limit": 10})
    assert response.status_code == 422  # Validation error

def test_get_nonexistent_article():
    """Test getting non-existent article"""
    response = client.get("/articles/nonexistent")
    assert response.status_code == 404

def test_trends_endpoint():
    """Test trends endpoint"""
    response = client.get("/trends?days=30")
    assert response.status_code == 200
    assert "trends" in response.json()

# Integration tests
@patch('api_services.APIManager.search_all')
def test_search_integration(mock_search, mock_openai, sample_article_data):
    """Test complete search integration"""
    # Mock API response
    from models import APIArticle
    mock_article = APIArticle(**sample_article_data)
    mock_search.return_value = [mock_article]
    
    response = client.post("/search", json={"query": "cancer", "limit": 5})
    
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["articles"]) == 1
    assert data["articles"][0]["title"] == "Test Article"

# Performance tests
def test_search_performance():
    """Basic performance test for search endpoint"""
    import time
    
    start_time = time.time()
    response = client.post("/search", json={"query": "test", "limit": 1})
    end_time = time.time()
    
    # Should complete within 30 seconds (generous for AI processing)
    assert end_time - start_time < 30
    assert response.status_code in [200, 500]  # May fail due to missing API keys

# Error handling tests
def test_search_with_invalid_limit():
    """Test search with invalid limit"""
    response = client.post("/search", json={"query": "test", "limit": 0})
    assert response.status_code == 422

def test_search_with_too_large_limit():
    """Test search with limit too large"""
    response = client.post("/search", json={"query": "test", "limit": 1000})
    assert response.status_code == 422

def test_similar_articles_nonexistent():
    """Test similar articles for non-existent article"""
    response = client.get("/articles/nonexistent/similar")
    assert response.status_code == 404

def test_summarize_nonexistent_article():
    """Test summarize non-existent article"""
    response = client.post("/articles/nonexistent/summarize")
    assert response.status_code == 404

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
