#!/usr/bin/env python3
"""
Simple database test script to verify setup
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_database_connection():
    """Test database connection and setup"""
    print("Testing database connection...")
    
    try:
        from database import engine, init_db
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            print("✓ Database connection successful")
        
        # Test table creation
        init_db()
        print("✓ Database tables created successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        return False

def test_basic_crud():
    """Test basic CRUD operations"""
    print("Testing basic CRUD operations...")
    
    try:
        from database import SessionLocal
        from models import Article
        from datetime import date
        
        # Create a test article
        db = SessionLocal()
        
        test_article = Article(
            doi="10.1000/test",
            title="Test Article",
            authors=["John Doe", "Jane Smith"],
            publication_date=date(2024, 1, 1),
            journal="Test Journal",
            abstract="This is a test abstract.",
            url="https://example.com/test",
            categories=["Test", "Example"],
            embedding=[0.1, 0.2, 0.3]  # Simple test embedding
        )
        
        # Insert
        db.add(test_article)
        db.commit()
        print("✓ Article inserted successfully")
        
        # Query
        article = db.query(Article).filter(Article.doi == "10.1000/test").first()
        if article:
            print("✓ Article retrieved successfully")
            print(f"  Title: {article.title}")
            print(f"  Authors: {article.authors}")
            print(f"  Categories: {article.categories}")
        
        # Cleanup
        db.delete(article)
        db.commit()
        db.close()
        print("✓ Article deleted successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ CRUD test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Database Setup Test")
    print("==================")
    
    # Check environment
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("✗ DATABASE_URL not set in environment")
        return False
    
    print(f"Database URL: {db_url}")
    
    # Run tests
    success = True
    
    if not test_database_connection():
        success = False
    
    if not test_basic_crud():
        success = False
    
    if success:
        print("\n✅ All database tests passed!")
        print("Database setup is working correctly.")
    else:
        print("\n❌ Some tests failed.")
        print("Please check your database configuration.")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
