# 🏗️ Pharmaceutical Research Platform - Project Structure

```
pharma-research-platform/
├── main.py                     # 🚀 FastAPI application entry point
├── models.py                   # 🗃️ SQLAlchemy & Pydantic models
├── database.py                 # 🔗 Database connection & configuration
├── api_services.py             # 🌐 External API integrations (PubMed, Semantic Scholar, CrossRef)
├── ai_services.py              # 🤖 OpenAI integration (GPT-4, embeddings)
├── logging_config.py           # 📋 Logging setup & utilities
├── test_config.py              # 🧪 Test suite & mocking
├── dev_config.py               # 🛠️ Development utilities & commands
├── db_test.py                  # 🗃️ Database connection testing
├── requirements.txt            # 📦 Python dependencies (ROOT LEVEL)
├── docker-compose.yml          # 🐳 Multi-container orchestration
├── Dockerfile.backend          # 🐳 Backend container configuration
├── Dockerfile.frontend         # 🐳 Frontend container configuration
├── Makefile                    # ⚙️ Development commands & automation
├── startup.sh                  # 🚀 Application startup script
├── setup.sh                    # ⚙️ Automated setup script
├── .env.template               # 🔐 Environment variables template
├── .env                        # 🔒 Environment variables (git-ignored)
├── .gitignore                  # 🚫 Git exclusion rules
├── README.md                   # 📖 Main project documentation
├── PROJECT_STRUCTURE.md        # 🏗️ This file
├── MVP_COMPLETION.md           # ✅ MVP feature summary
└── frontend/                   # 📁 React Frontend Application
    ├── package.json            # 📦 Node.js dependencies & scripts
    ├── public/
    │   ├── index.html          # 📄 HTML template with loading fallback
    │   ├── manifest.json       # 📱 PWA manifest
    │   └── favicon.ico         # 🖼️ Site icon
    └── src/
        ├── App.js              # ⚛️ Main React application component
        ├── App.css             # 🎨 Application styles & responsive design
        └── index.js            # 🚪 React application entry point

📊 Runtime Data (Git-Ignored)
├── .git/                       # 🌱 Git repository data
├── venv/                       # 🐍 Python virtual environment
├── __pycache__/                # 📦 Python bytecode cache
├── *.pyc                       # 📦 Compiled Python files
├── *.db                        # 🗃️ SQLite database files
├── *.log                       # 📋 Application logs
├── postgres_data/              # 🗃️ PostgreSQL data volume (Docker)
├── redis_data/                 # 💾 Redis cache volume (Docker)
├── frontend/node_modules/      # 📦 Node.js packages
├── frontend/build/             # 🏗️ Production build output
└── tmp/                        # 📁 Temporary files
```

## 🔧 Architecture Overview

### Root Level (Backend & Infrastructure)
```
FastAPI Application Stack
├── 🚀 main.py                 # API endpoints, search, summarize, trends
├── 🗃️ models.py               # Article, SearchQuery, SearchResponse models
├── 🔗 database.py             # PostgreSQL/SQLite connection, session management
├── 🌐 api_services.py         # PubMed, Semantic Scholar, CrossRef integration
├── 🤖 ai_services.py          # OpenAI GPT-4, embeddings, similarity search
├── 📋 logging_config.py       # Structured logging, API/DB/AI loggers
├── 🧪 test_config.py          # Pytest suite with API mocking
├── 🛠️ dev_config.py           # Development commands and utilities
└── 🗃️ db_test.py              # Database connection validation
```

### Frontend Directory
```
frontend/
├── 📦 package.json            # React, dependencies, proxy to :8000
├── 📁 public/
│   ├── 📄 index.html          # Entry HTML with loading spinner
│   └── 📱 manifest.json       # PWA configuration
└── 📁 src/
    ├── ⚛️ App.js              # Main app, search, article cards, trends
    ├── 🎨 App.css             # Responsive CSS, modern styling
    └── 🚪 index.js            # React DOM rendering
```

### Infrastructure Files
```
Deployment & Development
├── 🐳 docker-compose.yml      # PostgreSQL + Redis + Backend + Frontend
├── 🐳 Dockerfile.backend      # Python FastAPI container
├── 🐳 Dockerfile.frontend     # Node.js React container  
├── ⚙️ Makefile               # install, setup, start, test, etc.
├── 🚀 startup.sh             # Automated application startup
├── 🔐 .env.template          # Environment variables template
└── 🚫 .gitignore             # Protects .env, node_modules, *.db, etc.
```

## 📊 Data Flow Architecture

```
🔍 User Search Input
    ↓
⚛️ React Frontend (App.js:handleSearch)
    ↓
🌐 HTTP POST /search
    ↓
🚀 FastAPI Backend (main.py:search_articles)
    ↓
🌐 API Manager (api_services.py)
    ↓ ↓ ↓
📚 PubMed    🧠 Semantic Scholar    📖 CrossRef
    ↓ ↓ ↓
🤖 AI Processing (ai_services.py)
    ↓
🧠 OpenAI GPT-4 & Embeddings
    ↓
🗃️ PostgreSQL Storage (database.py)
    ↓
📊 Processed Results
    ↓
⚛️ React Display (ArticleCard components)
```

## 🔄 Development Workflow

### Setup Commands
```bash
# Root directory operations
make install              # pip install -r requirements.txt + npm install
make local-setup         # PostgreSQL + Redis + database creation
make test-db             # Verify database connection

# Development servers
make start-backend       # uvicorn main:app --reload (port 8000)
make frontend           # cd frontend && npm start (port 3000)

# Docker operations  
make start              # docker-compose up -d (all services)
make stop               # docker-compose down
```

### File Locations for Development
```bash
# Backend development (root directory)
./main.py               # Add new API endpoints
./models.py             # Add new data models
./api_services.py       # Add new external APIs

# Frontend development
./frontend/src/App.js   # Add new React components
./frontend/src/App.css  # Add new styles

# Configuration
./.env                  # Set OPENAI_API_KEY, DATABASE_URL
./Makefile             # Add new development commands
```

## 🚀 Application Ports & URLs

### Development Mode
- **Frontend**: http://localhost:3000 (React dev server)
- **Backend API**: http://localhost:8000 (FastAPI)
- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **Health Check**: http://localhost:8000/health

### Docker Mode
- **Frontend**: http://localhost:3000 (Containerized React)
- **Backend API**: http://localhost:8000 (Containerized FastAPI)
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

## 📦 Dependencies

### Root Level Python (requirements.txt)
```python
fastapi==0.115.0          # Web framework
uvicorn[standard]==0.32.0 # ASGI server
sqlalchemy==2.0.36        # Database ORM
psycopg2-binary>=2.9.5    # PostgreSQL driver
pydantic==2.10.2          # Data validation
openai==1.57.0            # AI services
aiohttp==3.11.10          # HTTP client
numpy>=1.26.0             # Vector calculations
redis==5.2.0              # Caching
pytest==8.3.4             # Testing
```

### Frontend (frontend/package.json)
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-scripts": "5.0.1"
  },
  "proxy": "http://localhost:8000"
}
```

## 🔐 Environment Configuration

### Required (.env file)
```bash
# Core services
DATABASE_URL=postgresql://localhost:5432/pharma_research
REDIS_URL=redis://localhost:6379
OPENAI_API_KEY=sk-your-actual-openai-key-here

# Optional
LOG_LEVEL=INFO
PUBMED_RATE_LIMIT=3
SEMANTIC_SCHOLAR_RATE_LIMIT=100
```

### Protected by .gitignore
```bash
# Secrets & Environment
.env                    # API keys and database URLs
*.key, *.pem           # Certificates and keys

# Python Runtime
venv/                  # Virtual environment
__pycache__/           # Bytecode cache
*.pyc                  # Compiled Python

# Node.js Runtime  
frontend/node_modules/ # NPM packages
frontend/build/        # Production build

# Database & Logs
*.db                   # SQLite files
*.log                  # Application logs
postgres_data/         # Docker PostgreSQL volume
redis_data/           # Docker Redis volume
```

## 🎯 Key Features

### Backend Capabilities (Root Level)
- 🔍 **Multi-source search**: PubMed + Semantic Scholar + CrossRef
- 🤖 **AI summarization**: OpenAI GPT-4 structured summaries  
- 📊 **Trend analysis**: Topic frequency and emerging themes
- 🔗 **Similarity search**: Vector embeddings with cosine similarity
- 🗃️ **Database storage**: PostgreSQL with JSONB for flexibility
- 📋 **Comprehensive logging**: Request/response/error tracking

### Frontend Features (frontend/)
- ⚛️ **React interface**: Modern component-based UI
- 🔍 **Real-time search**: Live results with loading indicators
- 📄 **Article cards**: Expandable with metadata and actions
- 🤖 **AI interactions**: Summarize and find similar buttons
- 📊 **Trends sidebar**: Dynamic research trend analysis
- 📱 **Responsive design**: Works on desktop and mobile

### Infrastructure (Docker & Make)
- 🐳 **Containerization**: Full Docker Compose setup
- ⚙️ **Build automation**: Makefile with 20+ commands
- 🚀 **Easy deployment**: One-command startup
- 🧪 **Testing suite**: Database and API testing
- 📊 **Health monitoring**: Service status endpoints

This flat structure with a dedicated frontend/ folder provides clean separation while keeping backend files easily accessible in the root directory! 🔬✨
