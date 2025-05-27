# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Zapa is a WhatsApp Agent System that integrates WhatsApp messaging with AI-powered agent capabilities. The system follows a microservice architecture with clear separation between:

- **WhatsApp Bridge (Node.js + Baileys)**: Handles WhatsApp connectivity
- **Backend API (Python FastAPI)**: Core business logic and orchestration
- **Admin Frontend (Vue.js)**: Web interface for managing agents
- **PostgreSQL Database**: Central data storage
- **Redis/RabbitMQ (Optional)**: Message queue for async processing
- **LLM Providers**: Uses OpenAI Agents SDK with support for OpenAI, Anthropic, Google, or any OpenAI-compatible API

## Architecture Philosophy

This project strictly follows the **"Plumbing + Intelligence"** architecture model with three layers:

1. **Surface Layer (API/Controllers)**: HTTP endpoints, request parsing, authentication - NO business logic
2. **Service Layer**: Core business logic, orchestration, decision-making - the "intelligence"
3. **Adapter Layer**: External integrations (DB, APIs, message queues) - isolates complexity

## Development Commands

### Backend (Python FastAPI)

```bash
# Install dependencies
cd backend
pip install -e ".[dev]"

# Run private service (internal, webhooks, admin)
uvicorn private_main:app --reload --port 8001

# Run public service (external, user auth/dashboard)
uvicorn public_main:app --reload --port 8002

# Run tests
pytest -v

# Run with coverage
pytest -v --cov=app --cov=models --cov=schemas --cov-report=html

# Linting and formatting
black app/ models/ schemas/ tests/ private_main.py public_main.py
ruff check app/ models/ schemas/ tests/ private_main.py public_main.py

# Type checking
mypy app/ models/ schemas/

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "Description"
```

### Frontend (Vue.js)

```bash
# Install dependencies
cd frontend
npm install

# Run development server
npm run serve

# Build for production
npm run build

# Run unit tests
npm run test:unit

# Run E2E tests (Cypress)
npm run test:e2e

# Lint
npm run lint
```

### Docker Development

```bash
# Build and run all services
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f [service_name]

# Stop all services
docker-compose down

# Run with clean slate (remove volumes)
docker-compose down -v
```

### Database

```bash
# Connect to PostgreSQL in Docker
docker-compose exec db psql -U myuser -d whatsapp_agent

# Connect to local development database
psql -U myuser -d whatsapp_agent
```

## Key Architectural Patterns

### Dual Entrypoint Architecture

This is a **single backend project** with two FastAPI entrypoints:
- `private_main.py` → Private API (port 8001) - internal network only
- `public_main.py` → Public API (port 8002) - internet-facing

Both share the same codebase under `backend/app/` to avoid duplication.

### Backend Structure

```
backend/
├── app/
│   ├── core/           # Shared utilities (config, database, exceptions, security)
│   ├── models/         # SQLAlchemy ORM models
│   ├── schemas/        # Pydantic validation schemas
│   ├── adapters/       # External service integrations (WhatsApp, LLMs)
│   ├── services/       # Business logic layer
│   ├── private/        # Private API endpoints
│   │   └── api/v1/     # Version 1 private API routes
│   └── public/         # Public API endpoints
│       └── api/v1/     # Version 1 public API routes
├── alembic/            # Database migrations
├── tests/              # Test suite
├── private_main.py     # Private service entrypoint
└── public_main.py      # Public service entrypoint
```

### Service Communication

- **Webhooks**: WhatsApp Bridge → Backend Private API (for incoming messages/events)
- **REST API**: Backend → WhatsApp Bridge (for sending messages)
- **REST API**: Frontend → Backend Public API (for user operations)
- **WebSocket** (optional): Backend → Frontend (for real-time updates)

### Message Processing Flow

1. User sends WhatsApp message to main service number
2. Message arrives at Node.js Bridge (zapw)
3. Bridge sends webhook to Backend Private API `/webhooks/whatsapp`
4. Backend stores message and loads user's LLM configuration
5. AgentService calls user's configured LLM provider with:
   - The user's message
   - Recent conversation context
   - Tools to access full message history
6. LLM processes message and may use tools to search/analyze conversation history
7. Generated response sent back via Bridge REST API to user
8. Assistant's response stored in database

### LLM Agent Integration

The system uses the OpenAI Agents SDK (`openai-agents`) for agent capabilities. This provides:
- Built-in tool management with `@function_tool` decorators
- Structured outputs with Pydantic models
- Support for multiple LLM providers via custom clients
- Context management for passing database sessions to tools

Agent tools available:
- `search_messages(query: str, limit: int)` - Search through user's conversation history
- `get_recent_messages(count: int)` - Retrieve the N most recent messages
- `summarize_chat(last_n: int)` - Generate a summary of recent messages
- `extract_tasks()` - Extract to-do items from conversation
- `get_conversation_stats()` - Get statistics like message count, date range, etc.

## Environment Variables

### Backend
- `DATABASE_URL`: PostgreSQL connection string
- `WHATSAPP_API_URL`: WhatsApp Bridge service URL (internal network)
- `ADMIN_TOKEN_SECRET`: JWT signing secret
- `REDIS_URL`: Redis connection (if using)
- `ENCRYPTION_KEY`: Key for encrypting user API keys in database

### WhatsApp Bridge (zapw)
- `PORT`: Service port (default 3000)
- `WEBHOOK_URL`: Backend webhook endpoint  
- Note: No authentication required (secured via network isolation)

## Testing Strategy

- **Unit Tests**: Test services with mocked adapters
- **Integration Tests**: Test API endpoints with test database
- **E2E Tests**: Frontend tests with Cypress
- **Load Tests**: Use Locust for concurrent session testing

Test database uses SQLite in-memory for speed, production uses PostgreSQL.

## Security Considerations

- Admin authentication via JWT
- User authentication via WhatsApp codes from main number
- API key authentication between services (except WhatsApp Bridge)
- Rate limiting on message processing
- Input sanitization for LLM prompts
- XSS protection in frontend
- User API keys stored encrypted with Fernet symmetric encryption

## Development Tips

- Always update `spec/tasks/progress.log` when completing tasks
- Run tests before committing: `pytest -v`
- Ensure CI passes before merging
- Use `gh run list` to check CI status
- Follow TDD approach - write tests first
- Keep adapter implementations isolated with clear interfaces

## Common Pitfalls

- WhatsApp Bridge adapter requires phone numbers in format: `{number}@s.whatsapp.net`
- SQLAlchemy 2.0 requires `text()` wrapper for raw SQL queries
- Mock `httpx` responses carefully - `json()` is sync, not async
- Remember to add `__init__.py` files to make directories proper Python packages
- Use `pytest.ini` with `pythonpath = .` for backend tests to resolve imports

## Current Implementation Status

Check `spec/tasks/progress.log` for detailed task completion status. As of last update:
- Tasks 01-06: ✅ Complete
- Task 07: LLM Adapter using OpenAI Agents SDK (in progress)
- Tasks 08-16: Pending

## Memories and Guidelines

- Always commit and push frequently when reaching a good state
- Use `gh` CLI for GitHub operations
- No need to ask for permission to commit
- Check CI status regularly with `gh run list`