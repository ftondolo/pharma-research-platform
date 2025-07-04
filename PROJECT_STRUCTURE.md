# Project Structure

```
pharma-research-platform/
├── 📁 backend/
│   ├── main.py                 # FastAPI application entry point
│   ├── models.py               # SQLAlchemy and Pydantic models
│   ├── database.py             # Database configuration and connection
│   ├── api_services.py         # External API integrations (PubMed, Semantic Scholar, CrossRef)
│   ├── ai_services.py          # OpenAI integration for AI features
│   ├── logging_config.py       # Logging configuration and utilities
│   ├── test_config.py          # Test suite configuration
│   ├── dev_config.py           # Development utilities and commands
│   └── requirements.txt        # Python dependencies
│
├── 📁 frontend/
│   ├── 📁 src/
│   │   ├── App.js             # Main React application component
│   │   ├── App.css            # Application styles
│   │   └── index.js           # React app entry point
│   ├── 📁 public/
│   │   ├── index.html         # HTML template
│   │   └── manifest.json      # PWA manifest
│   └── package.json           # Node.js dependencies
│
├── 📁 docker/
│   ├── docker-compose.yml     # Multi-container Docker configuration
│   ├── Dockerfile.backend     # Backend container configuration
│   └── Dockerfile.frontend    # Frontend container configuration
│
├── 📁 config/
│   ├── .env.template          # Environment variables template
│   └── logging.conf           # Logging configuration
│
├── 📁 scripts/
│   ├── startup.sh             # Application startup script
│   └── dev.py                 # Development utilities
│
├── 📁 docs/
│   ├── README.md              # Main documentation
│   ├── API.md                 # API documentation
│   └── DEPLOYMENT.md          # Deployment guide
│
├── 📁 tests/
│   ├── test_api.py            # API endpoint tests
│   ├── test_services.py       # Service layer tests
│   └── conftest.py            # Test configuration
│
├── Makefile                   # Development commands
├── .env.template              # Environment template
├── .gitignore                 # Git ignore rules
└── README.md                  # Project documentation
```

## Key Components

### Backend Architecture
- **FastAPI**: Modern, fast web framework for building APIs
- **SQLAlchemy**: Database ORM with PostgreSQL support
- **Pydantic**: Data validation and serialization
- **OpenAI Integration**: AI-powered categorization and summarization
- **Multi-API Support**: PubMed, Semantic Scholar, CrossRef integration

### Frontend Architecture
- **React**: Component-based UI library
- **Modern CSS**: Responsive design with CSS Grid/Flexbox
- **REST API Integration**: Axios for HTTP requests
- **State Management**: React hooks for local state

### Database Schema
- **Articles**: Core research article storage
- **Embeddings**: Vector representations for semantic search
- **Categories**: AI-generated article classifications
- **Metadata**: Journal, author, publication information

### AI Features
- **Categorization**: Automatic therapeutic area classification
- **Summarization**: Structured research summaries
- **Semantic Search**: Embedding-based similarity matching
- **Trend Analysis**: Topic frequency and emerging themes

### Infrastructure
- **Docker**: Containerized deployment
- **PostgreSQL**: Primary database with JSONB support
- **Redis**: Caching layer for API responses
- **Nginx**: Reverse proxy (production)

## Development Workflow

### Setup Commands
```bash
# Initialize project
make setup

# Start development
make dev

# Run tests
make test

# View logs
make logs
```

### API Development
1. Define models in `models.py`
2. Create endpoints in `main.py`
3. Add service logic in `api_services.py` or `ai_services.py`
4. Write tests in `test_config.py`

### Frontend Development
1. Create components in `src/`
2. Add styles in `App.css`
3. Connect to API endpoints
4. Test in browser

### Testing Strategy
- Unit tests for API endpoints
- Integration tests for AI services
- Mock external API calls
- Database transaction rollback

## Deployment Options

### Docker Deployment
```bash
docker-compose up -d
```

### Production Deployment
- Container orchestration (Kubernetes, Docker Swarm)
- Managed databases (AWS RDS, Google Cloud SQL)
- CDN for frontend assets
- Load balancing and auto-scaling

## Configuration

### Environment Variables
- `OPENAI_API_KEY`: Required for AI features
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `LOG_LEVEL`: Logging verbosity

### Rate Limiting
- PubMed: 3 requests/second
- Semantic Scholar: 100 requests/second
- CrossRef: 50 requests/second

## Monitoring

### Health Checks
- `/health`: Basic health check
- `/health/detailed`: Comprehensive dependency check

### Logging
- Structured logging with JSON format
- Request/response logging
- Error tracking and alerting

### Metrics
- API response times
- Database query performance
- OpenAI token usage
- User engagement metrics

## Security

### API Security
- Rate limiting on endpoints
- Input validation with Pydantic
- SQL injection prevention with SQLAlchemy
- CORS configuration

### Data Protection
- No sensitive data storage
- API key encryption
- Database connection pooling
- Secure headers configuration

## Performance Optimization

### Caching Strategy
- Redis for API responses (24-hour TTL)
- Permanent embedding storage
- Database query optimization

### Database Optimization
- Indexes on frequently queried fields
- Connection pooling
- Query optimization
- Regular maintenance

### AI Cost Management
- Batch processing for embeddings
- Response caching
- Token usage monitoring
- Model selection optimization
