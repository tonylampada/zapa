# Task 01: Project Setup & Scaffolding

## Objective
Initialize the project structure and create the basic directory layout for all components.

## Requirements
- Create directory structure for backend, frontend, and infrastructure
- Initialize git repository (already done)
- Create placeholder files for key components
- Set up .gitignore files

## Directory Structure to Create

```
zapa/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/
│   │   │   └── __init__.py
│   │   ├── services/
│   │   │   └── __init__.py
│   │   ├── adapters/
│   │   │   └── __init__.py
│   │   ├── models/
│   │   │   └── __init__.py
│   │   └── core/
│   │       └── __init__.py
│   ├── tests/
│   │   └── __init__.py
│   ├── alembic/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── Dockerfile
│   └── .gitignore
├── frontend/
│   ├── src/
│   ├── public/
│   ├── tests/
│   ├── package.json
│   ├── Dockerfile
│   └── .gitignore
├── whatsapp-bridge/
│   └── README.md (reference to zapw)
├── docker/
│   └── docker-compose.yml
├── .github/
│   └── workflows/
├── docs/
├── scripts/
├── .env.example
└── .gitignore (root)
```

## Files to Create

### Root .gitignore
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.env
*.egg-info/

# Node
node_modules/
dist/
.DS_Store
npm-debug.log*
yarn-debug.log*

# IDE
.vscode/
.idea/
*.swp
*.swo

# Docker
.docker/

# Logs
*.log

# Database
*.db
*.sqlite3

# OS
.DS_Store
Thumbs.db
```

### Backend requirements.txt (initial)
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
alembic==1.12.1
psycopg2-binary==2.9.9
pydantic==2.5.2
pydantic-settings==2.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
httpx==0.25.2
openai==1.6.1
redis==5.0.1
```

### Frontend package.json (initial)
```json
{
  "name": "whatsapp-agent-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "serve": "vue-cli-service serve",
    "build": "vue-cli-service build",
    "test:unit": "vue-cli-service test:unit",
    "test:e2e": "vue-cli-service test:e2e",
    "lint": "vue-cli-service lint"
  }
}
```

## Success Criteria
- [ ] All directories created
- [ ] All __init__.py files created
- [ ] .gitignore files in place
- [ ] Initial requirements.txt and package.json created
- [ ] Directory structure matches architecture pattern