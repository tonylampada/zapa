# Zapa Task Overview - Test-Driven Development Plan

This document provides a comprehensive overview of all tasks needed to implement the Zapa WhatsApp Agent System following strict TDD principles.

## Core Principles

1. **Test-Driven Development (TDD)**: Write tests first, then implementation
2. **Baby Steps**: Small, incremental changes with tests at every step
3. **CI/CD First**: Every commit must pass GitHub Actions
4. **Integration Tests**: External services have both mocked tests (for CI) and real integration tests (skippable)
5. **UV for Python**: All Python dependencies managed with UV package manager
6. **Single Backend Architecture**: One backend with Private and Public FastAPI entrypoints

## Task Structure

Each task follows this pattern:
- Clear objective and success criteria
- Test files to create FIRST
- Implementation files to satisfy tests
- Commands to verify locally
- CI/CD must pass before moving to next task

## Integration Test Strategy

For external services (WhatsApp Bridge, LLM providers):
- **Unit tests**: Always run, use mocks
- **Integration tests**: Skip by default, enable with env vars
  - `INTEGRATION_TEST_WHATSAPP=true` - Test real WhatsApp Bridge
  - `INTEGRATION_TEST_OPENAI=true` - Test real OpenAI API
  - `INTEGRATION_TEST_ANTHROPIC=true` - Test real Anthropic API
  - `INTEGRATION_TEST_GOOGLE=true` - Test real Google AI API

## Task Categories

### Phase 1: Foundation (Tasks 01-04)
- 01: Project setup with UV, basic CI/CD
- 02: Database models and schemas
- 03: Core configuration and settings
- 04: Database migrations and fixtures

### Phase 2: Backend Core Services (Tasks 05-09)
- 05: Private entrypoint structure and health checks
- 06: WhatsApp Bridge adapter (with integration tests)
- 07: LLM adapter interface and implementations
- 08: Message service and storage
- 09: Agent service with LLM tools

### Phase 3: API Endpoints (Tasks 10-13)
- 10: Admin API endpoints (private entrypoint)
- 11: Webhook handlers for WhatsApp events
- 12: Public authentication flow
- 13: WhatsApp integration and message flow

### Phase 4: Frontend & User Features (Tasks 14-16)
- 14: Frontend user dashboard (Vue.js + Tailwind)
- 15: Admin frontend setup
- 16: Integration testing

### Phase 5: Infrastructure & Deployment
- Docker setup for backend and frontends
- Docker Compose orchestration
- Redis setup for caching/sessions
- Production configuration
- Performance and load testing
- Documentation and deployment guide

## Success Metrics

Each task must achieve:
- ✅ All tests passing locally
- ✅ All tests passing in GitHub Actions
- ✅ Code coverage ≥ 80% for the module
- ✅ No linting errors (ruff, black, ESLint)
- ✅ Integration tests documented and skippable

## Development Flow

1. Read task specification
2. Write test files first
3. Run tests (they should fail)
4. Implement minimal code to pass tests
5. Refactor if needed
6. Ensure CI/CD passes
7. Commit and proceed to next task

## Key Architectural Decisions

1. **Two FastAPI Entrypoints**: Private (internal) and Public (internet-facing) in single backend
2. **WhatsApp Bridge**: No authentication, secured by network isolation
3. **Multi-LLM Support**: Adapter pattern for OpenAI, Anthropic, Google
4. **WhatsApp Auth**: Users authenticate via codes sent from main number
5. **Message Storage**: Metadata only for media, full text for text messages
6. **Frontend**: Vue 3 + TypeScript + Tailwind CSS, shared between services

## Testing Philosophy

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test real external services (skippable)
- **E2E Tests**: Test complete user flows
- **Performance Tests**: Ensure system handles load

Every feature must have tests at appropriate levels.