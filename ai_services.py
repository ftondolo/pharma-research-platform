import openai
import json
import os
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Article, Categories, Summary, TrendAnalysis
import numpy as np
from datetime import datetime, timedelta
import asyncio
from concurrent.futures import ThreadPoolExecutor

class AIService:
    """AI service for categorization, summarization, and embeddings"""
    
    def __init__(self):
        self.client = openai.OpenAI(
            api_key="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"
        )
        self.embedding_model = "text-embedding-3-large"
        self.chat_model = "gpt-4.1-mini"
        self.executor = ThreadPoolExecutor(max_workers=5)
        
        # Prompt templates
        self.categorization_prompt = """
Given this pharmaceutical research abstract, categorize it into:
1. Primary therapeutic area (e.g., Oncology, Cardiology, Neurology, etc.)
2. Research type (e.g., Clinical Trial, Drug Discovery, Review, etc.)
3. Key topics (up to 5 specific topics)

Return ONLY a JSON object with this structure:
{
  "primary_area": "string",
  "research_type": "string", 
  "key_topics": ["topic1", "topic2", "topic3"]
}

Abstract: {abstract}
"""
        
        self.summary_prompt = """
Create a structured summary of this pharmaceutical research abstract:

Abstract: {abstract}

Return ONLY a JSON object with this structure:
{
  "one_line": "Brief one-sentence summary",
  "key_findings": ["finding1", "finding2", "finding3"],
  "clinical_implications": "Brief clinical implications",
  "limitations": "Any limitations mentioned or null"
}
"""
        
        self.trend_prompt = """
Analyze these pharmaceutical research abstracts and identify:
1. Most frequent topics (top 5)
2. Emerging themes (new or growing topics)
3. Notable shifts from what might be expected

Return ONLY a JSON object with this structure:
{
  "frequent_topics": ["topic1", "topic2", "topic3"],
  "emerging_themes": ["theme1", "theme2"],
  "notable_shifts": ["shift1", "shift2"]
}

Abstracts: {abstracts}
"""
    
    def _get_embedding_sync(self, text: str) -> List[float]:
        """Synchronous embedding call"""
        try:
            response = self.client.embeddings.create(
                input=text,
                model=self.embedding_model
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Embedding error: {e}")
            return []
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding for text using OpenAI"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self._get_embedding_sync, text)
    
    def _categorize_article_sync(self, abstract: str) -> List[str]:
        """Synchronous categorization call"""
        try:
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": "You are a pharmaceutical research expert. Return only valid JSON."},
                    {"role": "user", "content": self.categorization_prompt.format(abstract=abstract)}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Flatten categories into a list
            categories = [result.get('primary_area', '')]
            categories.append(result.get('research_type', ''))
            categories.extend(result.get('key_topics', []))
            
            return [cat for cat in categories if cat]
            
        except Exception as e:
            print(f"Categorization error: {e}")
            return []
    
    async def categorize_article(self, abstract: str) -> List[str]:
        """Categorize an article abstract"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self._categorize_article_sync, abstract)
    
    def _summarize_article_sync(self, abstract: str) -> Dict[str, Any]:
        """Synchronous summarization call"""
        try:
            if not abstract or len(abstract.strip()) < 10:
                print("Abstract too short or empty")
                return {
                    "one_line": "Abstract too short to summarize",
                    "key_findings": [],
                    "clinical_implications": "Not available",
                    "limitations": None
                }

            print(f"Summarizing abstract: {abstract[:100]}...")

            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": "You are a pharmaceutical research expert. Return only valid JSON."},
                    {"role": "user", "content": self.summary_prompt.format(abstract=abstract)}
                ],
                temperature=0.25,
                max_tokens=400
            )

            # Safely extract content from response
            response_text = ""

            # Access response.choices[0].message["content"]
            print("0")
            if hasattr(response, "choices") and response.choices:
                message = response.choices[0].message
                print("1")
                if isinstance(message, dict):
                    response_text = message.get("content", "")
                    if not response_text:
                        print("A")
                        raise ValueError("Empty 'content' in response message")
                else:
                    print("B")
                    raise ValueError("Invalid message format")
            else:
                print("C")
                raise ValueError("No choices returned from OpenAI")

            print(f"OpenAI response: {response_text}")

            result = json.loads(response_text)
            print(f"Parsed result: {result}")

            # Validate and normalize expected fields
            return {
                "one_line": result.get("one_line", "No summary available"),
                "key_findings": result.get("key_findings", []),
                "clinical_implications": result.get("clinical_implications", "Not available"),
                "limitations": result.get("limitations", None)
            }

        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Raw response: {response_text}")
            return {
                "one_line": "Error parsing AI response",
                "key_findings": [],
                "clinical_implications": "Not available",
                "limitations": None
            }
        except Exception as e:
            print(f"Summary error: {e}")
            print(f"Error type: {type(e).__name__}")
            return {
                "one_line": "Summary unavailable",
                "key_findings": [],
                "clinical_implications": "Not available",
                "limitations": None
            }
    
    async def summarize_article(self, abstract: str) -> Dict[str, Any]:
        """Generate structured summary of an article"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self._summarize_article_sync, abstract)
    
    async def find_similar_articles(
        self, 
        query_embedding: List[float], 
        db: Session, 
        limit: int = 5,
        exclude_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Find similar articles using cosine similarity"""
        try:
            if not query_embedding:
                return []
            
            # Get all articles with embeddings
            query = db.query(Article).filter(Article.embedding.isnot(None))
            if exclude_id:
                query = query.filter(Article.id != exclude_id)
            
            articles = query.all()
            
            if not articles:
                return []
            
            # Calculate similarities
            similarities = []
            query_vec = np.array(query_embedding)
            
            for article in articles:
                if article.embedding and len(article.embedding) > 0:
                    try:
                        article_vec = np.array(article.embedding)
                        if len(article_vec) > 0 and len(query_vec) > 0:
                            similarity = np.dot(query_vec, article_vec) / (
                                np.linalg.norm(query_vec) * np.linalg.norm(article_vec)
                            )
                            similarities.append({
                                'article': article,
                                'similarity': float(similarity)
                            })
                    except Exception as e:
                        print(f"Error calculating similarity for article {article.id}: {e}")
                        continue
            
            # Sort by similarity and return top results
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            
            results = []
            for sim in similarities[:limit]:
                article = sim['article']
                results.append({
                    'id': str(article.id),
                    'title': article.title or 'Untitled',
                    'similarity': sim['similarity'],
                    'journal': article.journal or 'Unknown',
                    'publication_date': article.publication_date.isoformat() if article.publication_date else None
                })
            
            return results
            
        except Exception as e:
            print(f"Similarity search error: {e}")
            return []
    
    def _analyze_trends_sync(self, abstracts: List[str]) -> Dict[str, Any]:
        """Synchronous trend analysis call"""
        try:
            # Limit abstracts to avoid token limits
            sample_abstracts = abstracts[:20]
            abstracts_text = "\n\n".join([f"Abstract {i+1}: {abs}" for i, abs in enumerate(sample_abstracts)])
            
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": "You are a pharmaceutical research expert analyzing trends. Return only valid JSON."},
                    {"role": "user", "content": self.trend_prompt.format(abstracts=abstracts_text)}
                ],
                temperature=0.2,
                max_tokens=500
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            print(f"Trend analysis error: {e}")
            return {
                "frequent_topics": [],
                "emerging_themes": [],
                "notable_shifts": []
            }
    
    async def analyze_trends(self, abstracts: List[str]) -> Dict[str, Any]:
        """Analyze trends in a collection of abstracts"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self._analyze_trends_sync, abstracts)
    
    def calculate_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            v1 = np.array(vec1)
            v2 = np.array(vec2)
            return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        except:
            return 0.0