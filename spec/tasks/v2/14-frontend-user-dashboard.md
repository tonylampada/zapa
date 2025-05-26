# Task 14: Frontend User Dashboard

## Overview
Create the user dashboard in Vue.js for Zapa Public. This allows authenticated users to view their conversation history, manage LLM settings, and interact with their WhatsApp agent.

## Prerequisites
- Task 12: Public Service Authentication (for JWT auth)
- Backend APIs from Tasks 10 (adapted for public users)

## Acceptance Criteria
1. Vue.js SPA with modern UI (Tailwind CSS)
2. JWT authentication with token refresh
3. Display conversation history with search
4. Configure LLM provider and settings
5. View conversation statistics
6. Export conversation data
7. Responsive design for mobile
8. Real-time updates via polling/websocket

## Test-Driven Development Steps

### Step 1: Project Setup with Vite
```bash
# Create Vue project
cd frontend
npm create vite@latest zapa-public -- --template vue
cd zapa-public

# Install dependencies
npm install vue-router@4 pinia axios @vueuse/core
npm install -D @vitejs/plugin-vue tailwindcss postcss autoprefixer
npm install -D @vue/test-utils vitest @vitest/ui happy-dom
npm install -D @testing-library/vue @testing-library/user-event

# Initialize Tailwind
npx tailwindcss init -p
```

**Project Structure:**
```
frontend/zapa-public/
├── src/
│   ├── api/           # API client modules
│   ├── components/    # Reusable components
│   ├── composables/   # Vue composables
│   ├── layouts/       # Layout components
│   ├── pages/         # Page components
│   ├── router/        # Vue Router config
│   ├── stores/        # Pinia stores
│   ├── utils/         # Utilities
│   └── App.vue
├── tests/
│   ├── unit/         # Unit tests
│   └── e2e/          # E2E tests
└── vite.config.js
```

### Step 2: Create Auth Store with Pinia
```javascript
// src/stores/auth.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import authApi from '@/api/auth'
import { useRouter } from 'vue-router'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('auth_token'))
  const user = ref(null)
  const router = useRouter()
  
  const isAuthenticated = computed(() => !!token.value)
  
  async function requestCode(phoneNumber) {
    try {
      const response = await authApi.requestCode(phoneNumber)
      return { success: true, message: response.message }
    } catch (error) {
      return { 
        success: false, 
        message: error.response?.data?.detail || 'Failed to send code' 
      }
    }
  }
  
  async function verifyCode(phoneNumber, code) {
    try {
      const response = await authApi.verifyCode(phoneNumber, code)
      
      // Store token
      token.value = response.access_token
      localStorage.setItem('auth_token', response.access_token)
      
      // Store user info
      user.value = {
        id: response.user_id,
        phoneNumber: response.phone_number
      }
      
      // Configure axios defaults
      authApi.setAuthToken(response.access_token)
      
      return { success: true }
    } catch (error) {
      return { 
        success: false, 
        message: error.response?.data?.detail || 'Invalid code' 
      }
    }
  }
  
  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('auth_token')
    authApi.clearAuthToken()
    router.push('/login')
  }
  
  // Initialize auth if token exists
  if (token.value) {
    authApi.setAuthToken(token.value)
    // Could verify token validity here
  }
  
  return {
    token,
    user,
    isAuthenticated,
    requestCode,
    verifyCode,
    logout
  }
})
```

**Tests:**
```javascript
// tests/unit/stores/auth.test.js
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { vi, describe, it, expect, beforeEach } from 'vitest'

vi.mock('@/api/auth', () => ({
  default: {
    requestCode: vi.fn(),
    verifyCode: vi.fn(),
    setAuthToken: vi.fn(),
    clearAuthToken: vi.fn()
  }
}))

describe('Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })
  
  it('should request auth code', async () => {
    const store = useAuthStore()
    const authApi = await import('@/api/auth')
    
    authApi.default.requestCode.mockResolvedValue({ 
      success: true, 
      message: 'Code sent' 
    })
    
    const result = await store.requestCode('+1234567890')
    
    expect(result.success).toBe(true)
    expect(authApi.default.requestCode).toHaveBeenCalledWith('+1234567890')
  })
  
  it('should verify code and store token', async () => {
    const store = useAuthStore()
    const authApi = await import('@/api/auth')
    
    authApi.default.verifyCode.mockResolvedValue({
      access_token: 'test_token',
      user_id: 1,
      phone_number: '+1234567890'
    })
    
    const result = await store.verifyCode('+1234567890', '123456')
    
    expect(result.success).toBe(true)
    expect(store.token).toBe('test_token')
    expect(store.user.phoneNumber).toBe('+1234567890')
    expect(localStorage.getItem('auth_token')).toBe('test_token')
  })
})
```

### Step 3: Create Login Page Component
```vue
<!-- src/pages/LoginPage.vue -->
<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50 px-4">
    <div class="max-w-md w-full space-y-8">
      <div class="text-center">
        <h2 class="text-3xl font-bold text-gray-900">
          Sign in to Zapa
        </h2>
        <p class="mt-2 text-gray-600">
          Enter your WhatsApp number to receive a verification code
        </p>
      </div>
      
      <form @submit.prevent="handleSubmit" class="mt-8 space-y-6">
        <!-- Phone Input Step -->
        <div v-if="!codeSent" class="space-y-4">
          <div>
            <label for="phone" class="block text-sm font-medium text-gray-700">
              WhatsApp Phone Number
            </label>
            <input
              id="phone"
              v-model="phoneNumber"
              type="tel"
              required
              placeholder="+1234567890"
              class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
              :disabled="loading"
            />
            <p v-if="phoneError" class="mt-1 text-sm text-red-600">
              {{ phoneError }}
            </p>
          </div>
          
          <button
            type="submit"
            :disabled="loading || !phoneNumber"
            class="w-full py-2 px-4 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
          >
            {{ loading ? 'Sending...' : 'Send Code' }}
          </button>
        </div>
        
        <!-- Code Input Step -->
        <div v-else class="space-y-4">
          <div>
            <label for="code" class="block text-sm font-medium text-gray-700">
              Verification Code
            </label>
            <input
              id="code"
              v-model="verificationCode"
              type="text"
              required
              placeholder="123456"
              maxlength="6"
              class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-center text-2xl"
              :disabled="loading"
              @input="handleCodeInput"
            />
            <p class="mt-1 text-sm text-gray-600">
              Code sent to {{ phoneNumber }}
            </p>
            <p v-if="codeError" class="mt-1 text-sm text-red-600">
              {{ codeError }}
            </p>
          </div>
          
          <button
            type="submit"
            :disabled="loading || verificationCode.length !== 6"
            class="w-full py-2 px-4 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
          >
            {{ loading ? 'Verifying...' : 'Verify' }}
          </button>
          
          <button
            type="button"
            @click="resetForm"
            class="w-full py-2 px-4 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
          >
            Change Number
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const phoneNumber = ref('')
const verificationCode = ref('')
const codeSent = ref(false)
const loading = ref(false)
const phoneError = ref('')
const codeError = ref('')

async function handleSubmit() {
  if (!codeSent.value) {
    await sendCode()
  } else {
    await verifyCode()
  }
}

async function sendCode() {
  loading.value = true
  phoneError.value = ''
  
  const result = await authStore.requestCode(phoneNumber.value)
  
  if (result.success) {
    codeSent.value = true
  } else {
    phoneError.value = result.message
  }
  
  loading.value = false
}

async function verifyCode() {
  loading.value = true
  codeError.value = ''
  
  const result = await authStore.verifyCode(
    phoneNumber.value,
    verificationCode.value
  )
  
  if (result.success) {
    router.push('/dashboard')
  } else {
    codeError.value = result.message
  }
  
  loading.value = false
}

function handleCodeInput(event) {
  // Only allow digits
  event.target.value = event.target.value.replace(/\D/g, '')
  verificationCode.value = event.target.value
}

function resetForm() {
  codeSent.value = false
  verificationCode.value = ''
  codeError.value = ''
}
</script>
```

### Step 4: Create Message History Component
```vue
<!-- src/components/MessageHistory.vue -->
<template>
  <div class="flex flex-col h-full">
    <!-- Search Bar -->
    <div class="p-4 border-b">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="Search messages..."
        class="w-full px-4 py-2 border rounded-lg"
        @input="debouncedSearch"
      />
    </div>
    
    <!-- Messages List -->
    <div 
      ref="messagesContainer"
      class="flex-1 overflow-y-auto p-4 space-y-4"
      @scroll="handleScroll"
    >
      <div
        v-for="message in messages"
        :key="message.id"
        :class="[
          'flex',
          message.direction === 'outbound' ? 'justify-end' : 'justify-start'
        ]"
      >
        <div
          :class="[
            'max-w-xs lg:max-w-md px-4 py-2 rounded-lg',
            message.direction === 'outbound' 
              ? 'bg-green-500 text-white' 
              : 'bg-gray-200 text-gray-900'
          ]"
        >
          <p class="text-sm">{{ message.content }}</p>
          <p 
            :class="[
              'text-xs mt-1',
              message.direction === 'outbound' ? 'text-green-100' : 'text-gray-500'
            ]"
          >
            {{ formatTime(message.created_at) }}
          </p>
        </div>
      </div>
      
      <!-- Loading indicator -->
      <div v-if="loading" class="text-center py-4">
        <span class="text-gray-500">Loading messages...</span>
      </div>
      
      <!-- Load more trigger -->
      <div ref="loadMoreTrigger" class="h-1"></div>
    </div>
    
    <!-- Stats Bar -->
    <div class="p-4 border-t bg-gray-50">
      <div class="flex justify-between text-sm text-gray-600">
        <span>{{ messages.length }} messages</span>
        <span v-if="oldestMessage">
          Since {{ formatDate(oldestMessage.created_at) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useIntersectionObserver } from '@vueuse/core'
import { useMessagesStore } from '@/stores/messages'
import { debounce } from '@/utils/debounce'

const messagesStore = useMessagesStore()

const searchQuery = ref('')
const messagesContainer = ref(null)
const loadMoreTrigger = ref(null)

const messages = computed(() => messagesStore.messages)
const loading = computed(() => messagesStore.loading)
const hasMore = computed(() => messagesStore.hasMore)
const oldestMessage = computed(() => 
  messages.value.length > 0 ? messages.value[messages.value.length - 1] : null
)

// Load more messages when trigger is visible
const { stop } = useIntersectionObserver(
  loadMoreTrigger,
  ([{ isIntersecting }]) => {
    if (isIntersecting && hasMore.value && !loading.value) {
      messagesStore.loadMore()
    }
  }
)

// Debounced search
const debouncedSearch = debounce(() => {
  messagesStore.searchMessages(searchQuery.value)
}, 300)

// Auto-refresh messages
let refreshInterval
onMounted(() => {
  messagesStore.loadMessages()
  
  // Refresh every 10 seconds
  refreshInterval = setInterval(() => {
    messagesStore.refreshLatest()
  }, 10000)
})

onUnmounted(() => {
  clearInterval(refreshInterval)
  stop()
})

// Utility functions
function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString()
}

function formatDate(timestamp) {
  return new Date(timestamp).toLocaleDateString()
}

// Maintain scroll position when loading older messages
let lastScrollHeight = 0
function handleScroll() {
  const container = messagesContainer.value
  if (container.scrollTop === 0 && hasMore.value && !loading.value) {
    lastScrollHeight = container.scrollHeight
    messagesStore.loadMore().then(() => {
      // Restore scroll position
      container.scrollTop = container.scrollHeight - lastScrollHeight
    })
  }
}
</script>
```

### Step 5: Create LLM Settings Component
```vue
<!-- src/components/LLMSettings.vue -->
<template>
  <div class="p-6 bg-white rounded-lg shadow">
    <h3 class="text-lg font-semibold mb-4">AI Provider Settings</h3>
    
    <form @submit.prevent="saveSettings" class="space-y-6">
      <!-- Provider Selection -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">
          Select AI Provider
        </label>
        <div class="space-y-2">
          <label
            v-for="provider in providers"
            :key="provider.value"
            class="flex items-center p-3 border rounded-lg cursor-pointer hover:bg-gray-50"
          >
            <input
              v-model="selectedProvider"
              type="radio"
              :value="provider.value"
              class="mr-3"
            />
            <div class="flex-1">
              <p class="font-medium">{{ provider.name }}</p>
              <p class="text-sm text-gray-600">{{ provider.description }}</p>
            </div>
          </label>
        </div>
      </div>
      
      <!-- API Key Input -->
      <div v-if="selectedProvider">
        <label class="block text-sm font-medium text-gray-700 mb-1">
          API Key
        </label>
        <input
          v-model="apiKey"
          type="password"
          required
          placeholder="Enter your API key"
          class="w-full px-3 py-2 border rounded-md"
        />
        <p class="mt-1 text-sm text-gray-600">
          Your API key is encrypted and stored securely
        </p>
      </div>
      
      <!-- Model Selection -->
      <div v-if="selectedProvider && availableModels.length > 0">
        <label class="block text-sm font-medium text-gray-700 mb-1">
          Model
        </label>
        <select
          v-model="selectedModel"
          class="w-full px-3 py-2 border rounded-md"
        >
          <option
            v-for="model in availableModels"
            :key="model.value"
            :value="model.value"
          >
            {{ model.name }} - {{ model.description }}
          </option>
        </select>
      </div>
      
      <!-- Advanced Settings -->
      <details class="border rounded-lg p-4">
        <summary class="cursor-pointer font-medium">
          Advanced Settings
        </summary>
        
        <div class="mt-4 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Temperature (0-1)
            </label>
            <input
              v-model.number="temperature"
              type="number"
              min="0"
              max="1"
              step="0.1"
              class="w-full px-3 py-2 border rounded-md"
            />
            <p class="mt-1 text-sm text-gray-600">
              Controls randomness. Lower = more focused, Higher = more creative
            </p>
          </div>
          
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Max Tokens
            </label>
            <input
              v-model.number="maxTokens"
              type="number"
              min="100"
              max="4000"
              class="w-full px-3 py-2 border rounded-md"
            />
          </div>
        </div>
      </details>
      
      <!-- Actions -->
      <div class="flex space-x-4">
        <button
          type="submit"
          :disabled="saving || !selectedProvider || !apiKey"
          class="flex-1 py-2 px-4 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
        >
          {{ saving ? 'Saving...' : 'Save Settings' }}
        </button>
        
        <button
          v-if="hasExistingConfig"
          type="button"
          @click="testConnection"
          :disabled="testing"
          class="py-2 px-4 border border-gray-300 rounded-md hover:bg-gray-50"
        >
          {{ testing ? 'Testing...' : 'Test Connection' }}
        </button>
      </div>
    </form>
    
    <!-- Status Messages -->
    <div v-if="statusMessage" :class="[
      'mt-4 p-3 rounded-md',
      statusMessage.type === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
    ]">
      {{ statusMessage.text }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useLLMStore } from '@/stores/llm'

const llmStore = useLLMStore()

const selectedProvider = ref('')
const apiKey = ref('')
const selectedModel = ref('')
const temperature = ref(0.7)
const maxTokens = ref(1000)
const saving = ref(false)
const testing = ref(false)
const statusMessage = ref(null)

const providers = [
  {
    value: 'openai',
    name: 'OpenAI',
    description: 'GPT-4, GPT-3.5 Turbo'
  },
  {
    value: 'anthropic',
    name: 'Anthropic',
    description: 'Claude 3 Opus, Sonnet, Haiku'
  },
  {
    value: 'google',
    name: 'Google',
    description: 'Gemini Pro, Gemini Ultra'
  }
]

const modelsByProvider = {
  openai: [
    { value: 'gpt-4-turbo-preview', name: 'GPT-4 Turbo', description: 'Most capable' },
    { value: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo', description: 'Fast and efficient' }
  ],
  anthropic: [
    { value: 'claude-3-opus', name: 'Claude 3 Opus', description: 'Most capable' },
    { value: 'claude-3-sonnet', name: 'Claude 3 Sonnet', description: 'Balanced' },
    { value: 'claude-3-haiku', name: 'Claude 3 Haiku', description: 'Fast and efficient' }
  ],
  google: [
    { value: 'gemini-pro', name: 'Gemini Pro', description: 'Advanced reasoning' },
    { value: 'gemini-pro-vision', name: 'Gemini Pro Vision', description: 'Multimodal' }
  ]
}

const availableModels = computed(() => 
  modelsByProvider[selectedProvider.value] || []
)

const hasExistingConfig = computed(() => 
  llmStore.currentConfig !== null
)

// Load existing configuration
onMounted(async () => {
  await llmStore.loadConfiguration()
  
  if (llmStore.currentConfig) {
    selectedProvider.value = llmStore.currentConfig.provider
    selectedModel.value = llmStore.currentConfig.model_settings.model
    temperature.value = llmStore.currentConfig.model_settings.temperature
    maxTokens.value = llmStore.currentConfig.model_settings.max_tokens
    // Don't load the API key for security
  }
})

// Reset model when provider changes
watch(selectedProvider, () => {
  selectedModel.value = availableModels.value[0]?.value || ''
})

async function saveSettings() {
  saving.value = true
  statusMessage.value = null
  
  const config = {
    provider: selectedProvider.value,
    api_key: apiKey.value,
    model_settings: {
      model: selectedModel.value,
      temperature: temperature.value,
      max_tokens: maxTokens.value
    }
  }
  
  const result = await llmStore.saveConfiguration(config)
  
  if (result.success) {
    statusMessage.value = {
      type: 'success',
      text: 'Settings saved successfully!'
    }
    // Clear API key from form for security
    apiKey.value = ''
  } else {
    statusMessage.value = {
      type: 'error',
      text: result.message
    }
  }
  
  saving.value = false
}

async function testConnection() {
  testing.value = true
  statusMessage.value = null
  
  const result = await llmStore.testConfiguration()
  
  statusMessage.value = {
    type: result.success ? 'success' : 'error',
    text: result.message
  }
  
  testing.value = false
}
</script>
```

### Step 6: Create Dashboard Layout
```vue
<!-- src/pages/DashboardPage.vue -->
<template>
  <div class="min-h-screen bg-gray-100">
    <!-- Navigation -->
    <nav class="bg-white shadow">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between h-16">
          <div class="flex items-center">
            <h1 class="text-xl font-semibold">Zapa Dashboard</h1>
          </div>
          
          <div class="flex items-center space-x-4">
            <span class="text-sm text-gray-600">
              {{ userPhone }}
            </span>
            <button
              @click="logout"
              class="text-sm text-gray-500 hover:text-gray-700"
            >
              Logout
            </button>
          </div>
        </div>
      </div>
    </nav>
    
    <!-- Main Content -->
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <!-- Messages Section -->
        <div class="lg:col-span-2">
          <div class="bg-white rounded-lg shadow h-[600px]">
            <MessageHistory />
          </div>
        </div>
        
        <!-- Settings Section -->
        <div class="space-y-6">
          <!-- Quick Stats -->
          <div class="bg-white rounded-lg shadow p-6">
            <h3 class="text-lg font-semibold mb-4">Quick Stats</h3>
            <dl class="space-y-2">
              <div class="flex justify-between">
                <dt class="text-gray-600">Total Messages</dt>
                <dd class="font-medium">{{ stats.total_messages }}</dd>
              </div>
              <div class="flex justify-between">
                <dt class="text-gray-600">This Week</dt>
                <dd class="font-medium">{{ stats.this_week }}</dd>
              </div>
              <div class="flex justify-between">
                <dt class="text-gray-600">AI Provider</dt>
                <dd class="font-medium">{{ stats.provider || 'Not configured' }}</dd>
              </div>
            </dl>
          </div>
          
          <!-- LLM Settings -->
          <LLMSettings />
          
          <!-- Export Options -->
          <div class="bg-white rounded-lg shadow p-6">
            <h3 class="text-lg font-semibold mb-4">Export Data</h3>
            <div class="space-y-2">
              <button
                @click="exportMessages('json')"
                class="w-full py-2 px-4 border border-gray-300 rounded-md hover:bg-gray-50"
              >
                Export as JSON
              </button>
              <button
                @click="exportMessages('csv')"
                class="w-full py-2 px-4 border border-gray-300 rounded-md hover:bg-gray-50"
              >
                Export as CSV
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useMessagesStore } from '@/stores/messages'
import { useStatsStore } from '@/stores/stats'
import MessageHistory from '@/components/MessageHistory.vue'
import LLMSettings from '@/components/LLMSettings.vue'

const authStore = useAuthStore()
const messagesStore = useMessagesStore()
const statsStore = useStatsStore()

const userPhone = computed(() => authStore.user?.phoneNumber || '')
const stats = computed(() => statsStore.stats)

onMounted(() => {
  statsStore.loadStats()
})

function logout() {
  authStore.logout()
}

async function exportMessages(format) {
  const data = await messagesStore.exportMessages(format)
  
  // Create download
  const blob = new Blob([data], { 
    type: format === 'json' ? 'application/json' : 'text/csv' 
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `zapa-messages-${Date.now()}.${format}`
  a.click()
  URL.revokeObjectURL(url)
}
</script>
```

## Testing Strategy

### Unit Tests
```javascript
// tests/unit/components/MessageHistory.test.js
import { mount } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'
import MessageHistory from '@/components/MessageHistory.vue'

describe('MessageHistory', () => {
  it('displays messages correctly', () => {
    const wrapper = mount(MessageHistory, {
      global: {
        plugins: [createTestingPinia({
          initialState: {
            messages: {
              messages: [
                {
                  id: 1,
                  content: 'Hello',
                  direction: 'inbound',
                  created_at: new Date()
                },
                {
                  id: 2,
                  content: 'Hi there!',
                  direction: 'outbound',
                  created_at: new Date()
                }
              ]
            }
          }
        })]
      }
    })
    
    const messages = wrapper.findAll('[class*="rounded-lg"]')
    expect(messages).toHaveLength(2)
    expect(messages[0].text()).toContain('Hello')
    expect(messages[1].text()).toContain('Hi there!')
  })
})
```

### E2E Tests
```javascript
// tests/e2e/auth-flow.spec.js
import { test, expect } from '@playwright/test'

test('complete authentication flow', async ({ page }) => {
  // Navigate to login
  await page.goto('/login')
  
  // Enter phone number
  await page.fill('input[type="tel"]', '+1234567890')
  await page.click('button:has-text("Send Code")')
  
  // Wait for code input
  await expect(page.locator('input[maxlength="6"]')).toBeVisible()
  
  // Enter code (in real test, would intercept API call)
  await page.fill('input[maxlength="6"]', '123456')
  await page.click('button:has-text("Verify")')
  
  // Should redirect to dashboard
  await expect(page).toHaveURL('/dashboard')
  await expect(page.locator('h1')).toContainText('Zapa Dashboard')
})
```

## Implementation Notes

1. **State Management**: Use Pinia for reactive state management
2. **API Integration**: Axios with interceptors for auth headers
3. **Real-time Updates**: Polling for now, WebSocket later
4. **Mobile Responsive**: Tailwind CSS with mobile-first design
5. **Security**: JWT stored in localStorage with auto-refresh
6. **Performance**: Virtual scrolling for large message lists

## Dependencies
- Vue 3 with Composition API
- Vue Router 4 for navigation
- Pinia for state management
- Axios for API calls
- Tailwind CSS for styling
- Vite for build tooling
- Vitest for testing

## Next Steps
- Task 15: Vue.js Frontend Setup (Admin Panel)
- Task 16: Integration Testing