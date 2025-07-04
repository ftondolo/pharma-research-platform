# 🏗️ Pharmaceutical Research Platform - Project Structure

```
pharma-research-platform/
├── 📁 Backend (FastAPI)
│   ├── main.py                     # 🚀 FastAPI application entry point
│   ├── models.py                   # 🗃️ SQLAlchemy & Pydantic models
│   ├── database.py                 # 🔗 Database connection & configuration
│   ├── api_services.py             # 🌐 External API integrations (PubMed, Semantic Scholar, CrossRef)
│   ├── ai_services.py              # 🤖 OpenAI integration (GPT-4, embeddings)
│   ├── logging_config.py           # 📋 Logging setup & utilities
│   ├── test_config.py              # 🧪 Test suite & mocking
│   ├── dev_config.py               # 🛠️ Development utilities & commands
│   ├── db_test.py                  # 🗃️ Database connection testing
│   └── requirements.txt            # 📦 Python dependencies
│
├── 📁 Frontend (React)
│   ├── 📁 src/
│   │   ├── App.js                  # ⚛️ Main React application component
│   │   ├── App.css                 # 🎨 Application styles & responsive design
│   │   └── index.js                # 🚪 React application entry point
│   ├── 📁 public/
│   │   ├── index.html              # 📄 HTML template with loading fallback
│   │   ├── manifest.json           # 📱 PWA manifest
│   │   └── favicon.ico             # 🖼️ Site icon
│   └── package.json                # 📦 Node.js dependencies & scripts
│
├── 📁 Infrastructure
│   ├── docker-compose.yml          # 🐳 Multi-container orchestration
│   ├── Dockerfile.backend          # 🐳 Backend container configuration
│   ├── Dockerfile.frontend         # 🐳 Frontend container configuration
│   ├── Makefile                    # ⚙️ Development commands & automation
│   ├── startup.sh                  # 🚀 Application startup script
│   └── setup.sh                    # ⚙️ Automated setup script
│
├── 📁 Configuration
│   ├── .env.template               # 🔐 Environment variables template
│   ├── .env                        # 🔒 Environment variables (git-ignored)
│   └── .gitignore                  # 🚫 Git exclusion rules
│
├── 📁 Documentation
│   ├── README.md                   # 📖 Main project documentation
│   ├── PROJECT_STRUCTURE.md        # 🏗️ Architecture overview
│   └── MVP_COMPLETION.md           # ✅ MVP feature summary
│
└── 📁 Version Control
    ├── .git/                       # 🌱 Git repository data
    └── .github/                    # 🔄 GitHub workflows (if added)
        └── workflows/
            └── ci.yml              # 🤖 Continuous integration

📊 Runtime Data (Git-Ignored)
├── 📁 Database
│   ├── pharma_research.db          # 🗃️ SQLite database (development)
│   ├── postgres_data/              # 🗃️ PostgreSQL data volume
│   └── redis_data/                 # 💾 Redis cache volume
│
├── 📁 Python Environment
│   ├── venv/                       # 🐍 Virtual environment
│   ├── __pycache__/                # 📦 Python bytecode cache
│   └── *.pyc                       # 📦 Compiled Python files
│
├── 📁 Node.js
│   ├── frontend/node_modules/      # 📦 Node.js packages
│   ├── frontend/build/             # 🏗️ Production build
│   └── *.log                       # 📋 npm/yarn logs
│
└── 📁 Logs & Temp
    ├── *.log                       # 📋 Application logs
    ├── tmp/                        # 📁 Temporary files
    └── .cache/                     # 💾 Various caches
```

## 🔧 Core Architecture

### Backend Stack
```
FastAPI Application (main.py)
├── 🗃️ Database Layer (database.py, models.py)
│   ├── PostgreSQL (production) / SQLite (development)
│   ├── SQLAlchemy ORM
│   ├── Pydantic validation
│   └── JSONB storage for flexible data
│
├── 🌐 External APIs (api_services.py)
│   ├── PubMed E-utilities API
│   ├── Semantic Scholar API
│   ├── CrossRef API
│   └── Rate limiting & error handling
│
├── 🤖 AI Services (ai_services.py)
│   ├── OpenAI GPT-4 (categorization, summarization)
│   ├── OpenAI Embeddings (semantic search)
│   ├── Trend analysis
│   └── Similar article recommendations
│
└── 🛠️ Support Systems
    ├── Logging (logging_config.py)
    ├── Testing (test_config.py)
    ├── Development tools (dev_config.py)
    └── Health monitoring
```

### Frontend Architecture
```
React Application (App.js)
├── 🔍 Search Interface
│   ├── Multi-source search
│   ├── Real-time processing indicators
│   └── Advanced filtering
│
├── 📄 Article Display
│   ├── Article cards with metadata
│   ├── Category tags
│   ├── Author information
│   └── Publication details
│
├── 🤖 AI Features
│   ├── Article summarization
│   ├── Similar article finder
│   ├── Trend analysis sidebar
│   └── Interactive AI responses
│
└── 🎨 User Experience
    ├── Responsive design
    ├── Loading states
    ├── Error handling
    └── Modern CSS styling
```

## 📊 Data Flow

```
User Search Request
    ↓
React Frontend (App.js)
    ↓
FastAPI Backend (main.py)
    ↓
API Manager (api_services.py)
    ↓ ↓ ↓
PubMed   Semantic Scholar   CrossRef
    ↓ ↓ ↓
AI Processing (ai_services.py)
    ↓
OpenAI GPT-4 & Embeddings
    ↓
Database Storage (PostgreSQL)
    ↓
Processed Results
    ↓
React Frontend Display
```

## 🚀 Deployment Options

### Development
```
Local Machine
├── Python venv + PostgreSQL + Redis
├── React dev server (npm start)
├── FastAPI dev server (uvicorn --reload)
└── Manual service management
```

### Docker Development
```
Docker Compose
├── postgres:15 container
├── redis:7-alpine container
├── Custom backend container
└── Custom frontend container
```

### Production
```
Cloud Infrastructure
├── 🖥️ Container Service (AWS ECS, Google Cloud Run)
├── 🗃️ Managed Database (AWS RDS, Google Cloud SQL)
├── 💾 Managed Cache (AWS ElastiCache, Google Memorystore)
├── 🌐 CDN (CloudFront, CloudFlare)
└── 🔍 Load Balancer + Auto-scaling
```

## 📈 File Sizes & Complexity

| Component | Files | Lines of Code | Purpose |
|-----------|-------|---------------|---------|
| Backend | 9 files | ~2,000 LOC | API, AI, Database |
| Frontend | 4 files | ~800 LOC | UI, Search, Display |
| Infrastructure | 6 files | ~300 LOC | Docker, Build, Deploy |
| Configuration | 3 files | ~200 LOC | Environment, Git |
| Documentation | 3 files | ~1,500 LOC | README, Guides |

## 🔐 Security & Environment

### Protected Files (`.gitignore`)
- 🔒 `.env` - API keys and secrets
- 🗃️ `*.db` - Database files
- 📦 `node_modules/` - Dependencies
- 🐍 `venv/` - Python environment
- 📋 `*.log` - Log files

### Environment Variables (`.env`)
- 🤖 `OPENAI_API_KEY` - Required for AI features
- 🗃️ `DATABASE_URL` - Database connection
- 💾 `REDIS_URL` - Cache connection
- 📊 `LOG_LEVEL` - Logging verbosity

## 🎯 Development Workflow

```bash
# Setup
make install          # Install dependencies
make local-setup      # Local PostgreSQL + Redis setup
make test-db          # Verify database connection

# Development
make start-backend    # Start FastAPI server
make frontend         # Start React dev server (in another terminal)

# Testing
make test            # Run test suite
make health          # Check all services

# Production
make build           # Build Docker images
make start           # Start all services
make logs            # View application logs
```

This structure supports a production-ready pharmaceutical research platform with AI-powered search, analysis, and discovery capabilities! 🔬✨
