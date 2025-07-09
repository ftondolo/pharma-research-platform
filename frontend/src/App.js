import React, { useState, useEffect, useCallback } from 'react';
import './App.css';

// Use empty string to rely on proxy configuration
const API_BASE = '';

// Utility function to generate stable keys
const generateKey = (prefix, id, index, fallback = '') => {
  if (id && id !== 'None' && id !== 'null' && id !== 'undefined') {
    return `${prefix}-${id}`;
  }
  return `${prefix}-${index}-${fallback.substring(0, 20).replace(/\s+/g, '-')}-${Date.now()}`;
};

// Enhanced Search Component with hybrid search options
const SearchBar = ({ onSearch, loading }) => {
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState(10);
  const [requireAbstract, setRequireAbstract] = useState(false);
  const [searchDatabase, setSearchDatabase] = useState(true);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query, limit, requireAbstract, searchDatabase);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="search-form">
      <div className="search-input-group">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search pharmaceutical research..."
          className="search-input"
          disabled={loading}
        />
        <select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          className="limit-select"
          disabled={loading}
        >
          <option value={5}>5 results</option>
          <option value={10}>10 results</option>
          <option value={20}>20 results</option>
          <option value={50}>50 results</option>
        </select>
        <button type="submit" disabled={loading} className="search-button">
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>

      <div className="search-options">
        <div className="option-group">
          <label className="search-option">
            <input
              type="checkbox"
              checked={searchDatabase}
              onChange={(e) => setSearchDatabase(e.target.checked)}
              disabled={loading}
            />
            <span className="option-label">
              🔍 Search existing database
              <small>Include previously found articles</small>
            </span>
          </label>

          <label className="search-option">
            <input
              type="checkbox"
              checked={requireAbstract}
              onChange={(e) => setRequireAbstract(e.target.checked)}
              disabled={loading}
            />
            <span className="option-label">
              📄 Only articles with abstracts
              <small>Higher quality, fewer results</small>
            </span>
          </label>
        </div>
      </div>
    </form>
  );
};

// Article Card Component
const ArticleCard = ({ article, index }) => {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [similarArticles, setSimilarArticles] = useState([]);
  const [showSimilar, setShowSimilar] = useState(false);

  // Handle case where article.id might be None or invalid
  const articleId = article.id && article.id !== 'None' && !article.id.startsWith('temp-') ? article.id : null;

  const handleSummarize = async () => {
    if (!articleId) {
      alert('Please search again to get proper article IDs before summarizing.');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/articles/${articleId}/summarize`, {
        method: 'POST'
      });
      if (response.ok) {
        const data = await response.json();
        setSummary(data.summary);
      } else {
        const errorText = await response.text();
        console.error('Failed to generate summary:', errorText);
        alert('Failed to generate summary. Please try again.');
      }
    } catch (error) {
      console.error('Error generating summary:', error);
      alert('Error generating summary. Please check your connection.');
    }
    setLoading(false);
  };

  const handleFindSimilar = async () => {
    if (!articleId) {
      alert('Please search again to get proper article IDs before finding similar articles.');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/articles/${articleId}/similar`);
      if (response.ok) {
        const data = await response.json();
        setSimilarArticles(data.similar_articles || []);
        setShowSimilar(true);

        // Log method used for debugging
        if (data.method) {
          console.log(`Similar articles found using: ${data.method}`);
        }
      } else {
        const errorText = await response.text();
        console.error('Failed to find similar articles:', response.status, errorText);
        setSimilarArticles([]);
        setShowSimilar(true); // Still show the section with "no results" message
      }
    } catch (error) {
      console.error('Error finding similar articles:', error);
      setSimilarArticles([]);
      setShowSimilar(true); // Still show the section with error message
    }
    setLoading(false);
  };

  // Safe access to arrays with fallbacks
  const authors = article.authors || [];
  const categories = article.categories || [];
  const articleTitle = article.title || 'Untitled';

  return (
    <div className="article-card">
      <div className="article-header">
        <h3>{articleTitle}</h3>
        <span className="journal">{article.journal || 'Unknown Journal'}</span>
      </div>

      <div className="article-meta">
        <span className="authors">
          {authors.slice(0, 3).join(', ')}
          {authors.length > 3 && ` et al.`}
        </span>
        <span className="date">{article.publication_date || 'Unknown Date'}</span>
      </div>

      <div className="abstract">
        <p>{(article.abstract || 'No abstract available.').substring(0, 300)}...</p>
      </div>

      <div className="categories">
        {categories.map((cat, idx) => {
          const categoryKey = generateKey('cat', articleId, idx, cat || 'uncategorized');
          return (
            <span key={categoryKey} className="category-tag">
              {cat || 'Uncategorized'}
            </span>
          );
        })}
      </div>

      <div className="article-actions">
        <button
          onClick={handleSummarize}
          disabled={loading || !articleId}
          title={!articleId ? 'Search again to enable this feature' : ''}
        >
          {loading ? 'Generating...' : 'Summarize'}
        </button>
        <button
          onClick={handleFindSimilar}
          disabled={loading || !articleId}
          title={!articleId ? 'Search again to enable this feature' : ''}
        >
          {loading ? 'Finding...' : 'Find Similar'}
        </button>
        {article.url && article.url !== '#' && (
          <a href={article.url} target="_blank" rel="noopener noreferrer">
            View Full Article
          </a>
        )}
      </div>

      {summary && (
        <div className="summary-section">
          <h4>AI Summary</h4>
          {typeof summary === 'object' ? (
            <>
              <p><strong>Overview:</strong> {summary.one_line || summary.overview || 'Summary not available'}</p>
              {summary.overview && summary.overview !== summary.one_line && (
                <p><strong>Details:</strong> {summary.overview}</p>
              )}
              {summary.key_findings && summary.key_findings.length > 0 && (
                <div><strong>Key Findings:</strong>
                  <ul>
                    {summary.key_findings.map((finding, idx) => {
                      const findingKey = generateKey('finding', articleId, idx, finding || 'empty');
                      return (
                        <li key={findingKey}>
                          {finding}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
              {summary.clinical_implications && (
                <p><strong>Clinical Implications:</strong> {summary.clinical_implications}</p>
              )}
              {summary.limitations && (
                <p><strong>Limitations:</strong> {summary.limitations}</p>
              )}
              <p><em>Source: {summary.source || 'Generated summary'}</em></p>
            </>
          ) : (
            <p><strong>Summary:</strong> {summary}</p>
          )}
        </div>
      )}

      {showSimilar && (
        <div className="similar-section">
          <h4>Similar Articles</h4>
          {similarArticles.length > 0 ? (
            similarArticles.map((similar, idx) => {
              const similarKey = generateKey('similar', similar.id, idx, similar.title || 'untitled');

              return (
                <div key={similarKey} className="similar-article">
                  <span className="similarity-score">{(similar.similarity * 100).toFixed(1)}%</span>
                  <div className="similar-details">
                    <div className="similar-title">{similar.title || 'Untitled'}</div>
                    <div className="similar-journal">{similar.journal || 'Unknown'}</div>
                    {similar.authors && similar.authors.length > 0 && (
                      <div className="similar-authors">by {similar.authors.join(', ')}</div>
                    )}
                  </div>
                  {similar.url && similar.url !== '#' && (
                    <a href={similar.url} target="_blank" rel="noopener noreferrer" className="similar-link">
                      View
                    </a>
                  )}
                </div>
              );
            })
          ) : (
            <div className="no-similar">
              <p>No similar articles found.</p>
              <p><em>Try searching for related topics or check back later.</em></p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// Interactive Trends Component
const TrendsSection = ({ onTrendClick }) => {
  const [trends, setTrends] = useState(null);
  const [loading, setLoading] = useState(false);
  const [days, setDays] = useState(30);
  const [searchSuggestions, setSearchSuggestions] = useState([]);

  const fetchTrends = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/trends?days=${days}`);

      if (response.ok) {
        const data = await response.json();
        setTrends(data.trends || data);
        setSearchSuggestions(data.search_suggestions || []);

        // Log trend analysis info
        if (data.metadata) {
          console.log(`Trends analysis: ${data.metadata.data_source}, confidence: ${data.metadata.confidence}`);
        }
      } else {
        console.error('Failed to fetch trends:', response.status);
        setTrends(null);
      }
    } catch (error) {
      console.error('Error fetching trends:', error);
      setTrends(null);
    }
    setLoading(false);
  }, [days]);

  useEffect(() => {
    fetchTrends();
  }, [fetchTrends]);

  const handleTrendClick = (trendTerm) => {
    if (onTrendClick) {
      console.log('Trend clicked:', trendTerm);
      onTrendClick(trendTerm);
    }
  };

  return (
    <div className="trends-section">
      <div className="trends-header">
        <h3>Research Trends</h3>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="period-select"
        >
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      {loading ? (
        <div className="loading">Analyzing trends...</div>
      ) : trends ? (
        <div className="trends-content">
          <div className="trend-category">
            <h4>Frequent Topics</h4>
            <div className="trend-tags">
              {(trends.frequent_topics || []).map((topic, idx) => {
                const topicKey = generateKey('freq-topic', null, idx, topic || 'empty');
                return (
                  <button
                    key={topicKey}
                    className="trend-tag frequent clickable"
                    onClick={() => handleTrendClick(topic)}
                    title={`Search for "${topic}"`}
                  >
                    {topic || 'Unknown Topic'}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="trend-category">
            <h4>Emerging Themes</h4>
            <div className="trend-tags">
              {(trends.emerging_themes || []).map((theme, idx) => {
                const themeKey = generateKey('emerg-theme', null, idx, theme || 'empty');
                return (
                  <button
                    key={themeKey}
                    className="trend-tag emerging clickable"
                    onClick={() => handleTrendClick(theme)}
                    title={`Search for "${theme}"`}
                  >
                    {theme || 'Unknown Theme'}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="trend-category">
            <h4>Notable Shifts</h4>
            <div className="trend-tags">
              {(trends.notable_shifts || []).map((shift, idx) => {
                const shiftKey = generateKey('shift', null, idx, shift || 'empty');
                return (
                  <button
                    key={shiftKey}
                    className="trend-tag shift clickable"
                    onClick={() => handleTrendClick(shift)}
                    title={`Search for "${shift}"`}
                  >
                    {shift || 'Unknown Shift'}
                  </button>
                );
              })}
            </div>
          </div>

          {searchSuggestions && searchSuggestions.length > 0 && (
            <div className="trend-category">
              <h4>Quick Searches</h4>
              <div className="trend-tags">
                {searchSuggestions.map((suggestion, idx) => {
                  const suggestionKey = generateKey('suggestion', null, idx, suggestion || 'empty');
                  return (
                    <button
                      key={suggestionKey}
                      className="trend-tag suggestion clickable"
                      onClick={() => handleTrendClick(suggestion)}
                      title={`Search for "${suggestion}"`}
                    >
                      🔍 {suggestion}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="no-trends">
          No trends data available. Search for articles to generate trends.
        </div>
      )}
    </div>
  );
};

// Main App Component
const App = () => {
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchPerformed, setSearchPerformed] = useState(false);
  const [searchMetadata, setSearchMetadata] = useState(null);

  const handleSearch = async (query, limit, requireAbstract = false, searchDatabase = true) => {
    setLoading(true);
    setError(null);
    setSearchMetadata(null);

    try {
      // Build URL with query parameters
      const searchUrl = new URL(`${API_BASE}/search`, window.location.origin);
      if (requireAbstract) {
        searchUrl.searchParams.append('require_abstract', 'true');
      }
      if (!searchDatabase) {
        searchUrl.searchParams.append('search_database', 'false');
      }

      const response = await fetch(searchUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query, limit }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
      }

      const data = await response.json();
      console.log('Hybrid search response:', data);

      if (data && data.articles) {
        setArticles(data.articles);
        setSearchPerformed(true);
        setSearchMetadata(data.metadata || null);

        // Log hybrid search info
        if (data.metadata && data.metadata.hybrid_search) {
          console.log(`Hybrid search: ${data.metadata.database_results} from database, ${data.metadata.external_results} from external APIs`);
        }

        // Log abstract filtering info
        if (requireAbstract && data.metadata) {
          console.log(`Search with abstract filter: ${data.articles.length} results, ${data.metadata.filtered_count} filtered out`);
        }
      } else {
        console.error('Invalid response structure:', data);
        setArticles([]);
        setSearchPerformed(true);
      }
    } catch (error) {
      console.error('Search error:', error);
      setError(`Failed to search articles: ${error.message}`);
      setArticles([]);
    }

    setLoading(false);
  };

  const handleTrendClick = (trendTerm) => {
    console.log('Searching for trend:', trendTerm);
    // For trend searches, include both database and external sources with abstracts
    handleSearch(trendTerm, 15, true, true);

    // Scroll to results
    setTimeout(() => {
      const resultsSection = document.querySelector('.articles-section');
      if (resultsSection) {
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }, 100);
  };

  return (
    <div className="App">
      <header className="app-header">
        <h1>Pharmaceutical Research Platform</h1>
        <p>AI-powered research discovery and analysis</p>
      </header>

      <main className="app-main">
        <div className="search-section">
          <SearchBar onSearch={handleSearch} loading={loading} />
          {error && <div className="error-message">{error}</div>}
        </div>

        <div className="content-grid">
          <div className="articles-section">
            {loading && (
              <div className="loading">
                <div className="loading-text">Searching articles...</div>
                <div className="loading-details">
                  <span>🔍 Checking database</span>
                  <span>🌐 Fetching from external APIs</span>
                  <span>📊 Analyzing results</span>
                </div>
              </div>
            )}

            {!loading && searchPerformed && articles.length === 0 && (
              <div className="no-results">
                <h3>No articles found</h3>
                <p>Try different search terms or adjust your filters:</p>
                <ul>
                  <li>Enable database search to include existing articles</li>
                  <li>Disable abstract requirement for more results</li>
                  <li>Use broader search terms</li>
                  <li>Try clicking trend buttons for curated searches</li>
                </ul>
              </div>
            )}

            {!loading && articles.length > 0 && (
              <div className="articles-list">
                <div className="results-header">
                  <h2>Search Results</h2>
                  {searchMetadata && (
                    <div className="search-stats">
                      <span className="result-count">
                        Showing {searchMetadata.delivered_count} articles
                      </span>

                      {searchMetadata.hybrid_search && (
                        <div className="hybrid-stats">
                          <span className="source-breakdown">
                            📚 {searchMetadata.database_results} from database •
                            🌐 {searchMetadata.external_results} from external sources
                          </span>
                        </div>
                      )}

                      {searchMetadata.filtered_count > 0 && (
                        <span className="filter-info">
                          ({searchMetadata.filtered_count} filtered out for lacking abstracts)
                        </span>
                      )}

                      {!searchMetadata.search_complete && searchMetadata.delivered_count < searchMetadata.requested_count && (
                        <span className="incomplete-warning">
                          • Requested {searchMetadata.requested_count} but could only find {searchMetadata.delivered_count} with abstracts
                        </span>
                      )}

                      {searchMetadata.fetch_attempts > 1 && (
                        <span className="filter-info">
                          • Made {searchMetadata.fetch_attempts} API attempts to find articles with abstracts
                        </span>
                      )}

                      {searchMetadata.enhanced_apis_used && (
                        <span className="enhancement-info">
                          • Enhanced with multi-source APIs and real-time trends
                        </span>
                      )}

                      {searchMetadata.sources && (
                        <span className="sources-info">
                          Sources: {Object.entries(searchMetadata.sources)
                            .filter(([key, value]) => value > 0)
                            .map(([key, value]) => `${key}: ${value}`)
                            .join(', ')
                          }
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {articles.map((article, index) => {
                  const uniqueKey = generateKey('article', article.id, index, article.title || 'untitled');

                  return (
                    <ArticleCard
                      key={uniqueKey}
                      article={article}
                      index={index}
                    />
                  );
                })}
              </div>
            )}
          </div>

          <div className="sidebar">
            <TrendsSection onTrendClick={handleTrendClick} />
          </div>
        </div>
      </main>
    </div>
  );
};

export default App;