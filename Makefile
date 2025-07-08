# Pharmaceutical Research Platform - Makefile

.PHONY: help install setup start stop test clean logs status dev

# Default target
help:
	@echo "Pharmaceutical Research Platform - Development Commands"
	@echo "======================================================"
	@echo "install       - Install dependencies"
	@echo "setup         - Setup development environment (with Docker)"
	@echo "manual-setup  - Manual setup instructions (without Docker)"
	@echo "quick-setup   - Quick setup without Docker (manual steps)"
	@echo "local-setup   - Complete local setup (automated, no Docker)"
	@echo "start         - Start all services (Docker)"
	@echo "stop          - Stop all services (Docker)"
	@echo "test          - Run test suite"
	@echo "test-db       - Test database connection"
	@echo "init-db       - Initialize database tables"
	@echo "start-backend - Start backend server only"
	@echo "check-env     - Check environment configuration"
	@echo "clean         - Clean up containers and volumes"
	@echo "logs          - View application logs"
	@echo "status        - Show service status"
	@echo "dev           - Start development environment"
	@echo "backend       - Start backend with Docker services"
	@echo "frontend      - Start frontend only"
	@echo "db            - Start database services only (Docker)"
	@echo "debug         - Show debug information"

# Install dependencies
install:
	@echo "Installing Python dependencies..."
	@if command -v pip3 >/dev/null 2>&1; then \
		pip3 install -r requirements.txt --break-system-packages; \
	elif command -v pip >/dev/null 2>&1; then \
		pip install -r requirements.tx --break-system-packages; \
	else \
		python3 -m pip install -r requirements.txt --break-system-packages; \
	fi
	@echo "Installing Node.js dependencies..."
	@if [ -d "frontend" ]; then \
		cd frontend && npm install; \
	else \
		echo "Frontend directory not found, skipping npm install"; \
	fi
	@echo "✓ Dependencies installed"

# Setup development environment
setup:
	@echo "Setting up development environment..."
	@if [ ! -f .env ]; then \
		cp .env.template .env; \
		echo "Created .env file - please edit with your API keys"; \
		exit 1; \
	fi
	@if [ -f ./dev_config.py ]; then \
		python ./dev_config.py setup; \
	else \
		echo "dev_config.py not found. Creating basic setup..."; \
		python -c "from database import init_db; init_db()"; \
	fi
	@echo "✓ Development environment ready"

# Start all services
start:
	@echo "Starting all services..."
	@docker-compose up -d
	@echo "✓ All services started"
	@echo "Frontend: http://localhost:3000"
	@echo "Backend: http://localhost:8000"
	@echo "API Docs: http://localhost:8000/docs"

# Stop all services
stop:
	@echo "Stopping all services..."
	@docker-compose down
	@echo "✓ All services stopped"

# Run tests
test:
	@echo "Running test suite..."
	@if command -v python3 >/dev/null 2>&1; then \
		python3 -m pytest test_config.py -v; \
	elif command -v python >/dev/null 2>&1; then \
		python -m pytest test_config.py -v; \
	else \
		echo "Error: Python not found"; \
		exit 1; \
	fi
	@echo "✓ Tests completed"

# Clean up
clean:
	@echo "Cleaning up containers and volumes..."
	@docker-compose down -v
	@docker system prune -f
	@echo "✓ Cleanup completed"

# View logs
logs:
	@docker-compose logs -f

# Show status
status:
	@echo "Service Status:"
	@echo "==============="
	@docker-compose ps
	@echo ""
	@echo "API Health Check:"
	@curl -s http://localhost:8000/health | python -m json.tool || echo "API not responding"

# Development mode
dev:
	@echo "Starting development environment..."
	@python dev_config.py dev

# Backend only
backend:
	@echo "Starting backend services..."
	@docker-compose up -d postgres redis
	@echo "Waiting for services..."
	@sleep 5
	@echo "Starting backend..."
	@if [ -f ./main.py ]; then \
		uvicorn main:app --host 0.0.0.0 --port 8000 --reload; \
	else \
		echo "main.py not found in current directory"; \
		ls -la *.py; \
	fi

# Frontend only
frontend:
	@echo "Starting frontend..."
	@if [ ! -d "frontend" ]; then \
		echo "Error: frontend directory not found"; \
		exit 1; \
	fi
	@if [ ! -f "frontend/package.json" ]; then \
		echo "Error: frontend/package.json not found"; \
		exit 1; \
	fi
	@if [ ! -d "frontend/node_modules" ]; then \
		echo "Installing frontend dependencies..."; \
		cd frontend && npm install; \
	fi
	@echo "Starting React development server..."
	@cd frontend && npm start

# Database services only
db:
	@echo "Starting database services..."
	@docker-compose up -d postgres redis
	@echo "✓ Database services started"

# Quick development commands
quick-start: db
	@echo "Quick start - database services ready"
	@echo "Run 'make backend' in another terminal to start API"
	@echo "Run 'make frontend' in another terminal to start UI"

# Manual setup without Docker
manual-setup:
	@echo "Manual setup (without Docker)..."
	@echo "1. Install PostgreSQL and Redis:"
	@echo "   brew install postgresql redis"
	@echo "2. Start services:"
	@echo "   brew services start postgresql"
	@echo "   brew services start redis"
	@echo "3. Create database:"
	@echo "   createdb pharma_research"
	@echo "4. Update .env with local URLs and run 'make setup'"
	@echo "5. Initialize database:"
	@echo "   python -c \"from database import init_db; init_db()\""

# Quick setup without Docker
quick-setup:
	@echo "Quick setup without Docker..."
	@if [ ! -f .env ]; then \
		cp .env.template .env; \
		echo "DATABASE_URL=postgresql://$(shell whoami)@localhost:5432/pharma_research" >> .env; \
		echo "REDIS_URL=redis://localhost:6379" >> .env; \
		echo "Please edit .env with your OpenAI API key"; \
	fi
	@echo "Next steps:"
	@echo "1. brew install postgresql redis"
	@echo "2. brew services start postgresql redis"
	@echo "3. createdb pharma_research"
	@echo "4. Edit .env with OpenAI API key"
	@echo "5. make init-db"
	@echo "6. make start-backend"

# Test database connection
test-db:
	@echo "Testing database connection..."
	@python db_test.py

# Initialize database only
init-db:
	@echo "Initializing database..."
	@python -c "from database import init_db; init_db()"

# Simple backend start (assumes DB is ready)
start-backend:
	@echo "Starting backend server..."
	@uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Check environment
check-env:
	@echo "Environment Check:"
	@echo "=================="
	@echo "Python version: $(shell python --version)"
	@echo "Current directory: $(shell pwd)"
	@echo "Database URL: $(shell python -c 'import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv("DATABASE_URL", "Not set"))')"
	@echo "OpenAI API Key: $(shell python -c 'import os; from dotenv import load_dotenv; load_dotenv(); key=os.getenv("OPENAI_API_KEY", "Not set"); print("Set" if key and key != "Not set" and key != "your_openai_api_key_here" else "Not set")')"

# Complete local setup
local-setup:
	@echo "Complete local setup (no Docker)..."
	@echo "Step 1: Installing PostgreSQL and Redis..."
	@brew install postgresql redis || echo "brew install failed - install manually"
	@echo "Step 2: Starting services..."
	@brew services start postgresql || echo "PostgreSQL start failed"
	@brew services start redis || echo "Redis start failed"
	@echo "Step 3: Creating database..."
	@createdb pharma_research || echo "Database creation failed - may already exist"
	@echo "Step 4: Setting up environment..."
	@if [ ! -f .env ]; then \
		cp .env.template .env; \
		sed -i.bak 's|postgresql://user:password@localhost:5432/pharma_research|postgresql://$(shell whoami)@localhost:5432/pharma_research|g' .env; \
		sed -i.bak 's|redis://localhost:6379|redis://localhost:6379|g' .env; \
		echo "Please edit .env with your OpenAI API key"; \
	fi
	@echo "Step 5: Testing database..."
	@make test-db || echo "Database test failed"
	@echo "✓ Local setup complete!"
	@echo "Edit .env with OpenAI API key, then run: make start-backend"

# Production build
build:
	@echo "Building production images..."
	@docker-compose build
	@echo "✓ Production images built"

# Database operations
db-reset:
	@echo "Resetting database..."
	@docker-compose down postgres
	@docker volume rm pharma-research-platform_postgres_data || true
	@docker-compose up -d postgres
	@sleep 5
	@python -c "from database import init_db; init_db()"
	@echo "✓ Database reset completed"

# Lint and format
lint:
	@echo "Running linting..."
	@python -m flake8 --max-line-length=120 --ignore=E501 *.py
	@echo "✓ Linting completed"

format:
	@echo "Formatting code..."
	@python -m black --line-length=120 *.py
	@echo "✓ Code formatted"

# Backup database
backup:
	@echo "Creating database backup..."
	@docker-compose exec postgres pg_dump -U user pharma_research > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "✓ Database backup created"

# Performance test
perf-test:
	@echo "Running performance tests..."
	@python -c "import requests; import time; start=time.time(); r=requests.post('http://localhost:8000/search', json={'query': 'cancer', 'limit': 5}); print(f'Search took {time.time()-start:.2f}s, Status: {r.status_code}')"

# Health check
health:
	@curl -s http://localhost:8000/health | python -m json.tool

# Debug - show current directory and files
debug:
	@echo "Current directory:"
	@pwd
	@echo "Python files in current directory:"
	@ls -la *.py 2>/dev/null || echo "No Python files found"
	@echo "All files:"
	@ls -la
	@echo "Python version:"
	@python --version
	@echo "Make version:"
	@make --version | head -1

# Interactive development
shell:
	@echo "Starting Python shell with app context..."
	@python -c "from main import app; from database import get_db; import IPython; IPython.embed()"