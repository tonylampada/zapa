# Task 08: Frontend Structure Setup with Vue.js and Tests

## Objective
Set up Vue.js frontend structure with testing infrastructure, routing, and state management.

## Prerequisites
- Backend tasks completed or in progress
- Node.js and npm installed
- Understanding of Vue 3 Composition API

## Requirements
- Create Vue 3 project with TypeScript
- Set up testing with Vitest and Vue Test Utils
- Configure routing with Vue Router
- Set up state management with Pinia
- Create base components and layouts
- Implement API client structure

## Project Setup

### frontend/package.json
```json
{
  "name": "whatsapp-agent-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc && vite build",
    "preview": "vite preview",
    "test": "vitest",
    "test:ui": "vitest --ui",
    "test:coverage": "vitest --coverage",
    "lint": "eslint . --ext .vue,.js,.jsx,.cjs,.mjs,.ts,.tsx,.cts,.mts --fix",
    "format": "prettier --write src/"
  },
  "dependencies": {
    "vue": "^3.3.8",
    "vue-router": "^4.2.5",
    "pinia": "^2.1.7",
    "axios": "^1.6.2",
    "@vueuse/core": "^10.7.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^4.5.0",
    "@vue/test-utils": "^2.4.3",
    "@vitest/ui": "^1.0.4",
    "@types/node": "^20.10.4",
    "typescript": "^5.3.3",
    "vite": "^5.0.8",
    "vitest": "^1.0.4",
    "vue-tsc": "^1.8.25",
    "@typescript-eslint/eslint-plugin": "^6.14.0",
    "@typescript-eslint/parser": "^6.14.0",
    "eslint": "^8.55.0",
    "eslint-plugin-vue": "^9.19.2",
    "prettier": "^3.1.1",
    "jsdom": "^23.0.1",
    "@vitest/coverage-v8": "^1.0.4"
  }
}
```

### frontend/vite.config.ts
```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 8080,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },
  test: {
    globals: true,
    environment: 'jsdom',
    coverage: {
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/main.ts',
      ]
    }
  }
})
```

### frontend/tsconfig.json
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "module": "ESNext",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "preserve",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src/**/*.ts", "src/**/*.tsx", "src/**/*.vue"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

### frontend/src/main.ts
```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './assets/main.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
```

### frontend/src/App.vue
```vue
<template>
  <div id="app">
    <router-view />
  </div>
</template>

<script setup lang="ts">
// App setup logic here
</script>

<style>
#app {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen,
    Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2c3e50;
}
</style>
```

### frontend/src/router/index.ts
```typescript
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    name: 'dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/sessions',
    name: 'sessions',
    component: () => import('@/views/SessionsView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/sessions/:sessionId/chat/:contactJid',
    name: 'chat',
    component: () => import('@/views/ChatView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/agents',
    name: 'agents',
    component: () => import('@/views/AgentsView.vue'),
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guard
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next({ name: 'login', query: { redirect: to.fullPath } })
  } else if (to.name === 'login' && authStore.isAuthenticated) {
    next({ name: 'dashboard' })
  } else {
    next()
  }
})

export default router
```

### frontend/src/stores/auth.ts
```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User } from '@/types'
import { authApi } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)
  
  const isAuthenticated = computed(() => !!token.value)
  
  async function login(username: string, password: string) {
    try {
      const response = await authApi.login(username, password)
      token.value = response.access_token
      
      // Store token in localStorage
      localStorage.setItem('auth_token', response.access_token)
      
      // Decode user info from token (in real app)
      user.value = { id: 1, username, email: `${username}@example.com` }
      
      return { success: true }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }
  
  function logout() {
    user.value = null
    token.value = null
    localStorage.removeItem('auth_token')
  }
  
  function initializeAuth() {
    const storedToken = localStorage.getItem('auth_token')
    if (storedToken) {
      token.value = storedToken
      // In real app, would validate token and fetch user info
      user.value = { id: 1, username: 'user', email: 'user@example.com' }
    }
  }
  
  return {
    user,
    token,
    isAuthenticated,
    login,
    logout,
    initializeAuth
  }
})
```

### frontend/src/api/client.ts
```typescript
import axios, { type AxiosInstance } from 'axios'
import { useAuthStore } from '@/stores/auth'

const apiClient: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor to add auth token
apiClient.interceptors.request.use(
  (config) => {
    const authStore = useAuthStore()
    if (authStore.token) {
      config.headers.Authorization = `Bearer ${authStore.token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const authStore = useAuthStore()
      authStore.logout()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default apiClient
```

### frontend/src/api/auth.ts
```typescript
import apiClient from './client'

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface RegisterData {
  username: string
  email: string
  password: string
}

export const authApi = {
  async login(username: string, password: string): Promise<LoginResponse> {
    const response = await apiClient.post<LoginResponse>('/auth/login', {
      username,
      password
    })
    return response.data
  },
  
  async register(data: RegisterData) {
    const response = await apiClient.post('/auth/register', data)
    return response.data
  }
}
```

### frontend/src/types/index.ts
```typescript
export interface User {
  id: number
  username: string
  email: string
}

export interface Agent {
  id: number
  name: string
  description?: string
  model: string
  system_prompt: string
  functions: any[]
  is_active: boolean
  created_at: string
}

export interface Session {
  id: string
  status: 'qr_pending' | 'connected' | 'disconnected' | 'error'
  phone_number?: string
  qr_code?: string
  agent_id: number
  agent: Agent
  connected_at?: string
  created_at: string
}

export interface Message {
  id: number
  session_id: string
  contact_jid: string
  direction: 'incoming' | 'outgoing'
  message_type: string
  content: string
  timestamp: string
}
```

### frontend/tests/unit/stores/auth.test.ts
```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api/auth'

vi.mock('@/api/auth')

describe('Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })
  
  it('initializes with no user', () => {
    const store = useAuthStore()
    expect(store.user).toBeNull()
    expect(store.token).toBeNull()
    expect(store.isAuthenticated).toBe(false)
  })
  
  it('logs in successfully', async () => {
    const store = useAuthStore()
    const mockResponse = {
      access_token: 'test-token',
      token_type: 'bearer'
    }
    
    vi.mocked(authApi.login).mockResolvedValue(mockResponse)
    
    const result = await store.login('testuser', 'password')
    
    expect(result.success).toBe(true)
    expect(store.token).toBe('test-token')
    expect(store.isAuthenticated).toBe(true)
    expect(localStorage.getItem('auth_token')).toBe('test-token')
  })
  
  it('handles login failure', async () => {
    const store = useAuthStore()
    
    vi.mocked(authApi.login).mockRejectedValue(new Error('Invalid credentials'))
    
    const result = await store.login('testuser', 'wrongpass')
    
    expect(result.success).toBe(false)
    expect(result.error).toBe('Invalid credentials')
    expect(store.isAuthenticated).toBe(false)
  })
  
  it('logs out correctly', () => {
    const store = useAuthStore()
    store.token = 'test-token'
    store.user = { id: 1, username: 'test', email: 'test@example.com' }
    localStorage.setItem('auth_token', 'test-token')
    
    store.logout()
    
    expect(store.user).toBeNull()
    expect(store.token).toBeNull()
    expect(store.isAuthenticated).toBe(false)
    expect(localStorage.getItem('auth_token')).toBeNull()
  })
  
  it('initializes auth from localStorage', () => {
    localStorage.setItem('auth_token', 'stored-token')
    
    const store = useAuthStore()
    store.initializeAuth()
    
    expect(store.token).toBe('stored-token')
    expect(store.isAuthenticated).toBe(true)
  })
})
```

### frontend/tests/unit/router/guards.test.ts
```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createRouter, createWebHistory } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

describe('Router Guards', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  
  it('redirects to login when not authenticated', async () => {
    const authStore = useAuthStore()
    authStore.token = null
    
    await router.push('/sessions')
    
    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/sessions')
  })
  
  it('allows access when authenticated', async () => {
    const authStore = useAuthStore()
    authStore.token = 'test-token'
    
    await router.push('/sessions')
    
    expect(router.currentRoute.value.name).toBe('sessions')
  })
  
  it('redirects from login to dashboard when authenticated', async () => {
    const authStore = useAuthStore()
    authStore.token = 'test-token'
    
    await router.push('/login')
    
    expect(router.currentRoute.value.name).toBe('dashboard')
  })
})
```

### frontend/tests/unit/api/client.test.ts
```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import axios from 'axios'
import apiClient from '@/api/client'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

vi.mock('axios')

describe('API Client', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  
  it('adds auth token to requests', async () => {
    const authStore = useAuthStore()
    authStore.token = 'test-token'
    
    const mockRequest = { headers: {} }
    const interceptor = apiClient.interceptors.request.handlers[0]
    
    const result = await interceptor.fulfilled(mockRequest)
    
    expect(result.headers.Authorization).toBe('Bearer test-token')
  })
  
  it('handles 401 responses', async () => {
    const authStore = useAuthStore()
    authStore.token = 'test-token'
    
    const mockError = {
      response: { status: 401 }
    }
    
    const interceptor = apiClient.interceptors.response.handlers[0]
    
    // Mock window.location
    delete window.location
    window.location = { href: '' } as any
    
    try {
      await interceptor.rejected(mockError)
    } catch (error) {
      expect(authStore.token).toBeNull()
      expect(window.location.href).toBe('/login')
    }
  })
})
```

### frontend/src/components/base/BaseButton.vue
```vue
<template>
  <button
    :type="type"
    :class="buttonClasses"
    :disabled="disabled || loading"
    @click="$emit('click', $event)"
  >
    <span v-if="loading">Loading...</span>
    <slot v-else />
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  variant?: 'primary' | 'secondary' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  type?: 'button' | 'submit' | 'reset'
  disabled?: boolean
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'primary',
  size: 'md',
  type: 'button',
  disabled: false,
  loading: false
})

defineEmits<{
  click: [event: MouseEvent]
}>()

const buttonClasses = computed(() => [
  'base-button',
  `base-button--${props.variant}`,
  `base-button--${props.size}`,
  {
    'base-button--disabled': props.disabled,
    'base-button--loading': props.loading
  }
])
</script>

<style scoped>
.base-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 0.375rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.base-button--primary {
  background-color: #3b82f6;
  color: white;
}

.base-button--primary:hover:not(:disabled) {
  background-color: #2563eb;
}

.base-button--md {
  padding: 0.5rem 1rem;
  font-size: 1rem;
}

.base-button--disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
```

### frontend/tests/unit/components/BaseButton.test.ts
```typescript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseButton from '@/components/base/BaseButton.vue'

describe('BaseButton', () => {
  it('renders slot content', () => {
    const wrapper = mount(BaseButton, {
      slots: {
        default: 'Click me'
      }
    })
    
    expect(wrapper.text()).toBe('Click me')
  })
  
  it('emits click event', async () => {
    const wrapper = mount(BaseButton)
    
    await wrapper.trigger('click')
    
    expect(wrapper.emitted('click')).toHaveLength(1)
  })
  
  it('disables button when disabled prop is true', () => {
    const wrapper = mount(BaseButton, {
      props: {
        disabled: true
      }
    })
    
    expect(wrapper.attributes('disabled')).toBeDefined()
  })
  
  it('shows loading text when loading', () => {
    const wrapper = mount(BaseButton, {
      props: {
        loading: true
      },
      slots: {
        default: 'Submit'
      }
    })
    
    expect(wrapper.text()).toBe('Loading...')
    expect(wrapper.attributes('disabled')).toBeDefined()
  })
  
  it('applies correct variant classes', () => {
    const wrapper = mount(BaseButton, {
      props: {
        variant: 'danger'
      }
    })
    
    expect(wrapper.classes()).toContain('base-button--danger')
  })
})
```

## Success Criteria
- [ ] Vue 3 project created with TypeScript
- [ ] Testing infrastructure set up with Vitest
- [ ] Router configured with navigation guards
- [ ] Pinia store for authentication
- [ ] API client with interceptors
- [ ] Base components created
- [ ] All tests passing
- [ ] Code coverage above 80%

## Commands to Run
```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Run tests
npm run test

# Run tests with UI
npm run test:ui

# Run tests with coverage
npm run test:coverage

# Build for production
npm run build
```