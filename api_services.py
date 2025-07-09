# enhanced_api_services.py - Maximum abstract coverage from multiple free sources

import aiohttp
import asyncio
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Set
import logging
import json
import re
from urllib.parse import quote, urlencode
from datetime import datetime
import hashlib

from models import ArticleCreate

logger = logging.getLogger(__name__)

def ensure_string_date(date_value):
    """Ensure date value is a string"""
    if date_value is None:
        return None
    if isinstance(date_value, str):
        return date_value.strip() if date_value.strip() else None
    if hasattr(date_value, 'year'):
        return str(date_value.year)
    if isinstance(date_value, int):
        if 1900 <= date_value <= 2100:
            return str(date_value)
    try:
        return str(date_value)
    except:
        return None

class RateLimiter:
    """Enhanced rate limiter for API calls"""
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
    """Enhanced PubMed E-utilities API client"""
    def __init__(self):
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.rate_limiter = RateLimiter(3.0)
        
    async def search(self, query: str, limit: int = 20, offset: int = 0) -> List[ArticleCreate]:
        """Search PubMed with enhanced abstract retrieval"""
        await self.rate_limiter.wait()
        
        async with aiohttp.ClientSession() as session:
            try:
                # Enhanced search with filters for articles with abstracts
                enhanced_query = f"({query}) AND hasabstract[text]"
                
                search_url = f"{self.base_url}/esearch.fcgi"
                search_params = {
                    'db': 'pubmed',
                    'term': enhanced_query,
                    'retmax': limit,
                    'retstart': offset,
                    'retmode': 'xml',
                    'sort': 'relevance'
                }
                
                async with session.get(search_url, params=search_params) as response:
                    if response.status != 200:
                        logger.warning(f"PubMed search failed with status {response.status}")
                        return []
                    
                    search_xml = await response.text()
                    pmids = self._parse_search_results(search_xml)
                    
                    if not pmids:
                        logger.info("No PMIDs found from PubMed search")
                        return []
                    
                    # Get detailed info with abstracts
                    await self.rate_limiter.wait()
                    fetch_url = f"{self.base_url}/efetch.fcgi"
                    fetch_params = {
                        'db': 'pubmed',
                        'id': ','.join(pmids),
                        'retmode': 'xml',
                        'rettype': 'abstract'
                    }
                    
                    async with session.get(fetch_url, params=fetch_params) as fetch_response:
                        if fetch_response.status != 200:
                            logger.warning(f"PubMed fetch failed with status {fetch_response.status}")
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
        """Enhanced article parsing with focus on abstracts"""
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
                    
                    # Enhanced abstract parsing - handle structured abstracts
                    abstract = self._extract_abstract(article_data)
                    
                    # Skip articles without abstracts (our focus)
                    if not abstract or len(abstract.strip()) < 50:
                        continue
                    
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
                    if journal_elem is None:
                        journal_elem = article_data.find('Journal/ISOAbbreviation')
                    journal = journal_elem.text if journal_elem is not None else None
                    
                    # Parse publication date
                    pub_date = self._extract_publication_date(article_data)
                    
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
    
    def _extract_abstract(self, article_data) -> Optional[str]:
        """Extract abstract with support for structured abstracts"""
        abstract_parts = []
        
        # Handle structured abstracts
        abstract_elem = article_data.find('Abstract')
        if abstract_elem is not None:
            for abstract_text in abstract_elem.findall('AbstractText'):
                label = abstract_text.get('Label', '')
                text = abstract_text.text or ''
                
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)
        
        if abstract_parts:
            return ' '.join(abstract_parts).strip()
        
        # Fallback to simple abstract
        simple_abstract = article_data.find('Abstract/AbstractText')
        if simple_abstract is not None and simple_abstract.text:
            return simple_abstract.text.strip()
        
        return None
    
    def _extract_publication_date(self, article_data) -> Optional[str]:
        """Extract publication date with multiple fallbacks"""
        # Try journal issue date first
        pub_date_elem = article_data.find('Journal/JournalIssue/PubDate')
        if pub_date_elem is not None:
            year_elem = pub_date_elem.find('Year')
            if year_elem is not None and year_elem.text:
                return str(year_elem.text)
        
        # Try article date
        date_elem = article_data.find('ArticleDate')
        if date_elem is not None:
            year_elem = date_elem.find('Year')
            if year_elem is not None and year_elem.text:
                return str(year_elem.text)
        
        return None

class EuropePMCAPI:
    """Europe PMC REST API client"""
    def __init__(self):
        self.base_url = "https://www.ebi.ac.uk/europepmc/webservices/rest"
        self.rate_limiter = RateLimiter(10.0)
        
    async def search(self, query: str, limit: int = 20, offset: int = 0) -> List[ArticleCreate]:
        """Search Europe PMC for articles with abstracts"""
        await self.rate_limiter.wait()
        
        async with aiohttp.ClientSession() as session:
            try:
                # Enhanced query to prioritize articles with abstracts
                enhanced_query = f"({query}) AND HAS_ABSTRACT:y"
                
                search_url = f"{self.base_url}/search"
                params = {
                    'query': enhanced_query,
                    'resultType': 'core',
                    'cursorMark': '*',
                    'pageSize': limit,
                    'format': 'json'
                }
                
                async with session.get(search_url, params=params) as response:
                    if response.status != 200:
                        logger.warning(f"Europe PMC search failed with status {response.status}")
                        return []
                    
                    data = await response.json()
                    return self._parse_results(data)
            
            except Exception as e:
                logger.error(f"Europe PMC API error: {e}")
                return []
    
    def _parse_results(self, data: Dict) -> List[ArticleCreate]:
        """Parse Europe PMC results"""
        articles = []
        
        result_list = data.get('resultList', {})
        results = result_list.get('result', [])
        
        for result in results:
            try:
                title = result.get('title', 'No title')
                abstract = result.get('abstractText', '')
                
                # Skip if no substantial abstract
                if not abstract or len(abstract.strip()) < 50:
                    continue
                
                # Parse authors
                authors = []
                author_string = result.get('authorString', '')
                if author_string:
                    authors = [name.strip() for name in author_string.split(',')]
                
                # Get other fields
                doi = result.get('doi')
                journal = result.get('journalTitle') or result.get('journalName')
                pub_year = result.get('pubYear')
                pmid = result.get('pmid')
                
                # Create URL
                url = None
                if pmid:
                    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                elif doi:
                    url = f"https://doi.org/{doi}"
                
                article = ArticleCreate(
                    doi=doi,
                    title=title,
                    authors=authors,
                    publication_date=ensure_string_date(pub_year),
                    journal=journal,
                    abstract=abstract,
                    url=url
                )
                articles.append(article)
                
            except Exception as e:
                logger.error(f"Error parsing Europe PMC result: {e}")
                continue
        
        return articles

class ClinicalTrialsAPI:
    """ClinicalTrials.gov API client"""
    def __init__(self):
        self.base_url = "https://clinicaltrials.gov/api/query"
        self.rate_limiter = RateLimiter(5.0)
        
    async def search(self, query: str, limit: int = 20, offset: int = 0) -> List[ArticleCreate]:
        """Search ClinicalTrials.gov for trials with detailed summaries"""
        await self.rate_limiter.wait()
        
        async with aiohttp.ClientSession() as session:
            try:
                params = {
                    'expr': query,
                    'min_rnk': offset + 1,
                    'max_rnk': offset + limit,
                    'fmt': 'json',
                    'fields': 'NCTId,BriefTitle,DetailedDescription,BriefSummary,StudyType,Phase,Condition,InterventionName,StartDate,CompletionDate'
                }
                
                async with session.get(self.base_url + '/study_fields', params=params) as response:
                    if response.status != 200:
                        logger.warning(f"ClinicalTrials.gov search failed with status {response.status}")
                        return []
                    
                    data = await response.json()
                    return self._parse_trials(data)
            
            except Exception as e:
                logger.error(f"ClinicalTrials.gov API error: {e}")
                return []
    
    def _parse_trials(self, data: Dict) -> List[ArticleCreate]:
        """Parse clinical trials data"""
        articles = []
        
        studies = data.get('StudyFieldsResponse', {}).get('StudyFields', [])
        
        for study in studies:
            try:
                # Extract fields
                fields = {}
                for field_name, field_values in study.items():
                    if field_values:
                        fields[field_name] = field_values[0] if isinstance(field_values, list) else field_values
                
                nct_id = fields.get('NCTId', '')
                title = fields.get('BriefTitle', 'No title')
                
                # Combine description and summary for abstract
                description = fields.get('DetailedDescription', '')
                summary = fields.get('BriefSummary', '')
                
                abstract_parts = []
                if summary:
                    abstract_parts.append(f"Brief Summary: {summary}")
                if description:
                    abstract_parts.append(f"Detailed Description: {description}")
                
                abstract = ' '.join(abstract_parts) if abstract_parts else None
                
                # Skip if no substantial abstract
                if not abstract or len(abstract.strip()) < 100:
                    continue
                
                # Other fields
                study_type = fields.get('StudyType', '')
                phase = fields.get('Phase', '')
                condition = fields.get('Condition', '')
                intervention = fields.get('InterventionName', '')
                start_date = fields.get('StartDate', '')
                
                # Enhance title with study info
                title_parts = [title]
                if study_type:
                    title_parts.append(f"({study_type})")
                if phase:
                    title_parts.append(f"Phase {phase}")
                enhanced_title = ' '.join(title_parts)
                
                # URL
                url = f"https://clinicaltrials.gov/ct2/show/{nct_id}" if nct_id else None
                
                article = ArticleCreate(
                    doi=None,
                    title=enhanced_title,
                    authors=[],
                    publication_date=ensure_string_date(start_date[:4] if start_date else None),
                    journal="ClinicalTrials.gov",
                    abstract=abstract,
                    url=url
                )
                articles.append(article)
                
            except Exception as e:
                logger.error(f"Error parsing clinical trial: {e}")
                continue
        
        return articles

class SemanticScholarAPI:
    """Enhanced Semantic Scholar API client"""
    def __init__(self):
        self.base_url = "https://api.semanticscholar.org/graph/v1"
        self.rate_limiter = RateLimiter(10.0)
        
    async def search(self, query: str, limit: int = 20, offset: int = 0) -> List[ArticleCreate]:
        """Search Semantic Scholar prioritizing papers with abstracts"""
        await self.rate_limiter.wait()
        
        async with aiohttp.ClientSession() as session:
            try:
                search_url = f"{self.base_url}/paper/search"
                params = {
                    'query': query,
                    'limit': limit,
                    'offset': offset,
                    'fields': 'paperId,title,authors,year,journal,abstract,url,externalIds,publicationDate,citationCount'
                }
                
                async with session.get(search_url, params=params) as response:
                    if response.status != 200:
                        logger.warning(f"Semantic Scholar search failed with status {response.status}")
                        return []
                    
                    data = await response.json()
                    papers = data.get('data', [])
                    
                    # Filter for papers with substantial abstracts
                    filtered_papers = []
                    for paper in papers:
                        abstract = paper.get('abstract', '')
                        if abstract and len(abstract.strip()) >= 100:
                            filtered_papers.append(paper)
                    
                    return self._parse_papers(filtered_papers)
            
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
                
                # Parse publication date
                pub_date = None
                year = paper.get('year')
                pub_date_str = paper.get('publicationDate')
                if pub_date_str:
                    pub_date = pub_date_str[:4]  # Extract year
                elif year:
                    pub_date = str(year)
                
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
                
                abstract = paper.get('abstract', '')
                
                # Skip if abstract is too short
                if not abstract or len(abstract.strip()) < 100:
                    continue
                
                article = ArticleCreate(
                    doi=doi,
                    title=paper.get('title', 'No title'),
                    authors=authors,
                    publication_date=ensure_string_date(pub_date),
                    journal=journal,
                    abstract=abstract,
                    url=paper.get('url')
                )
                articles.append(article)
                
            except Exception as e:
                logger.error(f"Error parsing Semantic Scholar paper: {e}")
                continue
        
        return articles

class ArxivAPI:
    """Enhanced ArXiv API client"""
    def __init__(self):
        self.base_url = "http://export.arxiv.org/api/query"
        self.rate_limiter = RateLimiter(3.0)
        
    async def search(self, query: str, limit: int = 20, offset: int = 0) -> List[ArticleCreate]:
        """Search ArXiv for papers with substantial abstracts"""
        await self.rate_limiter.wait()
        
        async with aiohttp.ClientSession() as session:
            try:
                params = {
                    'search_query': f'all:{query}',
                    'start': offset,
                    'max_results': limit,
                    'sortBy': 'relevance',
                    'sortOrder': 'descending'
                }
                
                async with session.get(self.base_url, params=params) as response:
                    if response.status != 200:
                        logger.warning(f"ArXiv search failed with status {response.status}")
                        return []
                    
                    xml_content = await response.text()
                    return self._parse_arxiv_xml(xml_content)
            
            except Exception as e:
                logger.error(f"ArXiv API error: {e}")
                return []
    
    def _parse_arxiv_xml(self, xml_content: str) -> List[ArticleCreate]:
        """Parse ArXiv XML response with focus on abstracts"""
        articles = []
        
        try:
            xml_content = xml_content.replace('xmlns=', 'xmlnamespace=')
            root = ET.fromstring(xml_content)
            
            for entry in root.findall('entry'):
                try:
                    title_elem = entry.find('title')
                    title = title_elem.text.strip() if title_elem is not None else "No title"
                    
                    summary_elem = entry.find('summary')
                    summary = summary_elem.text.strip() if summary_elem is not None else None
                    
                    # Skip if abstract is too short
                    if not summary or len(summary.strip()) < 100:
                        continue
                    
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
                    
                    # Extract publication date
                    pub_date = ""
                    published = entry.find('published')
                    if published is not None and published.text:
                        pub_date = str(published.text[:4])
                    
                    article = ArticleCreate(
                        doi=None,
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

class EnhancedAPIManager:
    """Enhanced API manager optimized for finding abstracts"""
    def __init__(self):
        # Initialize all API clients
        self.pubmed = PubMedAPI()
        self.europe_pmc = EuropePMCAPI()
        self.clinical_trials = ClinicalTrialsAPI()
        self.semantic_scholar = SemanticScholarAPI()
        self.arxiv = ArxivAPI()
        
        # Configure API priorities and strategies
        self.apis = {
            "pubmed": {
                "client": self.pubmed, 
                "enabled": True, 
                "priority": 1,
                "good_for": ["medical", "pharmaceutical", "clinical", "biomedical"]
            },
            "europe_pmc": {
                "client": self.europe_pmc, 
                "enabled": True, 
                "priority": 2,
                "good_for": ["medical", "life sciences", "biomedical"]
            },
            "semantic_scholar": {
                "client": self.semantic_scholar, 
                "enabled": True, 
                "priority": 3,
                "good_for": ["general", "computer science", "AI", "technology"]
            },
            "clinical_trials": {
                "client": self.clinical_trials, 
                "enabled": True, 
                "priority": 4,
                "good_for": ["clinical", "trials", "drug", "treatment", "therapy"]
            },
            "arxiv": {
                "client": self.arxiv, 
                "enabled": True, 
                "priority": 5,
                "good_for": ["research", "preprint", "computational", "AI"]
            }
        }
        
        logger.info(f"Enhanced APIManager initialized with {len(self.apis)} specialized APIs")
    
    def _categorize_query(self, query: str) -> List[str]:
        """Categorize query to optimize API selection"""
        query_lower = query.lower()
        categories = []
        
        medical_terms = ["cancer", "drug", "treatment", "therapy", "clinical", "patient", "disease", "medical", "pharmaceutical", "medicine"]
        clinical_terms = ["trial", "study", "phase", "efficacy", "safety", "randomized", "placebo"]
        tech_terms = ["AI", "machine learning", "algorithm", "computational", "artificial intelligence"]
        
        if any(term in query_lower for term in medical_terms):
            categories.append("medical")
        if any(term in query_lower for term in clinical_terms):
            categories.append("clinical")
        if any(term in query_lower for term in tech_terms):
            categories.append("technology")
        
        return categories if categories else ["general"]
    
    async def search_all(self, query: str, limit: int = 20, offset: int = 0) -> List[ArticleCreate]:
        """Enhanced search across all APIs with intelligent prioritization"""
        query_categories = self._categorize_query(query)
        logger.info(f"Query categories: {query_categories}")
        
        # Sort APIs by relevance to query
        relevant_apis = []
        for api_name, api_config in self.apis.items():
            if not api_config.get("enabled", True):
                continue
            
            relevance_score = 0
            good_for = api_config.get("good_for", [])
            
            for category in query_categories:
                if category in good_for:
                    relevance_score += 10
                if "general" in good_for:
                    relevance_score += 1
            
            # Add priority bonus (lower priority number = higher relevance)
            relevance_score += (10 - api_config.get("priority", 5))
            
            relevant_apis.append((api_name, api_config, relevance_score))
        
        # Sort by relevance score (descending)
        relevant_apis.sort(key=lambda x: x[2], reverse=True)
        
        all_articles = []
        seen_identifiers: Set[str] = set()
        
        # Calculate per-API limits
        active_apis = len(relevant_apis)
        base_per_api = max(limit // active_apis, 5)
        
        for api_name, api_config, score in relevant_apis:
            try:
                # Adjust limit based on API performance and relevance
                api_limit = base_per_api
                if score > 15:  # Highly relevant
                    api_limit = int(base_per_api * 1.5)
                
                logger.info(f"Searching {api_name} (relevance: {score}) for '{query}' (limit: {api_limit})")
                
                api_client = api_config["client"]
                articles = await api_client.search(query, api_limit, offset)
                
                # Deduplicate and add articles
                unique_articles = []
                for article in articles:
                    # Create identifier for deduplication
                    identifier = self._create_identifier(article)
                    
                    if identifier not in seen_identifiers:
                        seen_identifiers.add(identifier)
                        unique_articles.append(article)
                
                all_articles.extend(unique_articles)
                logger.info(f"Retrieved {len(unique_articles)} unique articles from {api_name}")
                
                # Early stopping if we have enough good articles
                if len(all_articles) >= limit * 1.5:
                    break
                
            except Exception as e:
                logger.error(f"Error searching {api_name}: {e}")
                continue
        
        # Final deduplication and quality filtering
        final_articles = self._final_quality_filter(all_articles)
        
        # Sort by quality score
        final_articles.sort(key=self._calculate_quality_score, reverse=True)
        
        result = final_articles[:limit]
        logger.info(f"Returning {len(result)} high-quality articles with abstracts")
        return result
    
    def _create_identifier(self, article: ArticleCreate) -> str:
        """Create unique identifier for deduplication"""
        # Use DOI if available
        if article.doi:
            return f"doi:{article.doi.lower()}"
        
        # Use title hash
        if article.title:
            title_clean = re.sub(r'[^\w\s]', '', article.title.lower()).strip()
            title_hash = hashlib.md5(title_clean.encode()).hexdigest()[:12]
            return f"title:{title_hash}"
        
        return f"fallback:{hash(str(article))}"
    
    def _calculate_quality_score(self, article: ArticleCreate) -> float:
        """Calculate quality score for article ranking"""
        score = 0
        
        # Abstract quality (most important for our use case)
        if article.abstract:
            abstract_len = len(article.abstract.strip())
            if abstract_len >= 500:
                score += 50
            elif abstract_len >= 200:
                score += 30
            elif abstract_len >= 100:
                score += 15
            else:
                score += 5
        
        # Has DOI
        if article.doi:
            score += 10
        
        # Has authors
        if article.authors and len(article.authors) > 0:
            score += 5
        
        # Has journal
        if article.journal:
            score += 5
        
        # Recent publication
        if article.publication_date:
            try:
                year = int(article.publication_date[:4])
                if year >= 2020:
                    score += 10
                elif year >= 2015:
                    score += 5
            except:
                pass
        
        return score
    
    def _final_quality_filter(self, articles: List[ArticleCreate]) -> List[ArticleCreate]:
        """Apply final quality filters"""
        filtered = []
        
        for article in articles:
            # Must have substantial abstract
            if not article.abstract or len(article.abstract.strip()) < 50:
                continue
            
            # Must have reasonable title
            if not article.title or len(article.title.strip()) < 10:
                continue
            
            filtered.append(article)
        
        return filtered
    
    async def close(self):
        """Close any active sessions"""
        pass

# Create singleton instance
enhanced_api_manager = EnhancedAPIManager()