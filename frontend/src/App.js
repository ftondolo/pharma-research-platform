import React, { useState, useEffect, useCallback } from 'react';
import './App.css';

// Use empty string to rely on proxy configuration
const API_BASE = '';

// Article Card Component
const ArticleCard = ({ article, onViewDetails, onSummarize, onFindSimilar }) => {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [similarArticles, setSimilarArticles] = useState([]);
  const [showSimilar, setShowSimilar] = useState(false);

  const handleSummarize = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/articles/${article.id}/summarize`, {
        method: 'POST'
      });
      if (response.ok) {
        const data = await response.json();
        setSummary(data.summary);
      } else {
        console.error('Failed to generate summary');
      }
    } catch (error) {
      console.error('Error generating summary:', error);
    }
    setLoading(false);
  };

  const handleFindSimilar = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/articles/${article.id}/similar`);
      if (response.ok) {
        const data = await response.json();
        setSimilarArticles(data.similar_articles || []);
        setShowSimilar(true);

        // Log method used for debugging
        if (data.method) {
          console.log(`Similar articles found using: ${data.method}`);
        }
      } else {
        console.error('Failed to find similar articles:', response.status);
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

  return (
    <div className="article-card">
      <div className="article-header">
        <h3>{article.title || 'Untitled'}</h3>
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
        <p>{(article.abstract || 'No abstract available.').substring(0, 200)}...</p>
      </div>

      <div className="categories">
        {categories.map((cat, idx) => (
          <span key={`${article.id}-cat-${idx}-${cat || 'empty'}`} className="category-tag">
            {cat || 'Uncategorized'}
          </span>
        ))}
      </div>

      <div className="article-actions">
        <button onClick={handleSummarize} disabled={loading}>
          {loading ? 'Generating...' : 'Summarize'}
        </button>
        <button onClick={handleFindSimilar} disabled={loading}>
          {loading ? 'Finding...' : 'Find Similar'}
        </button>
        <a href={article.url} target="_blank" rel="noopener noreferrer">
          View Full Article
        </a>
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
                    {summary.key_findings.map((finding, idx) => (
                      <li key={`${article.id}-finding-${idx}-${finding ? finding.substring(0, 10) : 'empty'}`}>
                        {finding}
                      </li>
                    ))}
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
              // Generate a more stable unique key
              const titleSnippet = (similar.title || 'untitled').substring(0, 20).replace(/\s+/g, '-');
              const uniqueKey = `${article.id}-similar-${idx}-${similar.id || titleSnippet}`;

              return (
                <div key={uniqueKey} className="similar-article">
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

// Search Component
const SearchBar = ({ onSearch, loading }) => {
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState(10);
  const [requireAbstract, setRequireAbstract] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query, limit, requireAbstract);
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
        <label className="debug-option">
          <input
            type="checkbox"
            checked={requireAbstract}
            onChange={(e) => setRequireAbstract(e.target.checked)}
            disabled={loading}
          />
          <span className="debug-label">Debug: Only show articles with abstracts</span>
        </label>
      </div>
    </form>
  );
};

// Trends Component
const TrendsSection = () => {
  const [trends, setTrends] = useState(null);
  const [loading, setLoading] = useState(false);
  const [days, setDays] = useState(30);

  const fetchTrends = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/trends?days=${days}`);

      if (response.ok) {
        const data = await response.json();
        setTrends(data.trends || data);
      } else {
        console.error('Failed to fetch trends:', response.status);
        setTrends(null);
      }
    } catch (error) {
      console.error('Error fetching trends:', error);
      setTrends(null);
    }
    setLoading(false);
  }, [days]); // Add days as dependency

  useEffect(() => {
    fetchTrends();
  }, [fetchTrends]); // Include fetchTrends in dependency array

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
        <div className="loading">Loading trends...</div>
      ) : trends ? (
        <div className="trends-content">
          <div className="trend-category">
            <h4>Frequent Topics</h4>
            <div className="trend-tags">
              {(trends.frequent_topics || []).map((topic, idx) => (
                <span key={`freq-topic-${idx}-${topic || 'empty'}`} className="trend-tag frequent">
                  {topic || 'Unknown Topic'}
                </span>
              ))}
            </div>
          </div>

          <div className="trend-category">
            <h4>Emerging Themes</h4>
            <div className="trend-tags">
              {(trends.emerging_themes || []).map((theme, idx) => (
                <span key={`emerg-theme-${idx}-${theme || 'empty'}`} className="trend-tag emerging">
                  {theme || 'Unknown Theme'}
                </span>
              ))}
            </div>
          </div>

          <div className="trend-category">
            <h4>Notable Shifts</h4>
            <div className="trend-tags">
              {(trends.notable_shifts || []).map((shift, idx) => (
                <span key={`shift-${idx}-${shift || 'empty'}`} className="trend-tag shift">
                  {shift || 'Unknown Shift'}
                </span>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="no-trends">No trends data available. Try searching for articles first.</div>
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

  const handleSearch = async (query, limit, requireAbstract = false) => {
    setLoading(true);
    setError(null);
    setSearchMetadata(null);

    try {
      // Build URL with query parameters
      const searchUrl = new URL(`${API_BASE}/search`, window.location.origin);
      if (requireAbstract) {
        searchUrl.searchParams.append('require_abstract', 'true');
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
      console.log('Search response:', data); // Debug log

      if (data && data.articles) {
        setArticles(data.articles);
        setSearchPerformed(true);
        setSearchMetadata(data.metadata || null);

        // Log debug info if abstract filtering was used
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
            {loading && <div className="loading">Searching and processing articles...</div>}

            {!loading && searchPerformed && articles.length === 0 && (
              <div className="no-results">No articles found. Try a different search term or disable the abstract filter.</div>
            )}

            {!loading && articles.length > 0 && (
              <div className="articles-list">
                <div className="results-header">
                  <h2>Search Results</h2>
                  {searchMetadata && (
                    <div className="search-stats">
                      <span className="result-count">
                        Showing {searchMetadata.delivered_count} of {searchMetadata.total_fetched} articles found
                      </span>
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
                    </div>
                  )}
                </div>
                {articles.map((article, index) => {
                  // Generate a stable and unique key
                  const titleSnippet = (article.title || 'untitled').substring(0, 30).replace(/\s+/g, '-');
                  const uniqueKey = article.id ||
                    article.doi ||
                    `article-${index}-${titleSnippet}-${Date.now()}` ||
                    `fallback-${index}-${Date.now()}`;

                  return (
                    <ArticleCard
                      key={uniqueKey}
                      article={article}
                    />
                  );
                })}
              </div>
            )}
          </div>

          <div className="sidebar">
            <TrendsSection />
          </div>
        </div>
      </main>
    </div>
  );
};

export default App;