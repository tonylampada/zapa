# WhatsApp Agent System Architecture

## Overview

The WhatsApp Agent System consists of two separate FastAPI applications:
1. **Zapa Private** - Internal service handling WhatsApp webhooks and admin functions
2. **Zapa Public** - Internet-facing service for end users to manage their WhatsApp connections

Both applications share a Vue.js + Tailwind CSS frontend and follow the **"Plumbing + Intelligence"** architecture pattern.

## System Architecture

```mermaid
graph TB
    subgraph "External Services"
        WA[WhatsApp Network]
        USERS[End Users]
    end
    
    subgraph "Public Zone"
        PUB_UI[Vue.js + Tailwind<br/>Public Frontend]
        PUB_API[Zapa Public<br/>FastAPI]
    end
    
    subgraph "Private Zone"
        PRIV_UI[Vue.js + Tailwind<br/>Admin Frontend]
        PRIV_API[Zapa Private<br/>FastAPI]
        WB[WhatsApp Bridge<br/>zapw/Baileys]
    end
    
    subgraph "Shared Infrastructure"
        DB[(PostgreSQL)]
        REDIS[(Redis)]
    end
    
    USERS --> PUB_UI
    PUB_UI --> PUB_API
    
    ADMIN[Admin] --> PRIV_UI
    PRIV_UI --> PRIV_API
    
    WB --> PRIV_API
    WB <--> WA
    PRIV_API --> WB
    
    PUB_API --> DB
    PRIV_API --> DB
    PUB_API --> REDIS
    PRIV_API --> REDIS
    
    PRIV_API -.->|Send Auth Codes| WA
    
    style PRIV_API fill:#f9f,stroke:#333,stroke-width:4px
    style PUB_API fill:#9ff,stroke:#333,stroke-width:4px
    style WB fill:#ff9,stroke:#333,stroke-width:2px
```

## Component Architecture

### Zapa Private (Internal Service)

```mermaid
graph LR
    subgraph "API Layer"
        WH[Webhook Handler]
        ADM[Admin UI Routes]
        QR[QR Code Manager]
    end
    
    subgraph "Service Layer"
        MS[Message Service]
        SS[Session Service]
        NS[Notification Service]
    end
    
    subgraph "Adapter Layer"
        WC[WhatsApp Client]
        DR[DB Repository]
        MQ[Message Queue]
    end
    
    WH --> MS
    ADM --> SS
    ADM --> QR
    QR --> WC
    
    MS --> DR
    SS --> WC
    SS --> DR
    NS --> WC
    
    style WH fill:#faa,stroke:#333,stroke-width:2px
    style MS fill:#afa,stroke:#333,stroke-width:2px
    style WC fill:#aaf,stroke:#333,stroke-width:2px
```

### Zapa Public (Internet-Facing Service)

```mermaid
graph LR
    subgraph "API Layer"
        AUTH[Auth Endpoints]
        USER[User Dashboard API]
        STATS[Statistics API]
    end
    
    subgraph "Service Layer"
        AS[Auth Service]
        US[User Service]
        DS[Data Service]
    end
    
    subgraph "Adapter Layer"
        DR[DB Repository]
        CACHE[Redis Cache]
        SMS[SMS Gateway]
    end
    
    AUTH --> AS
    USER --> US
    STATS --> DS
    
    AS --> SMS
    AS --> DR
    US --> DR
    DS --> DR
    DS --> CACHE
    
    style AUTH fill:#faa,stroke:#333,stroke-width:2px
    style AS fill:#afa,stroke:#333,stroke-width:2px
    style DR fill:#aaf,stroke:#333,stroke-width:2px
```

## Data Flow Diagrams

### Main Service Connection Flow (Admin)

```mermaid
sequenceDiagram
    participant Admin
    participant PrivateUI
    participant PrivateAPI
    participant Bridge
    participant WhatsApp
    
    Admin->>PrivateUI: Access admin panel
    Admin->>PrivateUI: Click "Connect Main Number"
    PrivateUI->>PrivateAPI: GET /admin/qr-code
    PrivateAPI->>Bridge: Request QR for main service
    Bridge->>Bridge: Generate QR code
    Bridge-->>PrivateAPI: Return QR data
    PrivateAPI-->>PrivateUI: Display QR
    Admin->>WhatsApp: Scan QR with main number
    WhatsApp->>Bridge: Authenticate
    Bridge->>PrivateAPI: Webhook: session.connected
    PrivateAPI->>PrivateAPI: Mark main service active
```

### User Authentication Flow

```mermaid
sequenceDiagram
    participant User
    participant PublicUI
    participant PublicAPI
    participant PrivateAPI
    participant WhatsApp
    
    User->>PublicUI: Enter phone number
    PublicUI->>PublicAPI: POST /auth/request-code
    PublicAPI->>PublicAPI: Generate auth code
    PublicAPI->>PrivateAPI: Send code via internal API
    PrivateAPI->>WhatsApp: Send code to user
    WhatsApp->>User: Receive code
    User->>PublicUI: Enter code
    PublicUI->>PublicAPI: POST /auth/verify
    PublicAPI->>PublicAPI: Verify code
    PublicAPI-->>PublicUI: Return JWT token
    PublicUI->>User: Show dashboard
```

### Message Processing Flow

```mermaid
sequenceDiagram
    participant WhatsApp
    participant Bridge
    participant PrivateAPI
    participant Database
    
    WhatsApp->>Bridge: Message received
    Bridge->>PrivateAPI: Webhook: message.received
    PrivateAPI->>PrivateAPI: Parse message
    
    alt Text Message
        PrivateAPI->>Database: Store text content
    else Media Message
        PrivateAPI->>PrivateAPI: Extract metadata
        Note right of PrivateAPI: Duration (audio)<br/>Dimensions (image)<br/>File size, etc.
        PrivateAPI->>Database: Store metadata only
    end
    
    alt Has Caption
        PrivateAPI->>Database: Store caption
    end
    
    alt Is Reply
        PrivateAPI->>Database: Store reply reference
    end
    
    PrivateAPI-->>Bridge: Acknowledge
```

## Database Schema

```mermaid
erDiagram
    USER ||--o{ SESSION : has
    SESSION ||--o{ MESSAGE : contains
    USER ||--o{ AUTH_CODE : receives
    USER ||--o{ MESSAGE : owns
    USER ||--o{ LLM_CONFIG : configures
    
    USER {
        int id PK
        string phone_number UK
        string display_name
        datetime first_seen
        datetime last_active
        json preferences
        datetime created_at
        datetime updated_at
    }
    
    SESSION {
        int id PK
        int user_id FK
        string session_type "main|user"
        enum status
        datetime connected_at
        datetime disconnected_at
        json metadata
        datetime created_at
    }
    
    MESSAGE {
        bigint id PK
        int session_id FK
        int user_id FK "redundant for query performance"
        string sender_jid
        string recipient_jid
        datetime timestamp
        string message_type "text|image|audio|video|document"
        text content "nullable for media"
        text caption "nullable"
        bigint reply_to_id FK "nullable"
        json media_metadata "duration, dimensions, size, etc"
        datetime created_at
    }
    
    AUTH_CODE {
        int id PK
        int user_id FK
        string code
        boolean used
        datetime expires_at
        datetime created_at
    }
    
    LLM_CONFIG {
        int id PK
        int user_id FK
        string provider "openai|anthropic|google"
        string api_key_encrypted
        json model_settings "model, temperature, max_tokens, etc"
        boolean is_active
        datetime created_at
        datetime updated_at
    }
```

## Technology Stack

### Backend Stack (Both Services)
- **Framework**: FastAPI (Python 3.10+)
- **ORM**: SQLAlchemy 2.0
- **Database**: PostgreSQL 15
- **Cache**: Redis 7
- **Package Manager**: UV
- **Testing**: Pytest + pytest-asyncio
- **Migration**: Alembic
- **LLM Providers**: OpenAI, Anthropic, Google (Gemini)

### Frontend Stack
- **Framework**: Vue 3 (Composition API)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Build Tool**: Vite
- **State Management**: Pinia
- **Router**: Vue Router 4
- **HTTP Client**: Axios
- **Testing**: Vitest + Vue Test Utils

### Infrastructure
- **Containerization**: Docker + Docker Compose
- **Web Server**: Nginx (frontend serving)
- **Process Manager**: Uvicorn (backend)
- **CI/CD**: GitHub Actions
- **WhatsApp Bridge**: zapw (Baileys-based)

## Security Architecture

```mermaid
graph TB
    subgraph "Public Security"
        WA_AUTH[WhatsApp Code Auth]
        JWT[JWT Tokens]
        RATE_PUB[Rate Limiting]
    end
    
    subgraph "Private Security"
        ADMIN_AUTH[Admin Authentication]
        WEBHOOK_AUTH[Webhook Verification]
        INTERNAL[Internal Network Only]
    end
    
    subgraph "Shared Security"
        CORS[CORS Policy]
        SANITIZE[Input Sanitization]
        VALIDATE[Schema Validation]
        ENV[Environment Secrets]
    end
```

## Deployment Architecture

### Development Environment

```mermaid
graph TB
    subgraph "Docker Compose Network"
        subgraph "Private Services"
            PRIV_FE[Private Frontend<br/>:3000]
            PRIV_BE[Private Backend<br/>:8001]
            WB[WhatsApp Bridge<br/>:3001]
        end
        
        subgraph "Public Services"
            PUB_FE[Public Frontend<br/>:3002]
            PUB_BE[Public Backend<br/>:8002]
        end
        
        subgraph "Shared Services"
            DB[PostgreSQL<br/>:5432]
            RD[Redis<br/>:6379]
        end
    end
    
    DEV[Developer] --> PRIV_FE
    DEV --> PUB_FE
    
    PRIV_FE --> PRIV_BE
    PUB_FE --> PUB_BE
    
    PRIV_BE --> WB
    WB --> EXT[WhatsApp]
    
    PRIV_BE --> DB
    PUB_BE --> DB
    PRIV_BE --> RD
    PUB_BE --> RD
    
    style DEV fill:#f96,stroke:#333,stroke-width:2px
```

### Production Environment

```mermaid
graph TB
    subgraph "Internet"
        USERS[Public Users]
        CF[Cloudflare/CDN]
    end
    
    subgraph "DMZ"
        LB[Load Balancer]
        PUB_FE[Public Frontend]
        PUB_API[Public API Cluster]
    end
    
    subgraph "Private Network"
        PRIV_FE[Admin Frontend]
        PRIV_API[Private API]
        WB[WhatsApp Bridge]
        VPN[VPN Gateway]
    end
    
    subgraph "Data Tier"
        DB[(PostgreSQL)]
        RD[(Redis)]
    end
    
    USERS --> CF
    CF --> LB
    LB --> PUB_FE
    PUB_FE --> PUB_API
    
    ADMIN[Admins] --> VPN
    VPN --> PRIV_FE
    PRIV_FE --> PRIV_API
    
    PRIV_API --> WB
    WB --> WA[WhatsApp]
    
    PUB_API --> DB
    PRIV_API --> DB
    PUB_API --> RD
    PRIV_API --> RD
    
    style USERS fill:#f96,stroke:#333,stroke-width:2px
    style ADMIN fill:#6f9,stroke:#333,stroke-width:2px
```

## LLM Provider Architecture

```mermaid
graph TB
    subgraph "Service Layer"
        AS[Agent Service]
    end
    
    subgraph "LLM Adapter Layer"
        LA[LLM Adapter Interface]
        OA[OpenAI Adapter]
        AA[Anthropic Adapter]
        GA[Google Adapter]
    end
    
    subgraph "Provider APIs"
        OPENAI[OpenAI API]
        ANTHROPIC[Anthropic API]
        GOOGLE[Google AI API]
    end
    
    AS --> LA
    LA --> OA
    LA --> AA
    LA --> GA
    
    OA --> OPENAI
    AA --> ANTHROPIC
    GA --> GOOGLE
    
    style LA fill:#ff9,stroke:#333,stroke-width:4px
    style AS fill:#9f9,stroke:#333,stroke-width:2px
```

### LLM Adapter Interface
```python
class LLMAdapter(ABC):
    @abstractmethod
    async def complete(self, messages: List[Message], **kwargs) -> str:
        """Generate completion from messages"""
        pass
    
    @abstractmethod
    async def complete_with_functions(
        self, 
        messages: List[Message], 
        functions: List[FunctionDef],
        **kwargs
    ) -> Union[str, FunctionCall]:
        """Generate completion with function calling support"""
        pass
```

## Key Design Decisions

### 1. Separated Public/Private Services
- **Private Service**: Handles webhooks, admin functions, WhatsApp bridge
- **Public Service**: User-facing, authentication, data viewing
- **Security**: Private service never exposed to internet

### 2. WhatsApp-Based Authentication
- Users authenticate via WhatsApp code sent from main number
- No passwords needed - WhatsApp number is the identity
- Codes expire after short time for security

### 3. Efficient Message Storage
- Text messages stored directly in database
- Media messages store only metadata (no large objects)
- Metadata in JSON column for flexibility
- Separate columns for universal fields (timestamp, sender, caption, reply reference)

### 4. Vue.js + Tailwind Frontend
- Shared component library between public and private frontends
- Tailwind for consistent, utility-first styling
- TypeScript for type safety

### 5. Main Service Pattern
- Single main WhatsApp number acts as the service
- Admin connects this number via QR code in private interface
- All user authentication codes sent from this number

### 6. Multi-Provider LLM Support
- Users can choose between OpenAI, Anthropic, or Google as their LLM provider
- API keys stored encrypted in database per user
- Unified adapter interface allows seamless provider switching
- Each provider's specific features (function calling, tokens, models) normalized through adapters

## Message Storage Strategy

```mermaid
graph LR
    subgraph "Message Types"
        TEXT[Text Message]
        IMG[Image Message]
        AUD[Audio Message]
        VID[Video Message]
        DOC[Document]
    end
    
    subgraph "Storage Fields"
        COMMON[Common Fields<br/>- timestamp<br/>- sender_jid<br/>- recipient_jid<br/>- message_type]
        CONTENT[content<br/>Text only]
        CAPTION[caption<br/>Media caption]
        REPLY[reply_to_id<br/>Reply reference]
        META[media_metadata<br/>JSON column]
    end
    
    TEXT --> COMMON
    TEXT --> CONTENT
    TEXT --> REPLY
    
    IMG --> COMMON
    IMG --> CAPTION
    IMG --> REPLY
    IMG --> META
    
    AUD --> COMMON
    AUD --> META
    AUD --> REPLY
```

### Media Metadata Example
```json
{
  "duration": 120,
  "size": 1048576,
  "dimensions": {
    "width": 1920,
    "height": 1080
  },
  "mime_type": "image/jpeg"
}
```

## Scalability Considerations

1. **Service Separation**: Public and private services scale independently
2. **Stateless Design**: Both FastAPI services are stateless
3. **Database Optimization**: Indexes on phone_number, timestamp, sender_jid
4. **Caching Strategy**: Redis for auth codes and user session data
5. **Message Partitioning**: Can partition messages table by date if needed

## Monitoring and Observability

- **Health Endpoints**: Both services expose `/health`
- **Webhook Monitoring**: Track webhook delivery success
- **Auth Monitoring**: Track authentication attempts and failures
- **Message Stats**: Count messages per user, types, etc.
- **Connection Monitoring**: Track WhatsApp connection status