# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Zapa is a WhatsApp Agent System that integrates WhatsApp messaging with AI-powered agent capabilities. The system follows a microservice architecture with clear separation between:

- **WhatsApp Bridge (Node.js + Baileys)**: Handles WhatsApp connectivity
- **Backend API (Python FastAPI)**: Core business logic and orchestration
- **Admin Frontend (Vue.js)**: Web interface for managing agents
- **PostgreSQL Database**: Central data storage
- **Redis/RabbitMQ (Optional)**: Message queue for async processing
- **LLM Providers**: OpenAI, Anthropic, or Google (user-configurable) for agent intelligence

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
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest -v

# Run with coverage
pytest --cov=app --cov-report=html

# Linting
flake8 app/
black app/ --check

# Format code
black app/
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

# Run migrations (when implemented)
cd backend
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "Description"
```

## Key Architectural Patterns

### Backend Structure

The backend follows a strict layered architecture:

```
backend/app/
├── api/          # Surface layer - FastAPI routers (no business logic)
├── services/     # Service layer - Business logic and orchestration
├── adapters/     # Adapter layer - External integrations
├── models/       # Data models and schemas
└── core/         # Shared utilities and configuration
```

### Service Communication

- **Webhooks**: WhatsApp Bridge → Backend (for incoming messages/events)
- **REST API**: Backend → WhatsApp Bridge (for sending messages)
- **REST API**: Frontend → Backend (for admin operations)
- **WebSocket** (optional): Backend → Frontend (for real-time updates)

### Message Processing Flow

1. WhatsApp message arrives at Node.js Bridge
2. Bridge sends webhook to Backend `/webhooks/whatsapp`
3. Backend processes message in MessageService
4. If AI response needed, AgentService calls user's configured LLM provider with function definitions
5. Response sent back via Bridge REST API

### LLM Function Calling

The system uses function calling (supported by all providers) for agent commands:
- `summarize_chat(last_n: int)` - Summarizes recent messages
- `extract_tasks()` - Extracts to-do items from conversation
- `search_messages(query: str)` - Semantic search in chat history

## Environment Variables

### Backend
- `DATABASE_URL`: PostgreSQL connection string
- `WHATSAPP_API_URL`: WhatsApp Bridge service URL
- `WHATSAPP_API_KEY`: Shared secret for Bridge authentication
- `ADMIN_TOKEN_SECRET`: JWT signing secret
- `REDIS_URL`: Redis connection (if using)
- `ENCRYPTION_KEY`: Key for encrypting user API keys in database

### WhatsApp Bridge
- `PORT`: Service port (default 3000)
- `WEBHOOK_URL`: Backend webhook endpoint
- `API_KEY`: API authentication key

## Testing Strategy

- **Unit Tests**: Test services with mocked adapters
- **Integration Tests**: Test API endpoints with test database
- **E2E Tests**: Frontend tests with Cypress
- **Load Tests**: Use Locust for concurrent session testing

## Security Considerations

- Admin authentication via JWT
- API key authentication between services
- Rate limiting on message processing
- Input sanitization for LLM prompts
- XSS protection in frontend
- Secrets managed via environment variables

## Development Tips

- Remember to commit and push frequently whenever you reach a good state

## Memories and Guidelines

- Always keep a log of your tasks progress in spec/tasks/progress.log