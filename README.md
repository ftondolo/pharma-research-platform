# Pharmaceutical Research Platform - MVP

A streamlined AI-powered platform for pharmaceutical research discovery and analysis, implementing weeks 1-4 of the development timeline.

## Features

### Core Infrastructure (Weeks 1-2)
- FastAPI backend with PostgreSQL database
- PubMed and Semantic Scholar API integration
- CrossRef API for additional coverage
- React frontend with TypeScript
- Docker containerization

### AI Integration (Weeks 3-4)
- OpenAI GPT-4 for article categorization and summarization
- Semantic search using OpenAI embeddings
- Similar article recommendations
- Trend analysis across research topics

## Quick Start

### Prerequisites
- Docker and Docker Compose
- OpenAI API key
- (Optional) PubHive credentials

### Setup

1. **Clone and Configure**
   ```bash
   git clone <repository>
   cd pharma-research-platform
   cp .env.template .env
   ```

2. **Environment Setup**
   Edit `.env` file with your API keys:
   ```bash
   OPENAI_API_KEY=your_openai_api_key_here
   DATABASE_URL=postgresql://user:password@postgres:5432/pharma_research
   REDIS_URL=redis://redis:6379
   ```

3. **Start Services**
   ```bash
   docker-compose up -d
   ```

4. **Access Application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

## Manual Setup (Alternative)

### Backend Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup database
createdb pharma_research
# Or use Docker: docker run -d -p 5432:5432 -e POSTGRES_DB=pharma_research -e POSTGRES_USER=user -e POSTGRES_PASSWORD=password postgres:15

# Start Redis
redis-server
# Or use Docker: docker run -d -p 6379:6379 redis:7-alpine

# Run backend
uvicorn main:app --reload
```

### Frontend Setup
```bash
# Navigate to frontend directory
mkdir frontend
cd frontend

# Initialize React app
npx create-react-app . --template typescript
# Or copy the provided files

# Install dependencies
npm install

# Start development server
npm start
```

## Project Structure

```
pharma-research-platform/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── models.py            # Database and Pydantic models
│   ├── database.py          # Database configuration
│   ├── api_services.py      # External API integrations
│   ├── ai_services.py       # OpenAI integration
│   └── requirements.txt     # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── App.js          # Main React component
│   │   └── App.css         # Styling
│   └── package.json        # Node.js dependencies
├── docker-compose.yml       # Docker services
├── Dockerfile.backend      # Backend container
├── Dockerfile.frontend     # Frontend container
└── .env.template           # Environment template
```

## API Usage

### Search Articles
```bash
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "cancer immunotherapy", "limit": 10}'
```

### Get Article Summary
```bash
curl -X POST "http://localhost:8000/articles/{article_id}/summarize"
```

### Find Similar Articles
```bash
curl "http://localhost:8000/articles/{article_id}/similar?limit=5"
```

### Get Trends
```bash
curl "http://localhost:8000/trends?days=30"
```

## Key Components

### API Integrations
- **PubMed**: Medical literature via E-utilities API
- **Semantic Scholar**: AI-enhanced paper metadata
- **CrossRef**: DOI-based article information

### AI Features
- **Categorization**: Automatic therapeutic area classification
- **Summarization**: Structured research summaries
- **Semantic Search**: Embedding-based similarity matching
- **Trend Analysis**: Topic frequency and emerging themes

### Database Schema
- **Articles**: Metadata, abstracts, embeddings
- **Categories**: AI-generated classifications
- **Embeddings**: Vector representations for similarity

## Configuration

### Rate Limiting
- PubMed: 3 requests/second
- Semantic Scholar: 100 requests/second
- CrossRef: 50 requests/second (conservative)

### OpenAI Models
- Embeddings: `text-embedding-3-large`
- Chat: `gpt-4` for categorization and summarization

### Database
- PostgreSQL with JSONB for flexible metadata
- Redis for caching API responses and embeddings

## Development

### Adding New APIs
1. Create new API class in `api_services.py`
2. Implement rate limiting and error handling
3. Add to `APIManager.search_all()` method
4. Update deduplication logic

### Extending AI Features
1. Add new prompt templates in `ai_services.py`
2. Create corresponding API endpoints in `main.py`
3. Update frontend components for new features

### Testing
```bash
# Backend tests
pytest

# Frontend tests
npm test
```

## Deployment

### Production Setup
1. Use managed PostgreSQL (AWS RDS, Google Cloud SQL)
2. Use managed Redis (AWS ElastiCache, Google Memorystore)
3. Deploy backend to container service (AWS ECS, Google Cloud Run)
4. Deploy frontend to CDN (AWS CloudFront, Vercel)

### Environment Variables
- Set `LOG_LEVEL=ERROR` for production
- Use secure database credentials
- Configure proper CORS origins
- Set up monitoring and alerting

## Cost Optimization

### OpenAI Usage
- Cache embeddings permanently
- Cache summaries for 24 hours
- Use batch processing for multiple articles
- Monitor token usage and costs

### Database
- Index frequently queried fields
- Use connection pooling
- Regular maintenance and optimization

## Troubleshooting

### Common Issues
1. **Database Connection**: Check PostgreSQL is running and accessible
2. **API Rate Limits**: Verify rate limiting configuration
3. **OpenAI Errors**: Check API key and quota limits
4. **CORS Issues**: Verify frontend/backend URLs in configuration

### Logs
- Backend logs: Check uvicorn output
- Database logs: Check PostgreSQL logs
- Frontend logs: Check browser console

## Next Steps (Weeks 5-8)

Ready for implementation after this MVP:
- User authentication and saved articles
- Notification system for new research
- Slide generation functionality
- Advanced trend analysis
- Real-time collaboration features

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review API documentation at `/docs`
3. Check logs for error details
4. Verify environment configuration
