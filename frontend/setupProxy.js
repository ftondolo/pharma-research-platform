// frontend/src/setupProxy.js
const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  app.use(
    '/api',
    createProxyMiddleware({
      // In Docker, use the service name; locally use localhost
      target: process.env.REACT_APP_API_URL || 'http://backend:8000',
      changeOrigin: true,
      pathRewrite: {
        '^/api': '', // Remove /api prefix when forwarding to backend
      },
      onError: (err, req, res) => {
        console.error('Proxy error:', err);
        res.status(500).send('Proxy error');
      }
    })
  );
  
  // Also proxy other backend endpoints
  app.use(
    ['/search', '/articles', '/trends', '/health', '/usage', '/docs', '/openapi.json'],
    createProxyMiddleware({
      target: process.env.REACT_APP_API_URL || 'http://backend:8000',
      changeOrigin: true,
    })
  );
};
