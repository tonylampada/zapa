# WhatsApp Agent System Architecture

## Overview

The WhatsApp Agent System is a microservices-based platform that enables businesses to deploy AI-powered agents for WhatsApp conversations. The system follows a **"Plumbing + Intelligence"** architecture pattern, strictly separating infrastructure concerns from business logic.

## System Architecture

```mermaid
graph TB
    subgraph "External Services"
        WA[WhatsApp Network]
        OAI[OpenAI API]
    end
    
    subgraph "Frontend Layer"
        UI[Vue.js Dashboard]
        NGINX[Nginx Server]
    end
    
    subgraph "Backend Services"
        API[FastAPI Backend]
        AUTH[Auth Service]
        MSG[Message Service]
        AGT[Agent Service]
        CMD[Command Service]
    end
    
    subgraph "Infrastructure"
        WB[WhatsApp Bridge<br/>zapw/Baileys]
        DB[(PostgreSQL)]
        REDIS[(Redis)]
        VS[Vector Store]
    end
    
    UI --> NGINX
    NGINX --> API
    API --> AUTH
    API --> MSG
    API --> AGT
    API --> CMD
    
    MSG --> AGT
    AGT --> OAI
    CMD --> OAI
    
    API <--> WB
    WB <--> WA
    
    API --> DB
    API --> REDIS
    AGT --> VS
    
    style API fill:#f9f,stroke:#333,stroke-width:4px
    style WB fill:#9ff,stroke:#333,stroke-width:2px
    style UI fill:#ff9,stroke:#333,stroke-width:2px
```

## Component Architecture

### Backend Layer Architecture

```mermaid
graph LR
    subgraph "Surface Layer (Plumbing)"
        RT[FastAPI Routes]
        MW[Middleware]
        DEP[Dependencies]
    end
    
    subgraph "Service Layer (Intelligence)"
        SS[SessionService]
        MS[MessageService]
        AS[AgentService]
        CS[CommandService]
        AUS[AuthService]
    end
    
    subgraph "Adapter Layer (Plumbing)"
        WC[WhatsApp Client]
        OC[OpenAI Client]
        DR[DB Repository]
        VS[Vector Store]
        CQ[Cache/Queue]
    end
    
    RT --> SS
    RT --> MS
    RT --> AS
    RT --> CS
    RT --> AUS
    
    SS --> WC
    SS --> DR
    
    MS --> AS
    MS --> DR
    MS --> WC
    
    AS --> OC
    AS --> DR
    AS --> VS
    
    CS --> OC
    CS --> DR
    CS --> VS
    
    style RT fill:#faa,stroke:#333,stroke-width:2px
    style SS fill:#afa,stroke:#333,stroke-width:2px
    style MS fill:#afa,stroke:#333,stroke-width:2px
    style AS fill:#afa,stroke:#333,stroke-width:2px
    style WC fill:#aaf,stroke:#333,stroke-width:2px
    style OC fill:#aaf,stroke:#333,stroke-width:2px
```

## Data Flow Diagrams

### Session Creation Flow

```mermaid
sequenceDiagram
    participant Admin
    participant Frontend
    participant Backend
    participant Bridge
    participant WhatsApp
    
    Admin->>Frontend: Click "Create Session"
    Frontend->>Backend: POST /api/v1/sessions
    Backend->>Backend: Create session record
    Backend->>Bridge: POST /sessions
    Bridge->>Bridge: Generate QR code
    Bridge-->>Backend: Return QR code
    Backend-->>Frontend: Return session + QR
    Frontend->>Admin: Display QR code
    Admin->>WhatsApp: Scan QR code
    WhatsApp->>Bridge: Authenticate
    Bridge->>Backend: Webhook: session.connected
    Backend->>Backend: Update session status
    Backend-->>Frontend: Session connected
```

### Message Processing Flow

```mermaid
sequenceDiagram
    participant User
    participant WhatsApp
    participant Bridge
    participant Backend
    participant OpenAI
    
    User->>WhatsApp: Send message
    WhatsApp->>Bridge: Message received
    Bridge->>Backend: Webhook: message.received
    Backend->>Backend: Store message
    
    alt Is Command?
        Backend->>Backend: Process command
        Backend->>OpenAI: Function call
        OpenAI-->>Backend: Function result
    else Regular Message
        Backend->>OpenAI: Chat completion
        OpenAI-->>Backend: AI response
    end
    
    Backend->>Bridge: Send response
    Bridge->>WhatsApp: Deliver message
    WhatsApp->>User: Show response
```

## Database Schema

```mermaid
erDiagram
    USERS ||--o{ SESSIONS : manages
    AGENTS ||--o{ SESSIONS : powers
    SESSIONS ||--o{ MESSAGES : contains
    SESSIONS ||--o{ LOGS : generates
    
    USERS {
        int id PK
        string username UK
        string email UK
        string hashed_password
        boolean is_active
        int failed_login_attempts
        datetime last_failed_login
        datetime created_at
        datetime updated_at
    }
    
    AGENTS {
        int id PK
        string name
        text description
        string model
        text system_prompt
        json functions
        boolean is_active
        datetime created_at
        datetime updated_at
    }
    
    SESSIONS {
        string id PK
        enum status
        string phone_number
        text qr_code
        int agent_id FK
        datetime connected_at
        datetime disconnected_at
        datetime created_at
        datetime updated_at
    }
    
    MESSAGES {
        int id PK
        string session_id FK
        string contact_jid
        enum direction
        string message_type
        text content
        string media_url
        json metadata
        datetime timestamp
    }
    
    LOGS {
        int id PK
        enum level
        string source
        text message
        json details
        string session_id FK
        datetime timestamp
    }
```

## Technology Stack

### Backend Stack
- **Framework**: FastAPI (Python 3.10+)
- **ORM**: SQLAlchemy 2.0
- **Database**: PostgreSQL 15
- **Cache/Queue**: Redis 7 (optional)
- **Package Manager**: UV
- **Testing**: Pytest + pytest-asyncio
- **Migration**: Alembic

### Frontend Stack
- **Framework**: Vue 3 (Composition API)
- **Language**: TypeScript
- **Build Tool**: Vite
- **State Management**: Pinia
- **Router**: Vue Router 4
- **HTTP Client**: Axios
- **Testing**: Vitest + Vue Test Utils
- **UI Components**: Custom components

### Infrastructure
- **Containerization**: Docker + Docker Compose
- **Web Server**: Nginx (frontend)
- **Process Manager**: Uvicorn (backend)
- **CI/CD**: GitHub Actions
- **Monitoring**: Health checks + custom monitoring service

## Security Architecture

```mermaid
graph TB
    subgraph "Authentication & Authorization"
        JWT[JWT Tokens]
        BCRYPT[Bcrypt Password Hashing]
        RBAC[Role-Based Access]
    end
    
    subgraph "API Security"
        CORS[CORS Policy]
        RATE[Rate Limiting]
        WEBHOOK[Webhook Auth]
    end
    
    subgraph "Infrastructure Security"
        DOCKER[Non-root Containers]
        ENV[Environment Secrets]
        TLS[TLS/HTTPS]
    end
    
    subgraph "Application Security"
        LOCK[Account Lockout]
        SANITIZE[Input Sanitization]
        VALIDATE[Schema Validation]
    end
```

## Deployment Architecture

### Development Environment

```mermaid
graph TB
    subgraph "Docker Compose Network"
        FE[Frontend<br/>:80]
        BE[Backend<br/>:8000]
        WB[WhatsApp Bridge<br/>:3000]
        DB[PostgreSQL<br/>:5432]
        RD[Redis<br/>:6379]
        PG[PgAdmin<br/>:5050]
    end
    
    DEV[Developer] --> FE
    DEV --> BE
    DEV --> PG
    
    FE --> BE
    BE --> WB
    BE --> DB
    BE --> RD
    WB --> EXT[External WhatsApp]
    
    style DEV fill:#f96,stroke:#333,stroke-width:2px
```

### Production Environment

```mermaid
graph TB
    subgraph "Load Balancer"
        LB[Nginx/Traefik]
    end
    
    subgraph "Application Tier"
        FE1[Frontend Pod 1]
        FE2[Frontend Pod 2]
        BE1[Backend Pod 1]
        BE2[Backend Pod 2]
        WB1[WhatsApp Bridge]
    end
    
    subgraph "Data Tier"
        DB[(PostgreSQL<br/>Managed)]
        RD[(Redis<br/>Managed)]
        VS[(Vector Store)]
    end
    
    subgraph "External"
        WA[WhatsApp]
        OAI[OpenAI]
    end
    
    USERS[Users] --> LB
    LB --> FE1
    LB --> FE2
    FE1 --> BE1
    FE2 --> BE2
    BE1 --> DB
    BE2 --> DB
    BE1 --> RD
    BE2 --> RD
    BE1 --> WB1
    BE2 --> WB1
    WB1 --> WA
    BE1 --> OAI
    BE2 --> OAI
    
    style USERS fill:#f96,stroke:#333,stroke-width:2px
    style LB fill:#9f9,stroke:#333,stroke-width:2px
```

## Key Design Decisions

### 1. Plumbing + Intelligence Separation
- **Surface Layer**: Handles HTTP, authentication, validation
- **Service Layer**: Contains all business logic and orchestration
- **Adapter Layer**: Isolates external dependencies

### 2. Asynchronous Architecture
- FastAPI with async/await for high concurrency
- Background tasks for heavy operations
- Webhook-based communication with WhatsApp Bridge

### 3. Modular AI Integration
- Configurable agents with different models and prompts
- Function calling for advanced commands
- Vector store for semantic search capabilities

### 4. Resilient Design
- Health checks for all services
- Automatic reconnection for WhatsApp sessions
- Session persistence across restarts
- Comprehensive error handling and logging

### 5. Test-Driven Development
- Unit tests for all components
- Integration tests for APIs
- Mock adapters for external services
- Minimum 80% code coverage requirement

## Scalability Considerations

1. **Horizontal Scaling**: Backend and frontend can scale independently
2. **Session Affinity**: WhatsApp sessions tied to specific bridge instances
3. **Database Pooling**: Connection pooling for PostgreSQL
4. **Caching Strategy**: Redis for frequently accessed data
5. **Queue Processing**: Background tasks via Redis/RabbitMQ

## Monitoring and Observability

- **Health Endpoints**: All services expose `/health`
- **Structured Logging**: JSON logs with correlation IDs
- **Metrics**: Response times, error rates, session counts
- **Alerts**: Failed health checks, high error rates
- **Audit Trail**: All admin actions and AI interactions logged