import React, { useState, useEffect } from 'react';
import './App.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

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
      const data = await response.json();
      setSummary(data.summary);
    } catch (error) {
      console.error('Error generating summary:', error);
    }
    setLoading(false);
  };

  const handleFindSimilar = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/articles/${article.id}/similar`);
      const data = await response.json();
      setSimilarArticles(data.similar_articles || []);
      setShowSimilar(true);
    } catch (error) {
      console.error('Error finding similar articles:', error);
      setSimilarArticles([]);
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
          <span key={idx} className="category-tag">{cat}</span>
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
          <p><strong>Overview:</strong> {summary.one_line || 'Summary not available'}</p>
          <div><strong>Key Findings:</strong>
            <ul>
              {(summary.key_findings || []).map((finding, idx) => (
                <li key={idx}>{finding}</li>
              ))}
            </ul>
          </div>
          <p><strong>Clinical Implications:</strong> {summary.clinical_implications || 'Not available'}</p>
          {summary.limitations && (
            <p><strong>Limitations:</strong> {summary.limitations}</p>
          )}
        </div>
      )}

      {showSimilar && similarArticles.length > 0 && (
        <div className="similar-section">
          <h4>Similar Articles</h4>
          {similarArticles.map((similar, idx) => (
            <div key={idx} className="similar-article">
              <span className="similarity-score">{(similar.similarity * 100).toFixed(1)}%</span>
              <span className="similar-title">{similar.title || 'Untitled'}</span>
              <span className="similar-journal">{similar.journal || 'Unknown'}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// Search Component
const SearchBar = ({ onSearch, loading }) => {
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState(10);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query, limit);
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
    </form>
  );
};

// Trends Component
const TrendsSection = () => {
  const [trends, setTrends] = useState(null);
  const [loading, setLoading] = useState(false);
  const [days, setDays] = useState(30);

  const fetchTrends = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/trends?days=${days}`);
      const data = await response.json();
      setTrends(data.trends);
    } catch (error) {
      console.error('Error fetching trends:', error);
      setTrends(null);
    }
    setLoading(false);
  };

  useEffect(() => {
    const fetchTrends = async () => {
      try {
        const response = await fetch('/api/trends?days=30');
        const data = await response.json();
        setTrends(data);
      } catch (error) {
        console.error('Error fetching trends:', error);
      }
    };

    fetchTrends();
  }, []);

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
                <span key={idx} className="trend-tag frequent">{topic}</span>
              ))}
            </div>
          </div>

          <div className="trend-category">
            <h4>Emerging Themes</h4>
            <div className="trend-tags">
              {(trends.emerging_themes || []).map((theme, idx) => (
                <span key={idx} className="trend-tag emerging">{theme}</span>
              ))}
            </div>
          </div>

          <div className="trend-category">
            <h4>Notable Shifts</h4>
            <div className="trend-tags">
              {(trends.notable_shifts || []).map((shift, idx) => (
                <span key={idx} className="trend-tag shift">{shift}</span>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="no-trends">No trends data available</div>
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

  const handleSearch = async (query, limit) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/search`, {
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
              <div className="no-results">No articles found. Try a different search term.</div>
            )}

            {!loading && articles.length > 0 && (
              <div className="articles-list">
                <h2>Search Results ({articles.length})</h2>
                {articles.map((article, index) => (
                  <ArticleCard
                    key={article.id || article.doi || `article-${index}`}
                    article={article}
                  />
                ))}
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