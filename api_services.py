# enhanced_api_services.py - Enhanced with direct HTML scraping for better data extraction

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
from bs4 import BeautifulSoup
import ssl

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

class PubMedHTMLScraper:
    """Direct HTML scraper for PubMed web pages - gets better data than XML API"""
    def __init__(self):
        self.base_url = "https://pubmed.ncbi.nlm.nih.gov"
        self.search_url = "https://pubmed.ncbi.nlm.nih.gov"
        self.rate_limiter = RateLimiter(2.0)  # Be respectful to PubMed
        
    async def search_and_scrape(self, query: str, limit: int = 20, offset: int = 0) -> List[ArticleCreate]:
        """Search PubMed and scrape individual article pages for complete data"""
        # First get PMIDs from search
        pmids = await self._search_pmids(query, limit, offset)
        if not pmids:
            return []
        
        # Then scrape each article page
        articles = []
        for pmid in pmids[:limit]:
            try:
                await self.rate_limiter.wait()
                article = await self._scrape_article_page(pmid)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.error(f"Error scraping PMID {pmid}: {e}")
                continue
        
        return articles
    
    async def _search_pmids(self, query: str, limit: int, offset: int) -> List[str]:
        """Get PMIDs from PubMed search"""
        await self.rate_limiter.wait()
        
        connector = aiohttp.TCPConnector(ssl=ssl.create_default_context())
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                # Use the search interface to get PMIDs
                search_params = {
                    'term': f"({query}) AND hasabstract[text]",
                    'size': limit,
                    'sort': 'relevance'
                }
                
                async with session.get(self.search_url, params=search_params) as response:
                    if response.status != 200:
                        logger.warning(f"PubMed search failed with status {response.status}")
                        return []
                    
                    html = await response.text()
                    return self._extract_pmids_from_search(html)
            
            except Exception as e:
                logger.error(f"Error searching PubMed: {e}")
                return []
    
    def _extract_pmids_from_search(self, html: str) -> List[str]:
        """Extract PMIDs from search results page"""
        pmids = []
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Look for PMID patterns in various elements
            # Method 1: Look for data-article-id attributes
            for element in soup.find_all(attrs={'data-article-id': True}):
                pmid = element.get('data-article-id')
                if pmid and pmid.isdigit():
                    pmids.append(pmid)
            
            # Method 2: Look for PMID links
            for link in soup.find_all('a', href=re.compile(r'/(\d{8,})/?')):
                match = re.search(r'/(\d{8,})/?', link.get('href', ''))
                if match:
                    pmids.append(match.group(1))
            
            # Method 3: Look for PMID text patterns
            pmid_pattern = re.compile(r'PMID:\s*(\d{8,})')
            matches = pmid_pattern.findall(html)
            pmids.extend(matches)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_pmids = []
            for pmid in pmids:
                if pmid not in seen:
                    seen.add(pmid)
                    unique_pmids.append(pmid)
            
            logger.info(f"Extracted {len(unique_pmids)} PMIDs from search")
            return unique_pmids
            
        except Exception as e:
            logger.error(f"Error extracting PMIDs: {e}")
            return []
    
    async def _scrape_article_page(self, pmid: str) -> Optional[ArticleCreate]:
        """Scrape individual PubMed article page for complete data"""
        url = f"{self.base_url}/{pmid}/"
        
        connector = aiohttp.TCPConnector(ssl=ssl.create_default_context())
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch PMID {pmid}: status {response.status}")
                        return None
                    
                    html = await response.text()
                    return self._parse_article_html(html, pmid, url)
            
            except Exception as e:
                logger.error(f"Error fetching PMID {pmid}: {e}")
                return None
    
    def _parse_article_html(self, html: str, pmid: str, url: str) -> Optional[ArticleCreate]:
        """Parse PubMed article HTML for comprehensive data extraction"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract title
            title = self._extract_title(soup)
            
            # Extract abstract - this is the key improvement
            abstract = self._extract_abstract(soup)
            
            # Skip if no substantial abstract
            if not abstract or len(abstract.strip()) < 50:
                logger.info(f"Skipping PMID {pmid} - no substantial abstract")
                return None
            
            # Extract authors
            authors = self._extract_authors(soup)
            
            # Extract publication info
            journal, pub_date = self._extract_publication_info(soup)
            
            # Extract DOI
            doi = self._extract_doi(soup)
            
            article = ArticleCreate(
                doi=doi,
                title=title,
                authors=authors,
                publication_date=ensure_string_date(pub_date),
                journal=journal,
                abstract=abstract,
                url=url
            )
            
            logger.info(f"Successfully parsed PMID {pmid}")
            return article
            
        except Exception as e:
            logger.error(f"Error parsing article HTML for PMID {pmid}: {e}")
            return None
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract article title"""
        # Try multiple selectors
        selectors = [
            'h1.heading-title',
            '.heading-title',
            'h1',
            '[data-title]'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text(strip=True)
                if title and len(title) > 10:
                    return title
        
        return "No title available"
    
    def _extract_abstract(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract comprehensive abstract from PubMed page"""
        abstract_parts = []
        
        # Find the abstract section
        abstract_section = soup.find('div', {'id': 'abstract'}) or soup.find('div', class_='abstract')
        
        if abstract_section:
            # Handle structured abstracts with sub-titles
            abstract_content = abstract_section.find('div', class_='abstract-content')
            if abstract_content:
                for paragraph in abstract_content.find_all('p'):
                    # Check for sub-titles
                    subtitle = paragraph.find('strong', class_='sub-title')
                    if subtitle:
                        subtitle_text = subtitle.get_text(strip=True)
                        # Get the text after the subtitle
                        para_text = paragraph.get_text(strip=True)
                        # Remove the subtitle from the beginning
                        para_text = para_text.replace(subtitle_text, '', 1).strip()
                        if para_text:
                            abstract_parts.append(f"{subtitle_text} {para_text}")
                    else:
                        para_text = paragraph.get_text(strip=True)
                        if para_text:
                            abstract_parts.append(para_text)
            else:
                # Simple abstract without structured content
                para_text = abstract_section.get_text(strip=True)
                if para_text:
                    abstract_parts.append(para_text)
        
        if abstract_parts:
            return ' '.join(abstract_parts)
        
        # Fallback: look for any element containing abstract
        fallback_selectors = [
            '.abstract-text',
            '[id*="abstract"]',
            '[class*="abstract"]'
        ]
        
        for selector in fallback_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if text and len(text) > 100:
                    return text
        
        return None
    
    def _extract_authors(self, soup: BeautifulSoup) -> List[str]:
        """Extract authors with improved parsing"""
        authors = []
        
        # Method 1: Look for authors in the authors list
        authors_section = soup.find('div', class_='authors')
        if authors_section:
            author_links = authors_section.find_all('a', class_='full-name')
            for link in author_links:
                author_name = link.get_text(strip=True)
                if author_name:
                    authors.append(author_name)
        
        # Method 2: Look for inline authors
        if not authors:
            inline_authors = soup.find('div', class_='inline-authors')
            if inline_authors:
                author_elements = inline_authors.find_all('a', class_='full-name')
                for element in author_elements:
                    author_name = element.get_text(strip=True)
                    if author_name:
                        authors.append(author_name)
        
        # Method 3: Look in expanded authors section
        if not authors:
            expanded_authors = soup.find('div', class_='expanded-authors')
            if expanded_authors:
                author_elements = expanded_authors.find_all('a', class_='full-name')
                for element in author_elements:
                    author_name = element.get_text(strip=True)
                    if author_name:
                        authors.append(author_name)
        
        # Method 4: Fallback - look for any author-like patterns
        if not authors:
            author_patterns = soup.find_all(text=re.compile(r'[A-Z][a-z]+ [A-Z][A-Z]?[a-z]*'))
            for pattern in author_patterns[:10]:  # Limit to avoid false matches
                clean_name = pattern.strip()
                if len(clean_name.split()) == 2 and clean_name not in authors:
                    authors.append(clean_name)
        
        return authors[:20]  # Limit to reasonable number
    
    def _extract_publication_info(self, soup: BeautifulSoup) -> tuple[Optional[str], Optional[str]]:
        """Extract journal and publication date"""
        journal = None
        pub_date = None
        
        # Extract journal
        journal_selectors = [
            'button.journal-actions-trigger',
            '.journal-actions-trigger',
            '.article-source',
            '[class*="journal"]'
        ]
        
        for selector in journal_selectors:
            element = soup.select_one(selector)
            if element:
                journal_text = element.get_text(strip=True)
                if journal_text and len(journal_text) > 2 and len(journal_text) < 100:
                    journal = journal_text
                    break
        
        # Extract publication date
        # Look for citation information
        citation_selectors = [
            '.article-source .cit',
            '.cit',
            '.docsum-journal-citation',
            '.short-citation'
        ]
        
        for selector in citation_selectors:
            element = soup.select_one(selector)
            if element:
                citation_text = element.get_text(strip=True)
                # Extract year from citation like "2025 Feb;31(2):250-257"
                year_match = re.search(r'(\d{4})', citation_text)
                if year_match:
                    pub_date = year_match.group(1)
                    break
        
        # Fallback: look for secondary date (Epub date)
        if not pub_date:
            epub_element = soup.find('span', class_='secondary-date')
            if epub_element:
                epub_text = epub_element.get_text(strip=True)
                year_match = re.search(r'(\d{4})', epub_text)
                if year_match:
                    pub_date = year_match.group(1)
        
        return journal, pub_date
    
    def _extract_doi(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract DOI"""
        # Method 1: Look for DOI in citation
        doi_selectors = [
            '.citation-doi',
            '[class*="doi"]'
        ]
        
        for selector in doi_selectors:
            element = soup.select_one(selector)
            if element:
                doi_text = element.get_text(strip=True)
                # Extract DOI pattern
                doi_match = re.search(r'doi:\s*(10\.\S+)', doi_text)
                if doi_match:
                    return doi_match.group(1)
        
        # Method 2: Look for DOI links
        doi_links = soup.find_all('a', href=re.compile(r'doi\.org'))
        for link in doi_links:
            href = link.get('href', '')
            doi_match = re.search(r'doi\.org/(10\.\S+)', href)
            if doi_match:
                return doi_match.group(1)
        
        # Method 3: Look for DOI in identifiers
        identifiers = soup.find('ul', class_='identifiers')
        if identifiers:
            doi_link = identifiers.find('a', href=re.compile(r'doi\.org'))
            if doi_link:
                doi_text = doi_link.get_text(strip=True)
                if doi_text.startswith('10.'):
                    return doi_text
        
        return None

class EnhancedPubMedAPI:
    """Enhanced PubMed API that combines XML API with HTML scraping"""
    def __init__(self):
        self.xml_api_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.html_scraper = PubMedHTMLScraper()
        self.rate_limiter = RateLimiter(2.0)
        
    async def search(self, query: str, limit: int = 20, offset: int = 0) -> List[ArticleCreate]:
        """Search using hybrid approach: XML API + HTML scraping for best results"""
        
        # Try HTML scraping first for better data quality
        logger.info(f"Attempting HTML scraping for query: '{query}'")
        html_articles = await self.html_scraper.search_and_scrape(query, limit, offset)
        
        if html_articles and len(html_articles) >= limit // 2:
            logger.info(f"HTML scraping successful: {len(html_articles)} articles")
            return html_articles[:limit]
        
        # Fallback to XML API if HTML scraping fails or returns few results
        logger.info("Falling back to XML API")
        xml_articles = await self._search_xml_api(query, limit, offset)
        
        # Combine results, preferring HTML scraped data
        combined = html_articles + xml_articles
        
        # Deduplicate
        seen_titles = set()
        unique_articles = []
        for article in combined:
            title_key = article.title.lower().strip()
            if title_key not in seen_titles and len(title_key) > 10:
                seen_titles.add(title_key)
                unique_articles.append(article)
        
        return unique_articles[:limit]
    
    async def _search_xml_api(self, query: str, limit: int, offset: int) -> List[ArticleCreate]:
        """Fallback XML API search (existing implementation)"""
        await self.rate_limiter.wait()
        
        async with aiohttp.ClientSession() as session:
            try:
                # Enhanced search with filters for articles with abstracts
                enhanced_query = f"({query}) AND hasabstract[text]"
                
                search_url = f"{self.xml_api_url}/esearch.fcgi"
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
                        return []
                    
                    search_xml = await response.text()
                    pmids = self._parse_search_results(search_xml)
                    
                    if not pmids:
                        return []
                    
                    # Get detailed info with abstracts
                    await self.rate_limiter.wait()
                    fetch_url = f"{self.xml_api_url}/efetch.fcgi"
                    fetch_params = {
                        'db': 'pubmed',
                        'id': ','.join(pmids),
                        'retmode': 'xml',
                        'rettype': 'abstract'
                    }
                    
                    async with session.get(fetch_url, params=fetch_params) as fetch_response:
                        if fetch_response.status != 200:
                            return []
                        
                        fetch_xml = await fetch_response.text()
                        return self._parse_articles(fetch_xml)
            
            except Exception as e:
                logger.error(f"XML API error: {e}")
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
            logger.error(f"Error parsing search results: {e}")
            return []
    
    def _parse_articles(self, xml_content: str) -> List[ArticleCreate]:
        """Parse articles from XML (existing implementation)"""
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
                    
                    # Enhanced abstract parsing
                    abstract = self._extract_xml_abstract(article_data)
                    
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
                    pub_date = self._extract_xml_publication_date(article_data)
                    
                    # Parse DOI
                    doi = None
                    for article_id in medline.findall('.//ArticleId'):
                        if article_id.get('IdType') == 'doi':
                            doi = article_id.text
                            break
                    
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
                    logger.error(f"Error parsing XML article: {e}")
                    continue
            
            return articles
            
        except Exception as e:
            logger.error(f"Error parsing XML: {e}")
            return []
    
    def _extract_xml_abstract(self, article_data) -> Optional[str]:
        """Extract abstract from XML"""
        abstract_parts = []
        
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
        
        simple_abstract = article_data.find('Abstract/AbstractText')
        if simple_abstract is not None and simple_abstract.text:
            return simple_abstract.text.strip()
        
        return None
    
    def _extract_xml_publication_date(self, article_data) -> Optional[str]:
        """Extract publication date from XML"""
        pub_date_elem = article_data.find('Journal/JournalIssue/PubDate')
        if pub_date_elem is not None:
            year_elem = pub_date_elem.find('Year')
            if year_elem is not None and year_elem.text:
                return str(year_elem.text)
        
        date_elem = article_data.find('ArticleDate')
        if date_elem is not None:
            year_elem = date_elem.find('Year')
            if year_elem is not None and year_elem.text:
                return str(year_elem.text)
        
        return None


# Update the other API classes (keeping them the same)
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
                
                if not abstract or len(abstract.strip()) < 50:
                    continue
                
                authors = []
                author_string = result.get('authorString', '')
                if author_string:
                    authors = [name.strip() for name in author_string.split(',')]
                
                doi = result.get('doi')
                journal = result.get('journalTitle') or result.get('journalName')
                pub_year = result.get('pubYear')
                pmid = result.get('pmid')
                
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

# Keep other API classes the same...
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
                fields = {}
                for field_name, field_values in study.items():
                    if field_values:
                        fields[field_name] = field_values[0] if isinstance(field_values, list) else field_values
                
                nct_id = fields.get('NCTId', '')
                title = fields.get('BriefTitle', 'No title')
                
                description = fields.get('DetailedDescription', '')
                summary = fields.get('BriefSummary', '')
                
                abstract_parts = []
                if summary:
                    abstract_parts.append(f"Brief Summary: {summary}")
                if description:
                    abstract_parts.append(f"Detailed Description: {description}")
                
                abstract = ' '.join(abstract_parts) if abstract_parts else None
                
                if not abstract or len(abstract.strip()) < 100:
                    continue
                
                study_type = fields.get('StudyType', '')
                phase = fields.get('Phase', '')
                start_date = fields.get('StartDate', '')
                
                title_parts = [title]
                if study_type:
                    title_parts.append(f"({study_type})")
                if phase:
                    title_parts.append(f"Phase {phase}")
                enhanced_title = ' '.join(title_parts)
                
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
                authors = []
                for author in paper.get('authors', []):
                    if author.get('name'):
                        authors.append(author['name'])
                
                pub_date = None
                year = paper.get('year')
                pub_date_str = paper.get('publicationDate')
                if pub_date_str:
                    pub_date = pub_date_str[:4]
                elif year:
                    pub_date = str(year)
                
                doi = None
                external_ids = paper.get('externalIds', {})
                if external_ids:
                    doi = external_ids.get('DOI')
                
                journal = None
                journal_info = paper.get('journal')
                if journal_info and isinstance(journal_info, dict):
                    journal = journal_info.get('name')
                
                abstract = paper.get('abstract', '')
                
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
                    
                    if not summary or len(summary.strip()) < 100:
                        continue
                    
                    authors = []
                    for author in entry.findall('author'):
                        name_elem = author.find('name')
                        if name_elem is not None:
                            authors.append(name_elem.text)
                    
                    url = None
                    id_elem = entry.find('id')
                    if id_elem is not None:
                        url = id_elem.text
                    
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
    """Enhanced API manager with improved PubMed scraping"""
    def __init__(self):
        # Initialize enhanced PubMed API with HTML scraping
        self.pubmed = EnhancedPubMedAPI()
        self.europe_pmc = EuropePMCAPI()
        self.clinical_trials = ClinicalTrialsAPI()
        self.semantic_scholar = SemanticScholarAPI()
        self.arxiv = ArxivAPI()
        
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
        
        logger.info(f"Enhanced APIManager initialized with improved PubMed HTML scraping")
    
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
            
            relevance_score += (10 - api_config.get("priority", 5))
            
            relevant_apis.append((api_name, api_config, relevance_score))
        
        relevant_apis.sort(key=lambda x: x[2], reverse=True)
        
        all_articles = []
        seen_identifiers: Set[str] = set()
        
        active_apis = len(relevant_apis)
        base_per_api = max(limit // active_apis, 5)
        
        for api_name, api_config, score in relevant_apis:
            try:
                api_limit = base_per_api
                if score > 15:
                    api_limit = int(base_per_api * 1.5)
                
                logger.info(f"Searching {api_name} (relevance: {score}) for '{query}' (limit: {api_limit})")
                
                api_client = api_config["client"]
                articles = await api_client.search(query, api_limit, offset)
                
                unique_articles = []
                for article in articles:
                    identifier = self._create_identifier(article)
                    
                    if identifier not in seen_identifiers:
                        seen_identifiers.add(identifier)
                        unique_articles.append(article)
                
                all_articles.extend(unique_articles)
                logger.info(f"Retrieved {len(unique_articles)} unique articles from {api_name}")
                
                if len(all_articles) >= limit * 1.5:
                    break
                
            except Exception as e:
                logger.error(f"Error searching {api_name}: {e}")
                continue
        
        final_articles = self._final_quality_filter(all_articles)
        final_articles.sort(key=self._calculate_quality_score, reverse=True)
        
        result = final_articles[:limit]
        logger.info(f"Returning {len(result)} high-quality articles with abstracts")
        return result
    
    def _create_identifier(self, article: ArticleCreate) -> str:
        """Create unique identifier for deduplication"""
        if article.doi:
            return f"doi:{article.doi.lower()}"
        
        if article.title:
            title_clean = re.sub(r'[^\w\s]', '', article.title.lower()).strip()
            title_hash = hashlib.md5(title_clean.encode()).hexdigest()[:12]
            return f"title:{title_hash}"
        
        return f"fallback:{hash(str(article))}"
    
    def _calculate_quality_score(self, article: ArticleCreate) -> float:
        """Calculate quality score for article ranking"""
        score = 0
        
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
        
        if article.doi:
            score += 10
        
        if article.authors and len(article.authors) > 0:
            score += 5
        
        if article.journal:
            score += 5
        
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
            if not article.abstract or len(article.abstract.strip()) < 50:
                continue
            
            if not article.title or len(article.title.strip()) < 10:
                continue
            
            filtered.append(article)
        
        return filtered
    
    async def close(self):
        """Close any active sessions"""
        pass

# Create singleton instance
enhanced_api_manager = EnhancedAPIManager()