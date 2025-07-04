#!/usr/bin/env python3
"""
Development configuration and utilities for Pharmaceutical Research Platform
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def setup_database():
    """Setup development database"""
    print("Setting up database...")
    
    try:
        from database import init_db
        init_db()
        print("✓ Database initialized")
        return True
    except Exception as e:
        print(f"Database setup failed: {e}")
        print("Make sure PostgreSQL is running and DATABASE_URL is correct in .env")
        return False

def run_tests():
    """Run test suite"""
    print("Running tests...")
    
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "test_config.py", "-v"],
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"Test execution failed: {e}")
        return False

def start_development_server():
    """Start development server"""
    print("Starting development server...")
    
    try:
        # Start uvicorn with reload
        subprocess.run([
            "uvicorn", 
            "main:app", 
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload",
            "--log-level", "info"
        ])
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Server start failed: {e}")

def show_status():
    """Show application status"""
    print("Application Status:")
    print("==================")
    
    # Check if services are running
    docker_cmd = check_docker()
    if docker_cmd:
        try:
            if docker_cmd == "docker compose":
                result = subprocess.run(
                    ["docker", "compose", "ps"],
                    capture_output=True,
                    text=True
                )
            else:
                result = subprocess.run(
                    ["docker-compose", "ps"],
                    capture_output=True,
                    text=True
                )
            print(result.stdout)
        except Exception as e:
            print(f"Could not check Docker service status: {e}")
    else:
        print("Docker not available - checking manual services...")
        
        # Check PostgreSQL
        try:
            result = subprocess.run(
                ["pg_isready", "-h", "localhost"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print("✓ PostgreSQL is running")
            else:
                print("✗ PostgreSQL is not running")
        except FileNotFoundError:
            print("? PostgreSQL status unknown (pg_isready not found)")
        
        # Check Redis
        try:
            result = subprocess.run(
                ["redis-cli", "ping"],
                capture_output=True,
                text=True
            )
            if "PONG" in result.stdout:
                print("✓ Redis is running")
            else:
                print("✗ Redis is not running")
        except FileNotFoundError:
            print("? Redis status unknown (redis-cli not found)")
    
    # Check if API is responding
    try:
        import requests
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✓ API is responding")
        else:
            print(f"✗ API responded with status {response.status_code}")
    except Exception as e:
        print(f"✗ API is not responding: {e}")

def check_docker():
    """Check if Docker and Docker Compose are available"""
    try:
        # Check docker
        subprocess.run(["docker", "--version"], capture_output=True, check=True)
        
        # Check docker-compose (new style)
        try:
            subprocess.run(["docker", "compose", "version"], capture_output=True, check=True)
            return "docker compose"
        except subprocess.CalledProcessError:
            pass
        
        # Check docker-compose (old style)
        try:
            subprocess.run(["docker-compose", "--version"], capture_output=True, check=True)
            return "docker-compose"
        except subprocess.CalledProcessError:
            pass
        
        return None
        
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

def start_services():
    """Start required services (database, redis)"""
    print("Starting services...")
    
    docker_cmd = check_docker()
    if not docker_cmd:
        print("❌ Docker not found. Please install Docker Desktop or use manual setup.")
        print("Manual setup options:")
        print("1. Install PostgreSQL: brew install postgresql")
        print("2. Install Redis: brew install redis")
        print("3. Start PostgreSQL: brew services start postgresql")
        print("4. Start Redis: brew services start redis")
        return False
    
    try:
        if docker_cmd == "docker compose":
            subprocess.run([
                "docker", "compose", "up", "-d", "postgres", "redis"
            ], check=True)
        else:
            subprocess.run([
                "docker-compose", "up", "-d", "postgres", "redis"
            ], check=True)
        
        print("✓ Services started")
        print("Waiting for services to be ready...")
        time.sleep(5)
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Failed to start services: {e}")
        print("Try manual setup with: make manual-setup")
        return False

def stop_services():
    """Stop all services"""
    print("Stopping services...")
    
    docker_cmd = check_docker()
    if not docker_cmd:
        print("❌ Docker not found. If using manual setup, stop services manually.")
        return False
    
    try:
        if docker_cmd == "docker compose":
            subprocess.run([
                "docker", "compose", "down"
            ], check=True)
        else:
            subprocess.run([
                "docker-compose", "down"
            ], check=True)
        
        print("✓ Services stopped")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Failed to stop services: {e}")
        return False

def manual_setup():
    """Manual setup without Docker"""
    print("Manual Setup (without Docker)")
    print("============================")
    
    print("1. Install PostgreSQL:")
    print("   brew install postgresql")
    print("   brew services start postgresql")
    print("   createdb pharma_research")
    print("")
    
    print("2. Install Redis:")
    print("   brew install redis")
    print("   brew services start redis")
    print("")
    
    print("3. Update .env file:")
    print("   DATABASE_URL=postgresql://$(whoami)@localhost:5432/pharma_research")
    print("   REDIS_URL=redis://localhost:6379")
    print("   OPENAI_API_KEY=your_openai_api_key_here")
    print("")
    
    print("4. Initialize database:")
    print("   python -c \"from database import init_db; init_db()\"")
    print("")
    
    print("5. Start backend:")
    print("   uvicorn main:app --host 0.0.0.0 --port 8000 --reload")

def check_requirements():
    """Check if all requirements are met"""
    print("Checking requirements...")
    
    # Check Python version
    python_version = sys.version_info
    if python_version < (3, 8):
        print("Error: Python 3.8+ required")
        return False
    
    # Check if .env file exists
    if not Path(".env").exists():
        print("Warning: .env file not found. Creating from template...")
        if Path(".env.template").exists():
            subprocess.run(["cp", ".env.template", ".env"])
            print("Please edit .env file with your API keys")
            return False
        else:
            print("Creating basic .env file...")
            with open(".env", "w") as f:
                f.write("""# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/pharma_research

# Redis Configuration  
REDIS_URL=redis://localhost:6379

# OpenAI API Key (Required)
OPENAI_API_KEY=your_openai_api_key_here

# Logging
LOG_LEVEL=INFO
""")
            print("Please edit .env file with your OpenAI API key")
            return False
    
    # Check if OpenAI API key is set
    from dotenv import load_dotenv
    load_dotenv()
    
    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your_openai_api_key_here":
        print("Error: OPENAI_API_KEY not set in .env file")
        return False
    
    print("✓ Requirements check passed")
    return True

def show_status():
    """Show application status"""
    print("Application Status:")
    print("==================")
    
    # Check if services are running
    try:
        result = subprocess.run(
            ["docker-compose", "ps"],
            capture_output=True,
            text=True
        )
        print(result.stdout)
    except Exception as e:
        print(f"Could not check service status: {e}")
    
    # Check if API is responding
    try:
        import requests
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✓ API is responding")
        else:
            print(f"✗ API responded with status {response.status_code}")
    except Exception as e:
        print(f"✗ API is not responding: {e}")

def main():
    """Main development command"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Development utilities")
    parser.add_argument(
        "command", 
        choices=["check", "setup", "test", "start", "stop", "status", "dev", "manual"],
        help="Command to run"
    )
    
    args = parser.parse_args()
    
    if args.command == "check":
        success = check_requirements()
        sys.exit(0 if success else 1)
    
    elif args.command == "setup":
        if not check_requirements():
            sys.exit(1)
        
        docker_cmd = check_docker()
        if not docker_cmd:
            print("Docker not found. Would you like to:")
            print("1. Install Docker Desktop")
            print("2. Use manual setup (Homebrew)")
            choice = input("Enter choice (1 or 2): ").strip()
            if choice == "2":
                manual_setup()
                sys.exit(0)
            else:
                print("Please install Docker Desktop and try again.")
                sys.exit(1)
        
        if not start_services():
            sys.exit(1)
        
        if not setup_database():
            sys.exit(1)
        
        print("✓ Development setup complete")
    
    elif args.command == "manual":
        manual_setup()
    
    elif args.command == "test":
        if not check_requirements():
            sys.exit(1)
        
        success = run_tests()
        sys.exit(0 if success else 1)
    
    elif args.command == "start":
        if not check_requirements():
            sys.exit(1)
        
        start_development_server()
    
    elif args.command == "stop":
        stop_services()
    
    elif args.command == "status":
        show_status()
    
    elif args.command == "dev":
        # Full development startup
        if not check_requirements():
            sys.exit(1)
        
        docker_cmd = check_docker()
        if not docker_cmd:
            print("Docker not found. Please run 'python dev_config.py manual' for manual setup.")
            sys.exit(1)
        
        if not start_services():
            sys.exit(1)
        
        if not setup_database():
            sys.exit(1)
        
        print("✓ Development environment ready")
        print("🚀 Starting development server...")
        print("Frontend: http://localhost:3000")
        print("Backend: http://localhost:8000")
        print("API Docs: http://localhost:8000/docs")
        
        start_development_server()

if __name__ == "__main__":
    main()