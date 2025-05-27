# Zapa - WhatsApp Agent System

A powerful WhatsApp agent system that integrates AI-powered conversational capabilities with WhatsApp messaging. Built with a microservices architecture for scalability and flexibility.

## 🚀 Features

- **AI-Powered Conversations**: Integrate with multiple LLM providers (OpenAI, Anthropic, Google)
- **WhatsApp Integration**: Seamless messaging through WhatsApp Business API
- **Multi-Provider Support**: Switch between different AI providers on the fly
- **Secure Authentication**: WhatsApp-based authentication (no passwords!)
- **Admin Dashboard**: Vue.js frontend for managing agents and users
- **Message History**: Full conversation history with search capabilities
- **Real-time Processing**: Async message handling with Redis queuing
- **Tool Integration**: AI agents can search messages, extract tasks, and more

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  WhatsApp Users │────▶│ WhatsApp Bridge │────▶│  Zapa Private   │
└─────────────────┘     │    (Node.js)    │     │   (Port 8001)   │
                        └─────────────────┘     └─────────────────┘
                                                         │
                        ┌─────────────────┐              │
                        │   Zapa Public   │◀─────────────┘
                        │   (Port 8002)   │
                        └─────────────────┘
                                │
                        ┌───────▼─────────┐     ┌─────────────────┐
                        │  Admin Frontend │     │     Database    │
                        │    (Vue.js)     │     │  (PostgreSQL)   │
                        └─────────────────┘     └─────────────────┘
```

### Key Components

- **WhatsApp Bridge (zapw)**: Node.js service handling WhatsApp connectivity
- **Zapa Private API**: Internal service for webhooks and admin operations
- **Zapa Public API**: External service for user authentication and data access
- **Admin Frontend**: Vue.js application for system management
- **PostgreSQL Database**: Central data storage
- **Redis**: Message queuing and caching

## 🛠️ Tech Stack

### Backend
- **Python 3.11+** with FastAPI
- **SQLAlchemy 2.0** for ORM
- **Alembic** for database migrations
- **OpenAI Agents SDK** for LLM integration
- **Redis** for queuing
- **PostgreSQL** for data storage

### Frontend
- **Vue.js 3** with Composition API
- **Tailwind CSS** for styling
- **Vite** for build tooling

### Infrastructure
- **Docker** & **Docker Compose**
- **GitHub Actions** for CI/CD

## 📋 Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose (optional)

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/tonylampada/zapa.git
cd zapa
```

### 2. Set up environment variables
```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Install dependencies
```bash
# Backend
pip install -e ".[dev]"

# Frontend (if applicable)
cd frontend
npm install
```

### 4. Run database migrations
```bash
alembic upgrade head
```

### 5. Start the services

#### Using Docker Compose (Recommended)
```bash
docker-compose up
```

#### Manual startup
```bash
# Terminal 1: Private API
uvicorn private_main:app --reload --port 8001

# Terminal 2: Public API  
uvicorn public_main:app --reload --port 8002

# Terminal 3: WhatsApp Bridge (if running locally)
cd ../zapw
npm start
```

## 🧪 Testing

### Run all tests
```bash
pytest -v
```

### Run with coverage
```bash
pytest -v --cov=app --cov=models --cov=schemas --cov-report=html
```

### Run specific test categories
```bash
# Unit tests only
pytest tests/unit -v

# Integration tests (requires services)
INTEGRATION_TEST_DATABASE=true pytest tests/integration -v
```

## 📚 API Documentation

Once running, API documentation is available at:
- Private API: http://localhost:8001/docs
- Public API: http://localhost:8002/docs

## 🔧 Development

### Project Structure
```
zapa/
├── app/                    # Main application code
│   ├── adapters/          # External service integrations
│   ├── core/              # Core utilities and config
│   ├── models/            # SQLAlchemy models
│   ├── schemas/           # Pydantic schemas
│   ├── services/          # Business logic
│   ├── private/           # Private API routes
│   └── public/            # Public API routes
├── tests/                 # Test suite
├── alembic/               # Database migrations
├── private_main.py        # Private API entrypoint
├── public_main.py         # Public API entrypoint
└── docker-compose.yml     # Docker orchestration
```

### Code Quality
```bash
# Format code
black app/ models/ schemas/ tests/ private_main.py public_main.py

# Lint
ruff check app/ models/ schemas/ tests/

# Type checking
mypy app/ models/ schemas/
```

### Creating new migrations
```bash
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

## 🔒 Security

- API keys are encrypted at rest using Fernet encryption
- JWT-based authentication for admin access
- WhatsApp-based authentication for users (no passwords stored)
- Network isolation between services
- Rate limiting on sensitive endpoints

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow TDD approach - write tests first
- Maintain test coverage above 90%
- Use type hints for all functions
- Follow the existing code style
- Update documentation as needed

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Built on top of the [zapw](https://github.com/tonylampada/zapw) WhatsApp Bridge
- Uses [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) for LLM integration
- Inspired by modern microservices architecture patterns

## 📞 Support

For issues and feature requests, please use the [GitHub Issues](https://github.com/tonylampada/zapa/issues) page.

---

**Note**: This project is under active development. Check the [task progress log](spec/tasks/progress.log) for the latest implementation status.