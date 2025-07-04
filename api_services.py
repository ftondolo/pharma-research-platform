import aiohttp
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from models import APIArticle
import xml.etree.ElementTree as ET
import json
import os
from urllib.parse import quote

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
        
    async def search(self, query: str, limit: int = 10) -> List[APIArticle]:
        """Search PubMed for articles"""
        await self.rate_limiter.wait()
        
        async with aiohttp.ClientSession() as session:
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
                    return []
                
                search_xml = await response.text()
                pmids = self._parse_search_results(search_xml)
                
                if not pmids:
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
                        return []
                    
                    fetch_xml = await fetch_response.text()
                    return self._parse_articles(fetch_xml)
    
    def _parse_search_results(self, xml_content: str) -> List[str]:
        """Parse PMIDs from search results"""
        try:
            root = ET.fromstring(xml_content)
            pmids = []
            for id_elem in root.findall('.//Id'):
                pmids.append(id_elem.text)
            return pmids
        except:
            return []
    
    def _parse_articles(self, xml_content: str) -> List[APIArticle]:
        """Parse article details from XML"""
        try:
            root = ET.fromstring(xml_content)
            articles = []
            
            for article_elem in root.findall('.//PubmedArticle'):
                try:
                    medline = article_elem.find('MedlineCitation')
                    pmid = medline.find('PMID').text
                    
                    article_data = medline.find('Article')
                    title = article_data.find('ArticleTitle').text or ""
                    
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
                    journal = journal_elem.text if journal_elem is not None else ""
                    
                    # Parse abstract
                    abstract = ""
                    abstract_elem = article_data.find('Abstract/AbstractText')
                    if abstract_elem is not None:
                        abstract = abstract_elem.text or ""
                    
                    # Parse publication date
                    pub_date = None
                    pub_date_elem = article_data.find('Journal/JournalIssue/PubDate')
                    if pub_date_elem is not None:
                        year_elem = pub_date_elem.find('Year')
                        if year_elem is not None:
                            try:
                                pub_date = date(int(year_elem.text), 1, 1)
                            except:
                                pass
                    
                    # Parse DOI
                    doi = None
                    for article_id in article_data.findall('.//ArticleId'):
                        if article_id.get('IdType') == 'doi':
                            doi = article_id.text
                            break
                    
                    article = APIArticle(
                        id=pmid,
                        doi=doi,
                        title=title,
                        authors=authors,
                        publication_date=pub_date,
                        journal=journal,
                        abstract=abstract,
                        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                        source="pubmed"
                    )
                    articles.append(article)
                    
                except Exception as e:
                    continue  # Skip malformed articles
            
            return articles
            
        except Exception as e:
            return []

class SemanticScholarAPI:
    """Semantic Scholar API client"""
    def __init__(self):
        self.base_url = "https://api.semanticscholar.org/graph/v1"
        self.rate_limiter = RateLimiter(100.0)  # 100 requests per second
        
    async def search(self, query: str, limit: int = 10) -> List[APIArticle]:
        """Search Semantic Scholar for papers"""
        await self.rate_limiter.wait()
        
        async with aiohttp.ClientSession() as session:
            search_url = f"{self.base_url}/paper/search"
            params = {
                'query': query,
                'limit': limit,
                'fields': 'paperId,title,authors,year,journal,abstract,url,externalIds'
            }
            
            async with session.get(search_url, params=params) as response:
                if response.status != 200:
                    return []
                
                data = await response.json()
                return self._parse_papers(data.get('data', []))
    
    def _parse_papers(self, papers: List[Dict]) -> List[APIArticle]:
        """Parse papers from Semantic Scholar response"""
        articles = []
        
        for paper in papers:
            try:
                # Parse authors
                authors = []
                for author in paper.get('authors', []):
                    if author.get('name'):
                        authors.append(author['name'])
                
                # Parse publication date
                pub_date = None
                year = paper.get('year')
                if year:
                    try:
                        pub_date = date(int(year), 1, 1)
                    except:
                        pass
                
                # Parse DOI
                doi = None
                external_ids = paper.get('externalIds', {})
                if external_ids:
                    doi = external_ids.get('DOI')
                
                article = APIArticle(
                    id=paper['paperId'],
                    doi=doi,
                    title=paper.get('title', ''),
                    authors=authors,
                    publication_date=pub_date,
                    journal=paper.get('journal', {}).get('name', ''),
                    abstract=paper.get('abstract', ''),
                    url=paper.get('url', ''),
                    source="semantic_scholar"
                )
                articles.append(article)
                
            except Exception as e:
                continue  # Skip malformed papers
        
        return articles

class CrossRefAPI:
    """CrossRef API client"""
    def __init__(self):
        self.base_url = "https://api.crossref.org/works"
        self.rate_limiter = RateLimiter(50.0)  # Conservative rate limit
        
    async def search(self, query: str, limit: int = 10) -> List[APIArticle]:
        """Search CrossRef for works"""
        await self.rate_limiter.wait()
        
        async with aiohttp.ClientSession() as session:
            params = {
                'query': query,
                'rows': limit,
                'select': 'DOI,title,author,published-print,container-title,abstract,URL'
            }
            
            async with session.get(self.base_url, params=params) as response:
                if response.status != 200:
                    return []
                
                data = await response.json()
                return self._parse_works(data.get('message', {}).get('items', []))
    
    def _parse_works(self, works: List[Dict]) -> List[APIArticle]:
        """Parse works from CrossRef response"""
        articles = []
        
        for work in works:
            try:
                # Parse authors
                authors = []
                for author in work.get('author', []):
                    given = author.get('given', '')
                    family = author.get('family', '')
                    if given and family:
                        authors.append(f"{given} {family}")
                
                # Parse publication date
                pub_date = None
                published = work.get('published-print', {}).get('date-parts', [[]])
                if published and published[0]:
                    try:
                        pub_date = date(published[0][0], published[0][1] if len(published[0]) > 1 else 1, 1)
                    except:
                        pass
                
                # Parse title
                title = ""
                if work.get('title'):
                    title = work['title'][0] if isinstance(work['title'], list) else work['title']
                
                # Parse journal
                journal = ""
                if work.get('container-title'):
                    journal = work['container-title'][0] if isinstance(work['container-title'], list) else work['container-title']
                
                article = APIArticle(
                    id=work['DOI'],
                    doi=work['DOI'],
                    title=title,
                    authors=authors,
                    publication_date=pub_date,
                    journal=journal,
                    abstract=work.get('abstract', ''),
                    url=work.get('URL', ''),
                    source="crossref"
                )
                articles.append(article)
                
            except Exception as e:
                continue  # Skip malformed works
        
        return articles

class APIManager:
    """Unified API manager for all external sources"""
    def __init__(self):
        self.pubmed = PubMedAPI()
        self.semantic_scholar = SemanticScholarAPI()
        self.crossref = CrossRefAPI()
        
    async def search_all(self, query: str, limit: int = 10) -> List[APIArticle]:
        """Search all APIs concurrently"""
        # Distribute limit across APIs
        per_api_limit = max(1, limit // 3)
        
        tasks = [
            self.pubmed.search(query, per_api_limit),
            self.semantic_scholar.search(query, per_api_limit),
            self.crossref.search(query, per_api_limit)
        ]
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combine results and deduplicate by DOI
            all_articles = []
            seen_dois = set()
            
            for result in results:
                if isinstance(result, Exception):
                    continue  # Skip failed API calls
                    
                for article in result:
                    # Deduplicate by DOI if available
                    if article.doi and article.doi in seen_dois:
                        continue
                    if article.doi:
                        seen_dois.add(article.doi)
                    
                    all_articles.append(article)
            
            return all_articles[:limit]
            
        except Exception as e:
            return []
