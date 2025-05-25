# Task 17: Docker Setup and Container Orchestration

## Objective
Create comprehensive Docker configuration for all services with proper networking, volumes, and health checks.

## Prerequisites
- All backend services implemented
- Frontend build process ready
- Understanding of Docker networking and volumes

## Requirements
- Create optimized Dockerfiles for each service
- Set up Docker Compose for local development
- Configure proper health checks
- Implement container security best practices
- Create development and production configurations

## Files to Create

### backend/Dockerfile
```dockerfile
# Build stage
FROM python:3.10-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml .
COPY README.md .

# Create virtual environment and install dependencies
RUN uv venv && \
    . .venv/bin/activate && \
    uv pip install -e .

# Runtime stage
FROM python:3.10-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY app app/
COPY alembic alembic/
COPY alembic.ini .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Set Python path
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### backend/.dockerignore
```
**/__pycache__
**/*.pyc
**/*.pyo
**/*.pyd
.Python
*.egg-info
*.egg
.venv
.uv
.coverage
.pytest_cache
htmlcov
.git
.gitignore
.dockerignore
Dockerfile
docker-compose*.yml
tests/
docs/
.env
.env.*
*.log
```

### frontend/Dockerfile
```dockerfile
# Build stage
FROM node:18-alpine as builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY . .

# Build application
RUN npm run build

# Runtime stage
FROM nginx:alpine

# Install curl for health checks
RUN apk add --no-cache curl

# Copy built application
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Create non-root user
RUN adduser -D -u 1000 appuser && \
    chown -R appuser:appuser /usr/share/nginx/html && \
    chown -R appuser:appuser /var/cache/nginx && \
    chown -R appuser:appuser /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown appuser:appuser /var/run/nginx.pid

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:80/health || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### frontend/nginx.conf
```nginx
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;

    # Compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml application/json application/javascript application/xml+rss application/atom+xml image/svg+xml;

    # API proxy
    location /api {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }

    # SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### docker-compose.yml (Development)
```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-postgres}
      POSTGRES_DB: ${DB_NAME:-whatsapp_agent}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    networks:
      - app-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-postgres}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    networks:
      - app-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  whatsapp-bridge:
    build: ./whatsapp-bridge
    environment:
      PORT: 3000
      WEBHOOK_URL: http://backend:8000/api/v1/messages/webhook
      WEBHOOK_AUTH_TOKEN: ${WHATSAPP_API_KEY}
      API_KEY: ${WHATSAPP_API_KEY}
      LOG_LEVEL: info
    volumes:
      - whatsapp_sessions:/app/sessions_data
    ports:
      - "3000:3000"
    networks:
      - app-network
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped

  backend:
    build: 
      context: ./backend
      target: runtime
    environment:
      DATABASE_URL: postgresql://${DB_USER:-postgres}:${DB_PASSWORD:-postgres}@db:5432/${DB_NAME:-whatsapp_agent}
      REDIS_URL: redis://redis:6379/0
      WHATSAPP_API_URL: http://whatsapp-bridge:3000
      WHATSAPP_API_KEY: ${WHATSAPP_API_KEY}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      SECRET_KEY: ${SECRET_KEY}
      ADMIN_TOKEN_SECRET: ${ADMIN_TOKEN_SECRET}
    volumes:
      - ./backend/app:/app/app:ro  # Mount source for hot reload
      - ./backend/alembic:/app/alembic:ro
    ports:
      - "8000:8000"
    networks:
      - app-network
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    networks:
      - app-network
    depends_on:
      backend:
        condition: service_healthy

  # Development tools
  pgadmin:
    image: dpage/pgadmin4:latest
    environment:
      PGADMIN_DEFAULT_EMAIL: ${PGADMIN_EMAIL:-admin@example.com}
      PGADMIN_DEFAULT_PASSWORD: ${PGADMIN_PASSWORD:-admin}
    ports:
      - "5050:80"
    networks:
      - app-network
    depends_on:
      - db
    profiles:
      - tools

volumes:
  postgres_data:
  redis_data:
  whatsapp_sessions:

networks:
  app-network:
    driver: bridge
```

### docker-compose.prod.yml (Production)
```yaml
version: '3.8'

services:
  backend:
    image: ${DOCKER_REGISTRY}/whatsapp-agent-backend:${VERSION:-latest}
    environment:
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: ${REDIS_URL}
      WHATSAPP_API_URL: ${WHATSAPP_API_URL}
      WHATSAPP_API_KEY: ${WHATSAPP_API_KEY}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      SECRET_KEY: ${SECRET_KEY}
      ADMIN_TOKEN_SECRET: ${ADMIN_TOKEN_SECRET}
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3

  frontend:
    image: ${DOCKER_REGISTRY}/whatsapp-agent-frontend:${VERSION:-latest}
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '0.5'
          memory: 256M

  whatsapp-bridge:
    image: ${DOCKER_REGISTRY}/whatsapp-bridge:${VERSION:-latest}
    deploy:
      replicas: 1  # Only one instance per phone number
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
```

### .env.example
```bash
# Database
DB_USER=postgres
DB_PASSWORD=secure-password-here
DB_NAME=whatsapp_agent
DATABASE_URL=postgresql://postgres:secure-password-here@db:5432/whatsapp_agent

# Redis
REDIS_URL=redis://redis:6379/0

# Security
SECRET_KEY=your-secret-key-here-generate-with-openssl-rand-hex-32
ADMIN_TOKEN_SECRET=your-admin-token-secret-here
WHATSAPP_API_KEY=your-whatsapp-api-key-here

# OpenAI
OPENAI_API_KEY=your-openai-api-key-here

# Docker Registry (for production)
DOCKER_REGISTRY=docker.io/yourusername

# PgAdmin (development only)
PGADMIN_EMAIL=admin@example.com
PGADMIN_PASSWORD=admin
```

### Makefile
```makefile
.PHONY: help build up down logs test clean

help:
	@echo "Available commands:"
	@echo "  make build    - Build all Docker images"
	@echo "  make up       - Start all services"
	@echo "  make down     - Stop all services"
	@echo "  make logs     - View logs"
	@echo "  make test     - Run tests in containers"
	@echo "  make clean    - Clean up volumes and images"

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

test:
	docker-compose run --rm backend pytest tests -v

migrate:
	docker-compose run --rm backend alembic upgrade head

shell-backend:
	docker-compose exec backend /bin/bash

shell-db:
	docker-compose exec db psql -U postgres -d whatsapp_agent

clean:
	docker-compose down -v
	docker system prune -f
```

### scripts/init-db.sql
```sql
-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create initial admin user (password: admin123)
-- Note: Change this in production!
INSERT INTO users (username, email, hashed_password, is_active)
VALUES (
    'admin',
    'admin@example.com',
    '$2b$12$YourHashedPasswordHere',
    true
) ON CONFLICT DO NOTHING;
```

### scripts/docker-test.sh
```bash
#!/bin/bash
set -e

echo "Running tests in Docker..."

# Build test image
docker build -t whatsapp-agent-test -f backend/Dockerfile.test backend/

# Run tests
docker run --rm \
    -e DATABASE_URL=sqlite:///test.db \
    -e WHATSAPP_API_URL=http://localhost:3000 \
    -e OPENAI_API_KEY=test-key \
    whatsapp-agent-test \
    pytest tests -v --cov=app --cov-report=term-missing

echo "Tests completed!"
```

## Docker Security Best Practices

### backend/Dockerfile.test
```dockerfile
FROM python:3.10-slim

# Install dependencies
RUN apt-get update && apt-get install -y gcc libpq-dev curl

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy files
COPY pyproject.toml README.md ./
COPY app app/
COPY tests tests/

# Install dependencies
RUN uv venv && \
    . .venv/bin/activate && \
    uv pip install -e . && \
    uv pip install pytest pytest-asyncio pytest-cov

ENV PATH="/app/.venv/bin:$PATH"

CMD ["pytest"]
```

## Success Criteria
- [ ] All services have optimized Dockerfiles
- [ ] Docker Compose configuration for development
- [ ] Production-ready configuration
- [ ] Health checks implemented
- [ ] Volumes for persistent data
- [ ] Security best practices applied
- [ ] Tests can run in containers
- [ ] Documentation for Docker commands

## Commands to Run
```bash
# Build all images
make build

# Start development environment
make up

# View logs
make logs

# Run tests
make test

# Run database migrations
make migrate

# Access backend shell
make shell-backend

# Stop everything
make down

# Clean up
make clean
```