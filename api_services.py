# backend/api_services.py

import aiohttp
import asyncio
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
import logging
from urllib.parse import quote
import json
from datetime import datetime

# Import the models we need
from models import ArticleCreate

logger = logging.getLogger(__name__)

def ensure_string_date(date_value):
    """Ensure date value is a string, not a date object"""
    if date_value is None:
        return None
    if isinstance(date_value, str):
        return date_value
    if hasattr(date_value, 'year'):  # datetime.date or datetime.datetime
        return str(date_value.year)
    return str(date_value)

class RateLimiter:
    """Simple rate limiter for API calls"""
    def __init__(self, calls_per_second: float):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0
    
    async def wait(self):
        now = asyncio.get_event_loop().time()
        time_since_last = now - self.last_call
        if time_since_last < self.min_interval:
            await asyncio.sleep(self.min_interval - time_since_last)
        self.last_call = asyncio.get_event_loop().time()

class PubMedAPI:
    """PubMed E-utilities API client"""
    def __init__(self):
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.rate_limiter = RateLimiter(3.0)  # 3 requests per second
        
    async def search(self, query: str, limit: int = 10) -> List[ArticleCreate]:
        """Search PubMed for articles"""
        await self.rate_limiter.wait()
        
        async with aiohttp.ClientSession() as session:
            try:
                # First, search for PMIDs
                search_url = f"{self.base_url}/esearch.fcgi"
                search_params = {
                    'db': 'pubmed',
                    'term': query,
                    'retmax': limit,
                    'retmode': 'xml'
                }
                
                async with session.get(search_url, params=search_params) as response:
                    if response.status != 200:
                        logger.error(f"PubMed search failed with status {response.status}")
                        return []
                    
                    search_xml = await response.text()
                    pmids = self._parse_search_results(search_xml)
                    
                    if not pmids:
                        logger.info("No PMIDs found from PubMed search")
                        return []
                    
                    # Get detailed info for each PMID
                    await self.rate_limiter.wait()
                    fetch_url = f"{self.base_url}/efetch.fcgi"
                    fetch_params = {
                        'db': 'pubmed',
                        'id': ','.join(pmids),
                        'retmode': 'xml'
                    }
                    
                    async with session.get(fetch_url, params=fetch_params) as fetch_response:
                        if fetch_response.status != 200:
                            logger.error(f"PubMed fetch failed with status {fetch_response.status}")
                            return []
                        
                        fetch_xml = await fetch_response.text()
                        return self._parse_articles(fetch_xml)
            
            except Exception as e:
                logger.error(f"PubMed API error: {e}")
                return []
    
    def _parse_search_results(self, xml_content: str) -> List[str]:
        """Parse PMIDs from search results"""
        try:
            root = ET.fromstring(xml_content)
            pmids = []
            for id_elem in root.findall('.//Id'):
                if id_elem.text:
                    pmids.append(id_elem.text)
            return pmids
        except Exception as e:
            logger.error(f"Error parsing PubMed search results: {e}")
            return []
    
    def _parse_articles(self, xml_content: str) -> List[ArticleCreate]:
        """Parse article details from XML"""
        articles = []
        try:
            root = ET.fromstring(xml_content)
            
            for article_elem in root.findall('.//PubmedArticle'):
                try:
                    medline = article_elem.find('MedlineCitation')
                    if medline is None:
                        continue
                        
                    pmid_elem = medline.find('PMID')
                    pmid = pmid_elem.text if pmid_elem is not None else None
                    
                    article_data = medline.find('Article')
                    if article_data is None:
                        continue
                    
                    title_elem = article_data.find('ArticleTitle')
                    title = title_elem.text if title_elem is not None else "No title"
                    
                    # Parse authors
                    authors = []
                    author_list = article_data.find('AuthorList')
                    if author_list is not None:
                        for author in author_list.findall('Author'):
                            last_name = author.find('LastName')
                            first_name = author.find('ForeName')
                            if last_name is not None and first_name is not None:
                                authors.append(f"{first_name.text} {last_name.text}")
                    
                    # Parse journal
                    journal_elem = article_data.find('Journal/Title')
                    journal = journal_elem.text if journal_elem is not None else None
                    
                    # Parse abstract
                    abstract = None
                    abstract_elem = article_data.find('Abstract/AbstractText')
                    if abstract_elem is not None:
                        abstract = abstract_elem.text
                    
                    # Parse publication date - ensure it's always a string
                    pub_date = None
                    pub_date_elem = article_data.find('Journal/JournalIssue/PubDate')
                    if pub_date_elem is not None:
                        year_elem = pub_date_elem.find('Year')
                        if year_elem is not None and year_elem.text:
                            pub_date = str(year_elem.text)  # Ensure string format
                    
                    # Parse DOI
                    doi = None
                    for article_id in medline.findall('.//ArticleId'):
                        if article_id.get('IdType') == 'doi':
                            doi = article_id.text
                            break
                    
                    # Create URL
                    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None
                    
                    article = ArticleCreate(
                        doi=doi,
                        title=title,
                        authors=authors,
                        publication_date=ensure_string_date(pub_date),
                        journal=journal,
                        abstract=abstract,
                        url=url
                    )
                    articles.append(article)
                    
                except Exception as e:
                    logger.error(f"Error parsing PubMed article: {e}")
                    continue
            
            return articles
            
        except Exception as e:
            logger.error(f"Error parsing PubMed XML: {e}")
            return []

class SemanticScholarAPI:
    """Semantic Scholar API client"""
    def __init__(self):
        self.base_url = "https://api.semanticscholar.org/graph/v1"
        self.rate_limiter = RateLimiter(10.0)  # Conservative rate limit
        
    async def search(self, query: str, limit: int = 10) -> List[ArticleCreate]:
        """Search Semantic Scholar for papers"""
        await self.rate_limiter.wait()
        
        async with aiohttp.ClientSession() as session:
            try:
                search_url = f"{self.base_url}/paper/search"
                params = {
                    'query': query,
                    'limit': limit,
                    'fields': 'paperId,title,authors,year,journal,abstract,url,externalIds'
                }
                
                async with session.get(search_url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"Semantic Scholar search failed with status {response.status}")
                        return []
                    
                    data = await response.json()
                    return self._parse_papers(data.get('data', []))
            
            except Exception as e:
                logger.error(f"Semantic Scholar API error: {e}")
                return []
    
    def _parse_papers(self, papers: List[Dict]) -> List[ArticleCreate]:
        """Parse papers from Semantic Scholar response"""
        articles = []
        
        for paper in papers:
            try:
                # Parse authors
                authors = []
                for author in paper.get('authors', []):
                    if author.get('name'):
                        authors.append(author['name'])
                
                # Parse publication date - ensure it's always a string
                pub_date = None
                year = paper.get('year')
                if year:
                    pub_date = str(year)  # Ensure string format
                
                # Parse DOI
                doi = None
                external_ids = paper.get('externalIds', {})
                if external_ids:
                    doi = external_ids.get('DOI')
                
                # Parse journal
                journal = None
                journal_info = paper.get('journal')
                if journal_info and isinstance(journal_info, dict):
                    journal = journal_info.get('name')
                
                article = ArticleCreate(
                    doi=doi,
                    title=paper.get('title', 'No title'),
                    authors=authors,
                    publication_date=ensure_string_date(pub_date),
                    journal=journal,
                    abstract=paper.get('abstract'),
                    url=paper.get('url')
                )
                articles.append(article)
                
            except Exception as e:
                logger.error(f"Error parsing Semantic Scholar paper: {e}")
                continue
        
        return articles

class ArxivAPI:
    """ArXiv API client"""
    def __init__(self):
        self.base_url = "http://export.arxiv.org/api/query"
        self.rate_limiter = RateLimiter(3.0)  # 3 requests per second
        
    async def search(self, query: str, limit: int = 10) -> List[ArticleCreate]:
        """Search ArXiv for papers"""
        await self.rate_limiter.wait()
        
        async with aiohttp.ClientSession() as session:
            try:
                params = {
                    'search_query': f'all:{query}',
                    'start': 0,
                    'max_results': limit,
                    'sortBy': 'relevance',
                    'sortOrder': 'descending'
                }
                
                async with session.get(self.base_url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"ArXiv search failed with status {response.status}")
                        return []
                    
                    xml_content = await response.text()
                    return self._parse_arxiv_xml(xml_content)
            
            except Exception as e:
                logger.error(f"ArXiv API error: {e}")
                return []
    
    def _parse_arxiv_xml(self, xml_content: str) -> List[ArticleCreate]:
        """Parse ArXiv XML response"""
        articles = []
        
        try:
            # Remove namespace for easier parsing
            xml_content = xml_content.replace('xmlns=', 'xmlnamespace=')
            root = ET.fromstring(xml_content)
            
            for entry in root.findall('entry'):
                try:
                    title_elem = entry.find('title')
                    title = title_elem.text.strip() if title_elem is not None else "No title"
                    
                    summary_elem = entry.find('summary')
                    summary = summary_elem.text.strip() if summary_elem is not None else None
                    
                    # Extract authors
                    authors = []
                    for author in entry.findall('author'):
                        name_elem = author.find('name')
                        if name_elem is not None:
                            authors.append(name_elem.text)
                    
                    # Extract URL
                    url = None
                    id_elem = entry.find('id')
                    if id_elem is not None:
                        url = id_elem.text
                    
                    # Extract publication date - ensure it's always a string
                    pub_date = ""
                    published = entry.find('published')
                    if published is not None and published.text:
                        pub_date = str(published.text[:4])  # Just the year as string
                    
                    article = ArticleCreate(
                        doi=None,  # ArXiv doesn't use DOIs
                        title=title,
                        abstract=summary,
                        authors=authors,
                        publication_date=ensure_string_date(pub_date),
                        journal="arXiv",
                        url=url
                    )
                    articles.append(article)
                    
                except Exception as e:
                    logger.error(f"Error parsing ArXiv entry: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error parsing ArXiv XML: {e}")
        
        return articles

class APIManager:
    """Unified API manager for all external sources"""
    def __init__(self):
        # Initialize individual API clients
        self.pubmed = PubMedAPI()
        self.semantic_scholar = SemanticScholarAPI()
        self.arxiv = ArxivAPI()
        
        # Track enabled APIs
        self.apis = {
            "pubmed": {"client": self.pubmed, "enabled": True},
            "semantic_scholar": {"client": self.semantic_scholar, "enabled": True},
            "arxiv": {"client": self.arxiv, "enabled": True}
        }
        
        logger.info(f"APIManager initialized with {len(self.apis)} APIs")
    
    async def search_all(self, query: str, limit: int = 10, offset: int = 0) -> List[ArticleCreate]:
        """Search all configured APIs"""
        all_articles = []
        
        # Calculate how many to get from each source
        enabled_apis = [name for name, config in self.apis.items() if config.get("enabled", True)]
        per_source_limit = max(limit // len(enabled_apis), 3) if enabled_apis else limit
        
        # Search each enabled API
        for api_name, api_config in self.apis.items():
            if not api_config.get("enabled", True):
                continue
                
            try:
                logger.info(f"Searching {api_name} for '{query}' (limit: {per_source_limit})")
                
                api_client = api_config["client"]
                articles = await api_client.search(query, per_source_limit)
                
                all_articles.extend(articles)
                logger.info(f"Retrieved {len(articles)} articles from {api_name}")
                
            except Exception as e:
                logger.error(f"Error searching {api_name}: {e}")
                continue
        
        # Remove duplicates by DOI and title
        unique_articles = []
        seen_dois = set()
        seen_titles = set()
        
        for article in all_articles:
            # Skip if we've seen this DOI before
            if article.doi and article.doi in seen_dois:
                continue
            
            # Skip if we've seen this exact title before
            title_lower = (article.title or "").lower().strip()
            if title_lower and title_lower in seen_titles:
                continue
            
            # Add to unique list
            unique_articles.append(article)
            if article.doi:
                seen_dois.add(article.doi)
            if title_lower:
                seen_titles.add(title_lower)
        
        # Apply offset and limit
        if offset > 0:
            unique_articles = unique_articles[offset:]
        
        result = unique_articles[:limit]
        logger.info(f"Returning {len(result)} unique articles after deduplication and pagination")
        return result
    
    async def close(self):
        """Close any active sessions"""
        # Individual API clients handle their own session management
        pass