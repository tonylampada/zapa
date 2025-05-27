# Task 16: Integration Testing

## Overview
Create comprehensive integration tests that verify the complete system works end-to-end. Test real interactions between all components: WhatsApp Bridge, backend entrypoints, LLM providers, and frontends.

## Prerequisites
- All previous tasks (1-15) implemented
- Docker Compose setup for test environment
- Test phone numbers for WhatsApp

## Acceptance Criteria
1. E2E test suite covering all user flows
2. Integration tests for each service boundary
3. Load testing for concurrent users
4. Failure scenario testing
5. LLM provider switching tests
6. Performance benchmarks
7. Security penetration tests
8. CI/CD pipeline integration

## Test-Driven Development Steps

### Step 1: Create Test Environment Setup
```yaml
# docker-compose.test.yml
version: '3.8'

services:
  # Test Database
  test-db:
    image: postgres:15
    environment:
      POSTGRES_DB: zapa_test
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_pass
    ports:
      - "5433:5432"
    tmpfs:
      - /var/lib/postgresql/data

  # Test Redis
  test-redis:
    image: redis:7-alpine
    ports:
      - "6380:6379"
    command: redis-server --save ""

  # Mock WhatsApp Bridge
  mock-whatsapp:
    build:
      context: ./tests/mocks/whatsapp-bridge
    ports:
      - "3001:3000"
    environment:
      WEBHOOK_URL: http://backend-private:8001/api/v1/webhooks/whatsapp

  # Backend (Test Mode) - Private entrypoint
  backend-private:
    build:
      context: .
      dockerfile: Dockerfile
      target: test
    ports:
      - "8001:8001"
    environment:
      DATABASE_URL: postgresql://test_user:test_pass@test-db:5432/zapa_test
      REDIS_URL: redis://test-redis:6379
      WHATSAPP_API_URL: http://mock-whatsapp:3000
      TESTING: "true"
    command: python private_main.py
    depends_on:
      - test-db
      - test-redis
      - mock-whatsapp

  # Backend (Test Mode) - Public entrypoint
  backend-public:
    build:
      context: .
      dockerfile: Dockerfile
      target: test
    ports:
      - "8002:8002"
    environment:
      DATABASE_URL: postgresql://test_user:test_pass@test-db:5432/zapa_test
      REDIS_URL: redis://test-redis:6379
      PRIVATE_SERVICE_URL: http://backend-private:8001
      TESTING: "true"
    command: python public_main.py
    depends_on:
      - test-db
      - test-redis
      - backend-private

  # Test Runner
  test-runner:
    build:
      context: ./tests
    volumes:
      - ./tests:/tests
      - ./test-results:/results
    environment:
      ZAPA_PRIVATE_URL: http://backend-private:8001/api/v1
      ZAPA_PUBLIC_URL: http://backend-public:8002/api/v1
    depends_on:
      - backend-private
      - backend-public
```

### Step 2: Create Mock WhatsApp Bridge
```javascript
// tests/mocks/whatsapp-bridge/server.js
const express = require('express');
const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

const app = express();
app.use(express.json());

// In-memory storage
const sessions = new Map();
const messages = new Map();
const webhookUrl = process.env.WEBHOOK_URL;

// Mock endpoints
app.get('/sessions', (req, res) => {
  res.json(Array.from(sessions.values()));
});

app.post('/sessions', (req, res) => {
  const session = {
    id: uuidv4(),
    phone_number: req.body.phone_number,
    status: 'connected',
    created_at: new Date().toISOString()
  };
  sessions.set(session.id, session);
  res.json(session);
});

app.post('/messages/send', async (req, res) => {
  const { to, message, from } = req.body;
  
  const messageId = `mock_${uuidv4()}`;
  const messageData = {
    id: messageId,
    from: from || '+1234567890',
    to,
    message,
    status: 'sent',
    timestamp: new Date().toISOString()
  };
  
  messages.set(messageId, messageData);
  
  // Send webhook for sent confirmation
  if (webhookUrl) {
    setTimeout(async () => {
      await axios.post(webhookUrl, {
        event_type: 'message.sent',
        timestamp: new Date().toISOString(),
        data: {
          message_id: messageId,
          status: 'delivered'
        }
      });
    }, 1000);
  }
  
  res.json({ message_id: messageId, status: 'queued' });
});

// Simulate incoming messages
app.post('/simulate/message', async (req, res) => {
  const { from, to, message } = req.body;
  
  if (webhookUrl) {
    await axios.post(webhookUrl, {
      event_type: 'message.received',
      timestamp: new Date().toISOString(),
      data: {
        from_number: from,
        to_number: to || '+1234567890',
        message_id: `mock_${uuidv4()}`,
        text: message,
        timestamp: new Date().toISOString()
      }
    });
  }
  
  res.json({ status: 'simulated' });
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy', mock: true });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Mock WhatsApp Bridge running on port ${PORT}`);
});
```

### Step 3: Create E2E Test Suite
```python
# tests/e2e/test_full_flow.py
import pytest
import asyncio
import aiohttp
from datetime import datetime
import os

class TestE2EFlow:
    """End-to-end tests for complete user flows."""
    
    @pytest.fixture
    async def test_user(self, api_client):
        """Create a test user."""
        # Request auth code
        response = await api_client.post('/auth/request-code', json={
            'phone_number': '+15551234567'
        })
        assert response.status == 200
        
        # Mock verify code (in test mode)
        response = await api_client.post('/auth/verify', json={
            'phone_number': '+15551234567',
            'code': '123456'  # Test mode accepts any code
        })
        assert response.status == 200
        data = await response.json()
        
        return {
            'token': data['access_token'],
            'user_id': data['user_id'],
            'phone_number': '+15551234567'
        }
    
    @pytest.mark.asyncio
    async def test_complete_message_flow(self, api_client, test_user):
        """Test sending message through WhatsApp and receiving AI response."""
        # Configure LLM for user
        headers = {'Authorization': f'Bearer {test_user["token"]}'}
        
        response = await api_client.post(
            '/llm/configure',
            headers=headers,
            json={
                'provider': 'openai',
                'api_key': os.getenv('TEST_OPENAI_KEY', 'test-key'),
                'model_settings': {
                    'model': 'gpt-3.5-turbo',
                    'temperature': 0.7
                }
            }
        )
        assert response.status == 200
        
        # Simulate incoming WhatsApp message
        await api_client.post('/simulate/message', json={
            'from': test_user['phone_number'],
            'message': 'Hello, what is the weather like?'
        })
        
        # Wait for processing
        await asyncio.sleep(3)
        
        # Check message was stored and processed
        response = await api_client.get(
            '/messages',
            headers=headers
        )
        assert response.status == 200
        messages = await response.json()
        
        # Should have at least 2 messages (user + AI response)
        assert len(messages['items']) >= 2
        
        # Verify user message
        user_message = next(
            m for m in messages['items'] 
            if m['direction'] == 'inbound'
        )
        assert user_message['content'] == 'Hello, what is the weather like?'
        
        # Verify AI response exists
        ai_message = next(
            m for m in messages['items'] 
            if m['direction'] == 'outbound'
        )
        assert ai_message['content'] is not None
        assert len(ai_message['content']) > 0
    
    @pytest.mark.asyncio
    async def test_llm_provider_switching(self, api_client, test_user):
        """Test switching between different LLM providers."""
        headers = {'Authorization': f'Bearer {test_user["token"]}'}
        
        providers = [
            {
                'provider': 'openai',
                'api_key': os.getenv('TEST_OPENAI_KEY', 'test-key'),
                'model': 'gpt-3.5-turbo'
            },
            {
                'provider': 'anthropic',
                'api_key': os.getenv('TEST_ANTHROPIC_KEY', 'test-key'),
                'model': 'claude-3-haiku'
            }
        ]
        
        for provider_config in providers:
            # Configure provider
            response = await api_client.post(
                '/llm/configure',
                headers=headers,
                json={
                    'provider': provider_config['provider'],
                    'api_key': provider_config['api_key'],
                    'model_settings': {
                        'model': provider_config['model']
                    }
                }
            )
            assert response.status == 200
            
            # Send test message
            await api_client.post('/simulate/message', json={
                'from': test_user['phone_number'],
                'message': f'Test message for {provider_config["provider"]}'
            })
            
            await asyncio.sleep(3)
            
            # Verify response was generated
            response = await api_client.get(
                f'/messages?limit=1',
                headers=headers
            )
            messages = await response.json()
            assert len(messages['items']) > 0
    
    @pytest.mark.asyncio
    async def test_conversation_context(self, api_client, test_user):
        """Test that AI maintains conversation context."""
        headers = {'Authorization': f'Bearer {test_user["token"]}'}
        
        # Send series of related messages
        messages = [
            "My name is Alice",
            "What's my name?",
            "Tell me a joke about my name"
        ]
        
        for msg in messages:
            await api_client.post('/simulate/message', json={
                'from': test_user['phone_number'],
                'message': msg
            })
            await asyncio.sleep(3)
        
        # Get conversation
        response = await api_client.get(
            '/messages?limit=10',
            headers=headers
        )
        conversation = await response.json()
        
        # Find AI responses
        ai_responses = [
            m for m in conversation['items'] 
            if m['direction'] == 'outbound'
        ]
        
        # Second response should mention "Alice"
        assert 'Alice' in ai_responses[1]['content']
        
        # Third response should be a joke about Alice
        assert 'Alice' in ai_responses[2]['content']
```

### Step 4: Create Load Testing Suite
```python
# tests/load/test_concurrent_users.py
import asyncio
import aiohttp
import time
from locust import HttpUser, task, between
import random

class WhatsAppUser(HttpUser):
    """Simulates a WhatsApp user interacting with the system."""
    wait_time = between(5, 15)  # Wait 5-15 seconds between tasks
    
    def on_start(self):
        """Called when user starts - authenticate."""
        # Create unique phone number
        self.phone = f"+1555{random.randint(1000000, 9999999)}"
        
        # Request auth code
        response = self.client.post('/auth/request-code', json={
            'phone_number': self.phone
        })
        
        # Verify code (test mode)
        response = self.client.post('/auth/verify', json={
            'phone_number': self.phone,
            'code': '123456'
        })
        
        self.token = response.json()['access_token']
        self.headers = {'Authorization': f'Bearer {self.token}'}
        
        # Configure LLM
        self.client.post('/llm/configure', 
            headers=self.headers,
            json={
                'provider': 'openai',
                'api_key': 'test-key',
                'model_settings': {'model': 'gpt-3.5-turbo'}
            }
        )
    
    @task(3)
    def send_message(self):
        """Send a message through WhatsApp."""
        messages = [
            "What's the weather like?",
            "Tell me a joke",
            "What time is it?",
            "Help me with a recipe",
            "Explain quantum physics"
        ]
        
        self.client.post('/simulate/message', json={
            'from': self.phone,
            'message': random.choice(messages)
        })
    
    @task(2)
    def check_messages(self):
        """Check message history."""
        self.client.get('/messages', headers=self.headers)
    
    @task(1)
    def get_stats(self):
        """Get conversation statistics."""
        self.client.get('/stats', headers=self.headers)

# Async load test for sustained load
async def sustained_load_test(users=100, duration=300):
    """Test system under sustained load."""
    async with aiohttp.ClientSession() as session:
        start_time = time.time()
        tasks = []
        
        # Create users
        for i in range(users):
            task = asyncio.create_task(
                simulate_user(session, f"+1555{7000000+i}", duration)
            )
            tasks.append(task)
            await asyncio.sleep(0.1)  # Stagger user creation
        
        # Wait for all users to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        successful_users = sum(1 for r in results if not isinstance(r, Exception))
        failed_users = sum(1 for r in results if isinstance(r, Exception))
        
        print(f"Load test completed:")
        print(f"  Total users: {users}")
        print(f"  Successful: {successful_users}")
        print(f"  Failed: {failed_users}")
        print(f"  Duration: {time.time() - start_time:.2f}s")

async def simulate_user(session, phone_number, duration):
    """Simulate a single user for the specified duration."""
    end_time = time.time() + duration
    message_count = 0
    
    # Authenticate
    token = await authenticate_user(session, phone_number)
    headers = {'Authorization': f'Bearer {token}'}
    
    while time.time() < end_time:
        # Send message
        await session.post(
            'http://localhost:8001/simulate/message',
            json={
                'from': phone_number,
                'message': f'Test message {message_count}'
            }
        )
        message_count += 1
        
        # Random delay
        await asyncio.sleep(random.uniform(10, 30))
    
    return {'phone': phone_number, 'messages': message_count}
```

### Step 5: Create Integration Test Scenarios
```python
# tests/integration/test_failure_scenarios.py
import pytest
import asyncio
from unittest.mock import patch

class TestFailureScenarios:
    """Test system behavior under various failure conditions."""
    
    @pytest.mark.asyncio
    async def test_whatsapp_bridge_disconnect(self, system_fixture):
        """Test handling of WhatsApp Bridge disconnection."""
        # Send initial message
        await system_fixture.send_whatsapp_message(
            from_='+15551234567',
            message='Test message 1'
        )
        
        # Disconnect WhatsApp Bridge
        await system_fixture.stop_service('mock-whatsapp')
        
        # Try to send another message
        with pytest.raises(Exception) as exc_info:
            await system_fixture.send_whatsapp_message(
                from_='+15551234567',
                message='Test message 2'
            )
        
        # Verify message was queued
        queue_stats = await system_fixture.get_queue_stats()
        assert queue_stats['queued'] > 0
        
        # Reconnect WhatsApp Bridge
        await system_fixture.start_service('mock-whatsapp')
        
        # Wait for queue processing
        await asyncio.sleep(5)
        
        # Verify message was eventually sent
        queue_stats = await system_fixture.get_queue_stats()
        assert queue_stats['queued'] == 0
    
    @pytest.mark.asyncio
    async def test_llm_provider_failure(self, system_fixture):
        """Test fallback when LLM provider fails."""
        # Configure primary and fallback providers
        user = await system_fixture.create_test_user()
        
        # Mock OpenAI to fail
        with patch('openai.ChatCompletion.create') as mock_openai:
            mock_openai.side_effect = Exception("OpenAI API Error")
            
            # Send message
            await system_fixture.send_whatsapp_message(
                from_=user['phone_number'],
                message='Hello AI'
            )
            
            await asyncio.sleep(3)
            
            # Check that system handled the error gracefully
            messages = await system_fixture.get_user_messages(user['token'])
            
            # Should have error message or fallback response
            assert any(
                'temporarily unavailable' in m['content'].lower() 
                for m in messages 
                if m['direction'] == 'outbound'
            )
    
    @pytest.mark.asyncio
    async def test_database_connection_loss(self, system_fixture):
        """Test system behavior when database connection is lost."""
        # Send initial message
        await system_fixture.send_whatsapp_message(
            from_='+15551234567',
            message='Test before DB loss'
        )
        
        # Simulate database connection loss
        await system_fixture.stop_service('test-db')
        
        # Try to send another message
        response = await system_fixture.send_whatsapp_message(
            from_='+15551234567',
            message='Test during DB loss',
            expect_success=False
        )
        
        # Should get appropriate error response
        assert response['status'] == 'error'
        
        # Restart database
        await system_fixture.start_service('test-db')
        await asyncio.sleep(5)  # Wait for reconnection
        
        # Verify system recovers
        await system_fixture.send_whatsapp_message(
            from_='+15551234567',
            message='Test after DB recovery'
        )
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, system_fixture):
        """Test rate limiting protection."""
        phone = '+15551234567'
        
        # Send many auth requests rapidly
        results = []
        for i in range(10):
            response = await system_fixture.request_auth_code(phone)
            results.append(response['success'])
        
        # First 3 should succeed, rest should fail
        assert sum(results[:3]) == 3
        assert sum(results[3:]) == 0
        
        # Wait for rate limit to reset
        await asyncio.sleep(3600)  # Or use Redis to clear
        
        # Should work again
        response = await system_fixture.request_auth_code(phone)
        assert response['success'] is True
```

### Step 6: Create Security Testing Suite
```python
# tests/security/test_security.py
import pytest
import jwt
import asyncio
from datetime import datetime, timedelta

class TestSecurity:
    """Security and penetration tests."""
    
    @pytest.mark.asyncio
    async def test_jwt_token_validation(self, api_client):
        """Test JWT token security."""
        # Test expired token
        expired_token = jwt.encode({
            'user_id': 1,
            'exp': datetime.utcnow() - timedelta(days=1)
        }, 'wrong-secret', algorithm='HS256')
        
        response = await api_client.get(
            '/messages',
            headers={'Authorization': f'Bearer {expired_token}'}
        )
        assert response.status == 401
        
        # Test invalid signature
        invalid_token = jwt.encode({
            'user_id': 1,
            'exp': datetime.utcnow() + timedelta(days=1)
        }, 'wrong-secret', algorithm='HS256')
        
        response = await api_client.get(
            '/messages',
            headers={'Authorization': f'Bearer {invalid_token}'}
        )
        assert response.status == 401
    
    @pytest.mark.asyncio
    async def test_sql_injection(self, api_client, test_user):
        """Test SQL injection protection."""
        headers = {'Authorization': f'Bearer {test_user["token"]}'}
        
        # Try SQL injection in search
        malicious_queries = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "'; INSERT INTO admins VALUES ('hacker', 'password'); --"
        ]
        
        for query in malicious_queries:
            response = await api_client.get(
                f'/messages/search?q={query}',
                headers=headers
            )
            # Should handle safely
            assert response.status in [200, 400]
            
            # Verify tables still exist
            response = await api_client.get('/health')
            assert response.status == 200
    
    @pytest.mark.asyncio
    async def test_api_key_encryption(self, db_connection, test_user):
        """Test that API keys are properly encrypted in database."""
        # Configure LLM with API key
        api_key = 'sk-test-1234567890'
        
        response = await api_client.post(
            '/llm/configure',
            headers={'Authorization': f'Bearer {test_user["token"]}'},
            json={
                'provider': 'openai',
                'api_key': api_key,
                'model_settings': {'model': 'gpt-3.5-turbo'}
            }
        )
        assert response.status == 200
        
        # Check database directly
        result = await db_connection.execute(
            "SELECT api_key_encrypted FROM llm_configs WHERE user_id = %s",
            test_user['user_id']
        )
        row = await result.fetchone()
        
        # Should not find plain text API key
        assert api_key not in row['api_key_encrypted']
        assert row['api_key_encrypted'].startswith('enc:')  # Encrypted prefix
    
    @pytest.mark.asyncio
    async def test_xss_protection(self, api_client, test_user):
        """Test XSS protection in messages."""
        headers = {'Authorization': f'Bearer {test_user["token"]}'}
        
        # Send message with XSS attempt
        xss_payloads = [
            '<script>alert("XSS")</script>',
            '<img src=x onerror=alert("XSS")>',
            'javascript:alert("XSS")'
        ]
        
        for payload in xss_payloads:
            await api_client.post('/simulate/message', json={
                'from': test_user['phone_number'],
                'message': payload
            })
        
        # Retrieve messages
        response = await api_client.get('/messages', headers=headers)
        messages = await response.json()
        
        # Verify scripts are escaped/sanitized
        for message in messages['items']:
            assert '<script>' not in message['content']
            assert 'javascript:' not in message['content']
```

### Step 7: Create Performance Benchmarks
```python
# tests/performance/test_benchmarks.py
import pytest
import asyncio
import time
import statistics

class TestPerformanceBenchmarks:
    """Performance benchmarking tests."""
    
    @pytest.mark.asyncio
    async def test_message_processing_speed(self, system_fixture):
        """Benchmark message processing speed."""
        user = await system_fixture.create_test_user()
        
        # Measure time for message round-trip
        times = []
        
        for i in range(10):
            start = time.time()
            
            # Send message
            await system_fixture.send_whatsapp_message(
                from_=user['phone_number'],
                message=f'Performance test {i}'
            )
            
            # Wait for AI response
            response_received = False
            for _ in range(30):  # Max 30 seconds
                messages = await system_fixture.get_user_messages(
                    user['token']
                )
                if len(messages) >= (i + 1) * 2:  # User + AI messages
                    response_received = True
                    break
                await asyncio.sleep(0.5)
            
            if response_received:
                elapsed = time.time() - start
                times.append(elapsed)
        
        # Calculate statistics
        avg_time = statistics.mean(times)
        p95_time = statistics.quantiles(times, n=20)[18]  # 95th percentile
        
        print(f"Message processing benchmarks:")
        print(f"  Average: {avg_time:.2f}s")
        print(f"  95th percentile: {p95_time:.2f}s")
        
        # Assert performance requirements
        assert avg_time < 5.0  # Average under 5 seconds
        assert p95_time < 10.0  # 95% under 10 seconds
    
    @pytest.mark.asyncio
    async def test_concurrent_message_handling(self, system_fixture):
        """Test handling multiple concurrent messages."""
        users = []
        for i in range(10):
            user = await system_fixture.create_test_user(
                phone=f'+1555800{i:04d}'
            )
            users.append(user)
        
        # Send messages concurrently
        start = time.time()
        tasks = []
        
        for user in users:
            task = system_fixture.send_whatsapp_message(
                from_=user['phone_number'],
                message='Concurrent test message'
            )
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        # Wait for all responses
        all_processed = False
        for _ in range(60):  # Max 60 seconds
            processed_count = 0
            
            for user in users:
                messages = await system_fixture.get_user_messages(
                    user['token']
                )
                if len(messages) >= 2:  # Has AI response
                    processed_count += 1
            
            if processed_count == len(users):
                all_processed = True
                break
                
            await asyncio.sleep(1)
        
        elapsed = time.time() - start
        
        assert all_processed
        print(f"Processed {len(users)} concurrent messages in {elapsed:.2f}s")
        assert elapsed < 30  # Should handle 10 users in under 30 seconds
    
    @pytest.mark.asyncio
    async def test_database_query_performance(self, db_connection):
        """Benchmark critical database queries."""
        # Create test data
        user_id = 1
        for i in range(10000):
            await db_connection.execute("""
                INSERT INTO messages (user_id, content, direction, created_at)
                VALUES (%s, %s, %s, NOW() - INTERVAL '%s days')
            """, user_id, f'Test message {i}', 'inbound', i % 365)
        
        # Benchmark queries
        queries = [
            ("Recent messages", """
                SELECT * FROM messages 
                WHERE user_id = %s 
                ORDER BY created_at DESC 
                LIMIT 50
            """),
            ("Message search", """
                SELECT * FROM messages 
                WHERE user_id = %s 
                AND content ILIKE %s
                ORDER BY created_at DESC
                LIMIT 20
            """),
            ("Daily stats", """
                SELECT DATE(created_at) as day, COUNT(*) as count
                FROM messages
                WHERE user_id = %s
                AND created_at > NOW() - INTERVAL '30 days'
                GROUP BY DATE(created_at)
            """)
        ]
        
        for name, query in queries:
            start = time.time()
            
            if 'ILIKE' in query:
                await db_connection.execute(query, user_id, '%test%')
            else:
                await db_connection.execute(query, user_id)
            
            elapsed = time.time() - start
            print(f"{name}: {elapsed*1000:.2f}ms")
            
            # All queries should be fast
            assert elapsed < 0.1  # Under 100ms
```

## CI/CD Integration

```yaml
# .github/workflows/integration-tests.yml
name: Integration Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  integration-tests:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v2
    
    - name: Start test environment
      run: |
        docker-compose -f docker-compose.test.yml up -d
        ./scripts/wait-for-services.sh
    
    - name: Run integration tests
      run: |
        docker-compose -f docker-compose.test.yml run test-runner \
          pytest tests/integration -v --junitxml=results/integration.xml
    
    - name: Run E2E tests
      run: |
        docker-compose -f docker-compose.test.yml run test-runner \
          pytest tests/e2e -v --junitxml=results/e2e.xml
    
    - name: Run load tests
      run: |
        docker-compose -f docker-compose.test.yml run test-runner \
          locust -f tests/load/test_concurrent_users.py \
          --headless -u 50 -r 5 -t 5m \
          --html results/load-test.html
    
    - name: Upload test results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: test-results
        path: results/
    
    - name: Publish test results
      uses: EnricoMi/publish-unit-test-result-action@v2
      if: always()
      with:
        files: |
          results/**/*.xml
```

## Implementation Notes

1. **Test Isolation**: Each test runs in isolated environment
2. **Mock Services**: Mock WhatsApp Bridge for predictable testing
3. **Real LLM Testing**: Optional real LLM tests with API keys
4. **Performance Metrics**: Track and assert on performance
5. **Security Testing**: Comprehensive security test suite
6. **Load Testing**: Realistic user simulation
7. **CI/CD Ready**: Automated test execution

## Testing Strategy Summary

- **Unit Tests**: Already covered in individual tasks
- **Integration Tests**: Service boundaries and interactions
- **E2E Tests**: Complete user journeys
- **Load Tests**: Concurrent user handling
- **Security Tests**: Penetration and vulnerability testing
- **Performance Tests**: Benchmarks and requirements validation

## Dependencies
- pytest for Python testing
- Playwright/Cypress for browser testing
- Locust for load testing
- Docker Compose for test environment
- GitHub Actions for CI/CD

## Next Steps
- Task 17: Performance Optimization
- Task 18: Deployment Configuration