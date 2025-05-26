# Task 15: Admin Frontend Setup

## Overview
Create the admin frontend for Zapa Private. This provides a web interface for administrators to manage the WhatsApp integration, monitor system health, view all users, and configure system settings.

## Prerequisites
- Task 10: Admin API Endpoints
- Task 13: WhatsApp Integration (for monitoring)
- Task 14: Frontend User Dashboard (to reuse components)

## Acceptance Criteria
1. Vue.js admin panel with authentication
2. System health monitoring dashboard
3. User management interface
4. WhatsApp session management
5. Message queue monitoring
6. System logs viewer
7. Configuration management
8. Real-time updates for critical metrics

## Test-Driven Development Steps

### Step 1: Create Admin Frontend Project
```bash
# Create admin frontend
cd frontend
npm create vite@latest zapa-admin -- --template vue
cd zapa-admin

# Install dependencies (same as user frontend plus extras)
npm install vue-router@4 pinia axios @vueuse/core
npm install chart.js vue-chartjs date-fns
npm install -D @vitejs/plugin-vue tailwindcss postcss autoprefixer
npm install -D @vue/test-utils vitest @vitest/ui happy-dom

# Initialize Tailwind
npx tailwindcss init -p
```

**Shared Components Library:**
```bash
# Create shared components package
cd frontend
mkdir zapa-shared
cd zapa-shared
npm init -y

# Install as workspace in both frontends
# frontend/package.json
{
  "workspaces": ["zapa-admin", "zapa-public", "zapa-shared"]
}
```

### Step 2: Create Admin Auth Store
```javascript
// src/stores/adminAuth.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import adminApi from '@/api/admin'
import { useRouter } from 'vue-router'

export const useAdminAuthStore = defineStore('adminAuth', () => {
  const token = ref(localStorage.getItem('admin_token'))
  const admin = ref(null)
  const router = useRouter()
  
  const isAuthenticated = computed(() => !!token.value)
  const isSuper = computed(() => admin.value?.role === 'super')
  
  async function login(username, password) {
    try {
      const response = await adminApi.login(username, password)
      
      // Store token
      token.value = response.access_token
      localStorage.setItem('admin_token', response.access_token)
      
      // Store admin info
      admin.value = {
        id: response.admin_id,
        username: response.username,
        role: response.role
      }
      
      // Configure axios
      adminApi.setAuthToken(response.access_token)
      
      return { success: true }
    } catch (error) {
      return { 
        success: false, 
        message: error.response?.data?.detail || 'Login failed' 
      }
    }
  }
  
  async function verifyToken() {
    if (!token.value) return false
    
    try {
      const response = await adminApi.getCurrentAdmin()
      admin.value = response
      return true
    } catch {
      logout()
      return false
    }
  }
  
  function logout() {
    token.value = null
    admin.value = null
    localStorage.removeItem('admin_token')
    adminApi.clearAuthToken()
    router.push('/login')
  }
  
  // Initialize
  if (token.value) {
    adminApi.setAuthToken(token.value)
    verifyToken()
  }
  
  return {
    token,
    admin,
    isAuthenticated,
    isSuper,
    login,
    logout,
    verifyToken
  }
})
```

### Step 3: Create System Health Dashboard
```vue
<!-- src/components/SystemHealthDashboard.vue -->
<template>
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
    <!-- Health Status Cards -->
    <div
      v-for="component in healthComponents"
      :key="component.name"
      :class="[
        'bg-white rounded-lg shadow p-6',
        getStatusColor(component.status)
      ]"
    >
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-lg font-semibold">{{ component.title }}</h3>
          <p class="text-sm text-gray-600 mt-1">{{ component.message }}</p>
        </div>
        <div :class="['w-4 h-4 rounded-full', getStatusDot(component.status)]"></div>
      </div>
      
      <div v-if="component.metadata" class="mt-4 space-y-1">
        <div
          v-for="(value, key) in component.metadata"
          :key="key"
          class="flex justify-between text-sm"
        >
          <span class="text-gray-600">{{ formatKey(key) }}:</span>
          <span class="font-medium">{{ value }}</span>
        </div>
      </div>
    </div>
    
    <!-- Message Queue Chart -->
    <div class="col-span-full lg:col-span-2 bg-white rounded-lg shadow p-6">
      <h3 class="text-lg font-semibold mb-4">Message Queue</h3>
      <LineChart
        :data="queueChartData"
        :options="chartOptions"
        class="h-64"
      />
    </div>
    
    <!-- Active Sessions -->
    <div class="col-span-full lg:col-span-2 bg-white rounded-lg shadow p-6">
      <h3 class="text-lg font-semibold mb-4">WhatsApp Sessions</h3>
      <div class="space-y-3">
        <div
          v-for="session in sessions"
          :key="session.id"
          class="flex items-center justify-between p-3 bg-gray-50 rounded"
        >
          <div>
            <p class="font-medium">{{ session.phone_number }}</p>
            <p class="text-sm text-gray-600">
              {{ session.status }} - {{ formatDuration(session.uptime) }}
            </p>
          </div>
          <button
            v-if="session.status !== 'connected'"
            @click="reconnectSession(session.id)"
            class="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Reconnect
          </button>
        </div>
        
        <button
          @click="showQRCode = true"
          class="w-full py-2 border border-dashed border-gray-300 rounded text-gray-600 hover:border-gray-400"
        >
          + Add New Session
        </button>
      </div>
    </div>
  </div>
  
  <!-- QR Code Modal -->
  <Modal v-model="showQRCode" title="Scan QR Code">
    <div class="text-center">
      <div v-if="qrCode" class="inline-block p-4 bg-white rounded">
        <img :src="qrCode" alt="WhatsApp QR Code" class="w-64 h-64" />
      </div>
      <p class="mt-4 text-sm text-gray-600">
        Scan this QR code with WhatsApp to add a new session
      </p>
    </div>
  </Modal>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Line as LineChart } from 'vue-chartjs'
import { useHealthStore } from '@/stores/health'
import { useSessionStore } from '@/stores/sessions'
import Modal from '@/components/Modal.vue'
import { formatDuration, formatKey } from '@/utils/format'

const healthStore = useHealthStore()
const sessionStore = useSessionStore()

const showQRCode = ref(false)
const qrCode = ref('')

const healthComponents = computed(() => {
  const health = healthStore.health
  return [
    {
      name: 'whatsapp_bridge',
      title: 'WhatsApp Bridge',
      status: health.whatsapp_bridge?.status || 'unknown',
      message: health.whatsapp_bridge?.message || 'Checking...',
      metadata: health.whatsapp_bridge?.metadata
    },
    {
      name: 'message_queue',
      title: 'Message Queue',
      status: health.message_queue?.status || 'unknown',
      message: health.message_queue?.message || 'Checking...',
      metadata: health.message_queue?.metadata
    },
    {
      name: 'database',
      title: 'Database',
      status: health.database?.status || 'unknown',
      message: health.database?.message || 'Checking...',
      metadata: health.database?.metadata
    },
    {
      name: 'redis',
      title: 'Redis Cache',
      status: health.redis?.status || 'unknown',
      message: health.redis?.message || 'Checking...',
      metadata: health.redis?.metadata
    }
  ]
})

const sessions = computed(() => sessionStore.sessions)

const queueChartData = computed(() => ({
  labels: healthStore.queueHistory.map(h => 
    new Date(h.timestamp).toLocaleTimeString()
  ),
  datasets: [{
    label: 'Queued',
    data: healthStore.queueHistory.map(h => h.queued),
    borderColor: 'rgb(59, 130, 246)',
    backgroundColor: 'rgba(59, 130, 246, 0.1)',
    tension: 0.4
  }, {
    label: 'Processing',
    data: healthStore.queueHistory.map(h => h.processing),
    borderColor: 'rgb(16, 185, 129)',
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    tension: 0.4
  }]
}))

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'bottom'
    }
  },
  scales: {
    y: {
      beginAtZero: true
    }
  }
}

// Refresh data periodically
let refreshInterval
onMounted(() => {
  healthStore.loadHealth()
  sessionStore.loadSessions()
  
  refreshInterval = setInterval(() => {
    healthStore.loadHealth()
    sessionStore.loadSessions()
  }, 5000) // Every 5 seconds
})

onUnmounted(() => {
  clearInterval(refreshInterval)
})

async function reconnectSession(sessionId) {
  await sessionStore.reconnectSession(sessionId)
}

function getStatusColor(status) {
  const colors = {
    healthy: 'border-l-4 border-green-500',
    degraded: 'border-l-4 border-yellow-500',
    unhealthy: 'border-l-4 border-red-500',
    unknown: 'border-l-4 border-gray-500'
  }
  return colors[status] || colors.unknown
}

function getStatusDot(status) {
  const colors = {
    healthy: 'bg-green-500',
    degraded: 'bg-yellow-500',
    unhealthy: 'bg-red-500',
    unknown: 'bg-gray-500'
  }
  return colors[status] || colors.unknown
}
</script>
```

### Step 4: Create User Management Interface
```vue
<!-- src/components/UserManagement.vue -->
<template>
  <div class="bg-white rounded-lg shadow">
    <!-- Header with Search -->
    <div class="p-6 border-b">
      <div class="flex items-center justify-between">
        <h2 class="text-xl font-semibold">User Management</h2>
        <div class="flex items-center space-x-4">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search users..."
            class="px-4 py-2 border rounded-lg"
            @input="debouncedSearch"
          />
          <select
            v-model="filterStatus"
            class="px-4 py-2 border rounded-lg"
            @change="loadUsers"
          >
            <option value="">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
      </div>
    </div>
    
    <!-- Users Table -->
    <div class="overflow-x-auto">
      <table class="w-full">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              User
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Status
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Messages
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              LLM Provider
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Last Active
            </th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Actions
            </th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr v-for="user in users" :key="user.id">
            <td class="px-6 py-4 whitespace-nowrap">
              <div>
                <div class="text-sm font-medium text-gray-900">
                  {{ user.phone_number }}
                </div>
                <div class="text-sm text-gray-500">
                  ID: {{ user.id }}
                </div>
              </div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              <span
                :class="[
                  'px-2 inline-flex text-xs leading-5 font-semibold rounded-full',
                  user.is_active
                    ? 'bg-green-100 text-green-800'
                    : 'bg-red-100 text-red-800'
                ]"
              >
                {{ user.is_active ? 'Active' : 'Inactive' }}
              </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ user.message_count || 0 }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ user.llm_provider || 'Not configured' }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ formatDate(user.last_active) }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
              <button
                @click="viewUserDetails(user)"
                class="text-indigo-600 hover:text-indigo-900 mr-4"
              >
                View
              </button>
              <button
                @click="toggleUserStatus(user)"
                :class="[
                  'hover:underline',
                  user.is_active ? 'text-red-600' : 'text-green-600'
                ]"
              >
                {{ user.is_active ? 'Deactivate' : 'Activate' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    
    <!-- Pagination -->
    <div class="px-6 py-4 border-t">
      <Pagination
        v-model:page="currentPage"
        :total="totalUsers"
        :per-page="perPage"
        @update:page="loadUsers"
      />
    </div>
  </div>
  
  <!-- User Details Modal -->
  <Modal v-model="showUserDetails" title="User Details" size="lg">
    <div v-if="selectedUser" class="space-y-6">
      <!-- User Info -->
      <div>
        <h3 class="text-lg font-medium mb-3">User Information</h3>
        <dl class="grid grid-cols-2 gap-4">
          <div>
            <dt class="text-sm text-gray-600">Phone Number</dt>
            <dd class="font-medium">{{ selectedUser.phone_number }}</dd>
          </div>
          <div>
            <dt class="text-sm text-gray-600">User ID</dt>
            <dd class="font-medium">{{ selectedUser.id }}</dd>
          </div>
          <div>
            <dt class="text-sm text-gray-600">Created</dt>
            <dd class="font-medium">{{ formatDate(selectedUser.created_at) }}</dd>
          </div>
          <div>
            <dt class="text-sm text-gray-600">Status</dt>
            <dd>
              <span
                :class="[
                  'px-2 py-1 text-xs rounded-full',
                  selectedUser.is_active
                    ? 'bg-green-100 text-green-800'
                    : 'bg-red-100 text-red-800'
                ]"
              >
                {{ selectedUser.is_active ? 'Active' : 'Inactive' }}
              </span>
            </dd>
          </div>
        </dl>
      </div>
      
      <!-- Message Stats -->
      <div>
        <h3 class="text-lg font-medium mb-3">Message Statistics</h3>
        <div class="grid grid-cols-3 gap-4">
          <div class="bg-gray-50 rounded p-4 text-center">
            <p class="text-2xl font-bold">{{ selectedUser.message_count || 0 }}</p>
            <p class="text-sm text-gray-600">Total Messages</p>
          </div>
          <div class="bg-gray-50 rounded p-4 text-center">
            <p class="text-2xl font-bold">{{ selectedUser.messages_today || 0 }}</p>
            <p class="text-sm text-gray-600">Today</p>
          </div>
          <div class="bg-gray-50 rounded p-4 text-center">
            <p class="text-2xl font-bold">{{ selectedUser.messages_this_week || 0 }}</p>
            <p class="text-sm text-gray-600">This Week</p>
          </div>
        </div>
      </div>
      
      <!-- Recent Messages -->
      <div>
        <h3 class="text-lg font-medium mb-3">Recent Messages</h3>
        <div class="space-y-2 max-h-64 overflow-y-auto">
          <div
            v-for="message in selectedUser.recent_messages"
            :key="message.id"
            class="p-3 bg-gray-50 rounded"
          >
            <div class="flex justify-between items-start">
              <p class="text-sm">{{ message.content }}</p>
              <span
                :class="[
                  'text-xs px-2 py-1 rounded',
                  message.direction === 'inbound'
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-green-100 text-green-700'
                ]"
              >
                {{ message.direction }}
              </span>
            </div>
            <p class="text-xs text-gray-500 mt-1">
              {{ formatDate(message.created_at) }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </Modal>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useUserStore } from '@/stores/users'
import { debounce } from '@/utils/debounce'
import Modal from '@/components/Modal.vue'
import Pagination from '@/components/Pagination.vue'
import { formatDate } from '@/utils/format'

const userStore = useUserStore()

const searchQuery = ref('')
const filterStatus = ref('')
const currentPage = ref(1)
const perPage = ref(20)
const showUserDetails = ref(false)
const selectedUser = ref(null)

const users = computed(() => userStore.users)
const totalUsers = computed(() => userStore.total)

const debouncedSearch = debounce(() => {
  currentPage.value = 1
  loadUsers()
}, 300)

async function loadUsers() {
  await userStore.loadUsers({
    page: currentPage.value,
    per_page: perPage.value,
    search: searchQuery.value,
    status: filterStatus.value
  })
}

async function viewUserDetails(user) {
  selectedUser.value = await userStore.getUserDetails(user.id)
  showUserDetails.value = true
}

async function toggleUserStatus(user) {
  const newStatus = !user.is_active
  await userStore.updateUserStatus(user.id, newStatus)
  await loadUsers()
}

onMounted(() => {
  loadUsers()
})
</script>
```

### Step 5: Create System Logs Viewer
```vue
<!-- src/components/SystemLogs.vue -->
<template>
  <div class="bg-white rounded-lg shadow">
    <!-- Filters -->
    <div class="p-4 border-b">
      <div class="flex flex-wrap gap-4">
        <select
          v-model="logLevel"
          class="px-3 py-2 border rounded"
          @change="loadLogs"
        >
          <option value="">All Levels</option>
          <option value="debug">Debug</option>
          <option value="info">Info</option>
          <option value="warning">Warning</option>
          <option value="error">Error</option>
        </select>
        
        <select
          v-model="logSource"
          class="px-3 py-2 border rounded"
          @change="loadLogs"
        >
          <option value="">All Sources</option>
          <option value="webhook">Webhooks</option>
          <option value="agent">Agent Service</option>
          <option value="bridge">WhatsApp Bridge</option>
          <option value="auth">Authentication</option>
        </select>
        
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search logs..."
          class="px-3 py-2 border rounded flex-1"
          @input="debouncedSearch"
        />
        
        <button
          @click="isStreaming = !isStreaming"
          :class="[
            'px-4 py-2 rounded',
            isStreaming
              ? 'bg-green-600 text-white'
              : 'bg-gray-200 text-gray-700'
          ]"
        >
          {{ isStreaming ? 'Streaming' : 'Paused' }}
        </button>
      </div>
    </div>
    
    <!-- Logs Display -->
    <div
      ref="logsContainer"
      class="font-mono text-sm p-4 bg-gray-900 text-gray-100 h-96 overflow-y-auto"
    >
      <div
        v-for="log in logs"
        :key="log.id"
        :class="['py-1', getLogClass(log.level)]"
      >
        <span class="text-gray-500">{{ formatTimestamp(log.timestamp) }}</span>
        <span :class="getLevelClass(log.level)" class="mx-2">
          [{{ log.level.toUpperCase() }}]
        </span>
        <span class="text-blue-400">[{{ log.source }}]</span>
        <span class="ml-2">{{ log.message }}</span>
        
        <!-- Expandable details -->
        <div
          v-if="log.details"
          class="ml-8 mt-1 text-gray-400"
        >
          <pre class="text-xs">{{ JSON.stringify(log.details, null, 2) }}</pre>
        </div>
      </div>
      
      <!-- Auto-scroll anchor -->
      <div ref="scrollAnchor"></div>
    </div>
    
    <!-- Stats Bar -->
    <div class="p-2 border-t bg-gray-50 text-xs text-gray-600">
      <div class="flex justify-between">
        <span>{{ logs.length }} logs loaded</span>
        <span v-if="isStreaming">Live streaming enabled</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useLogsStore } from '@/stores/logs'
import { debounce } from '@/utils/debounce'

const logsStore = useLogsStore()

const logLevel = ref('')
const logSource = ref('')
const searchQuery = ref('')
const isStreaming = ref(true)
const logsContainer = ref(null)
const scrollAnchor = ref(null)

const logs = computed(() => logsStore.logs)

const debouncedSearch = debounce(() => {
  loadLogs()
}, 300)

async function loadLogs() {
  await logsStore.loadLogs({
    level: logLevel.value,
    source: logSource.value,
    search: searchQuery.value
  })
}

// Auto-scroll to bottom when new logs arrive
watch(logs, async () => {
  if (isStreaming.value) {
    await nextTick()
    scrollAnchor.value?.scrollIntoView({ behavior: 'smooth' })
  }
})

// WebSocket for real-time logs
let ws
function connectWebSocket() {
  ws = new WebSocket(`${import.meta.env.VITE_WS_URL}/logs`)
  
  ws.onmessage = (event) => {
    if (isStreaming.value) {
      const log = JSON.parse(event.data)
      logsStore.addLog(log)
    }
  }
  
  ws.onerror = () => {
    setTimeout(connectWebSocket, 5000) // Reconnect after 5s
  }
}

onMounted(() => {
  loadLogs()
  connectWebSocket()
})

onUnmounted(() => {
  ws?.close()
})

function formatTimestamp(timestamp) {
  return new Date(timestamp).toLocaleTimeString()
}

function getLogClass(level) {
  const classes = {
    debug: 'text-gray-400',
    info: 'text-gray-100',
    warning: 'text-yellow-400',
    error: 'text-red-400'
  }
  return classes[level] || ''
}

function getLevelClass(level) {
  const classes = {
    debug: 'text-gray-500',
    info: 'text-blue-500',
    warning: 'text-yellow-500',
    error: 'text-red-500'
  }
  return classes[level] || ''
}
</script>
```

### Step 6: Create Admin Dashboard Layout
```vue
<!-- src/layouts/AdminLayout.vue -->
<template>
  <div class="min-h-screen bg-gray-100">
    <!-- Sidebar -->
    <div class="fixed inset-y-0 left-0 w-64 bg-gray-900">
      <div class="flex items-center h-16 px-4 bg-gray-800">
        <h1 class="text-xl font-bold text-white">Zapa Admin</h1>
      </div>
      
      <nav class="mt-8">
        <RouterLink
          v-for="item in navigation"
          :key="item.name"
          :to="item.to"
          :class="[
            'flex items-center px-4 py-3 text-gray-300 hover:bg-gray-800 hover:text-white',
            $route.path === item.to && 'bg-gray-800 text-white'
          ]"
        >
          <component :is="item.icon" class="w-5 h-5 mr-3" />
          {{ item.name }}
        </RouterLink>
      </nav>
      
      <!-- Admin Info -->
      <div class="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-800">
        <div class="text-sm text-gray-400">
          <p>{{ adminUsername }}</p>
          <p class="text-xs">{{ adminRole }}</p>
        </div>
        <button
          @click="logout"
          class="mt-2 text-xs text-gray-500 hover:text-gray-300"
        >
          Logout
        </button>
      </div>
    </div>
    
    <!-- Main Content -->
    <div class="ml-64">
      <!-- Header -->
      <header class="bg-white shadow">
        <div class="px-8 py-4">
          <h2 class="text-2xl font-semibold text-gray-900">
            {{ currentPageTitle }}
          </h2>
        </div>
      </header>
      
      <!-- Page Content -->
      <main class="p-8">
        <RouterView />
      </main>
    </div>
    
    <!-- Notifications -->
    <NotificationContainer />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAdminAuthStore } from '@/stores/adminAuth'
import {
  HomeIcon,
  UsersIcon,
  ChatBubbleLeftRightIcon,
  CogIcon,
  ChartBarIcon,
  DocumentTextIcon
} from '@heroicons/vue/24/outline'
import NotificationContainer from '@/components/NotificationContainer.vue'

const route = useRoute()
const adminAuthStore = useAdminAuthStore()

const navigation = [
  { name: 'Dashboard', to: '/dashboard', icon: HomeIcon },
  { name: 'Users', to: '/users', icon: UsersIcon },
  { name: 'Sessions', to: '/sessions', icon: ChatBubbleLeftRightIcon },
  { name: 'Analytics', to: '/analytics', icon: ChartBarIcon },
  { name: 'Logs', to: '/logs', icon: DocumentTextIcon },
  { name: 'Settings', to: '/settings', icon: CogIcon }
]

const currentPageTitle = computed(() => {
  const item = navigation.find(n => n.to === route.path)
  return item?.name || 'Admin Panel'
})

const adminUsername = computed(() => adminAuthStore.admin?.username || '')
const adminRole = computed(() => adminAuthStore.admin?.role || '')

function logout() {
  adminAuthStore.logout()
}
</script>
```

## Testing Strategy

### Unit Tests
```javascript
// tests/unit/stores/adminAuth.test.js
import { setActivePinia, createPinia } from 'pinia'
import { useAdminAuthStore } from '@/stores/adminAuth'
import { vi } from 'vitest'

describe('Admin Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })
  
  it('should login admin successfully', async () => {
    const store = useAdminAuthStore()
    const mockApi = vi.fn().mockResolvedValue({
      access_token: 'admin_token',
      admin_id: 1,
      username: 'admin',
      role: 'super'
    })
    
    // Mock the API
    vi.mock('@/api/admin', () => ({
      default: { login: mockApi }
    }))
    
    const result = await store.login('admin', 'password')
    
    expect(result.success).toBe(true)
    expect(store.token).toBe('admin_token')
    expect(store.admin.role).toBe('super')
    expect(store.isSuper).toBe(true)
  })
})
```

### E2E Tests
```javascript
// tests/e2e/admin-dashboard.spec.js
import { test, expect } from '@playwright/test'

test.describe('Admin Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // Login as admin
    await page.goto('/login')
    await page.fill('input[name="username"]', 'admin')
    await page.fill('input[name="password"]', 'admin123')
    await page.click('button[type="submit"]')
    await page.waitForURL('/dashboard')
  })
  
  test('should display system health', async ({ page }) => {
    await expect(page.locator('h3:has-text("WhatsApp Bridge")')).toBeVisible()
    await expect(page.locator('h3:has-text("Message Queue")')).toBeVisible()
    
    // Check for health status indicators
    const healthCards = page.locator('[class*="border-l-4"]')
    await expect(healthCards).toHaveCount(4)
  })
  
  test('should navigate to users page', async ({ page }) => {
    await page.click('a:has-text("Users")')
    await page.waitForURL('/users')
    
    // Should show users table
    await expect(page.locator('table')).toBeVisible()
    await expect(page.locator('th:has-text("Phone Number")')).toBeVisible()
  })
  
  test('should stream logs in real-time', async ({ page }) => {
    await page.goto('/logs')
    
    // Check streaming is enabled
    await expect(page.locator('button:has-text("Streaming")')).toHaveClass(/bg-green-600/)
    
    // Logs should be visible
    await expect(page.locator('.font-mono')).toBeVisible()
  })
})
```

## Implementation Notes

1. **Real-time Updates**: WebSocket for logs, polling for health metrics
2. **Role-Based Access**: Super admins can manage other admins
3. **Performance**: Virtual scrolling for large datasets
4. **Security**: JWT auth with role checking
5. **Monitoring**: Comprehensive health checks and metrics
6. **UX**: Responsive design, keyboard shortcuts, notifications

## Dependencies
- Vue 3 + Composition API
- Vue Router for navigation
- Pinia for state management
- Chart.js for visualizations
- Tailwind CSS for styling
- Heroicons for icons
- WebSocket for real-time updates

## Next Steps
- Task 16: Integration Testing
- Task 17: Performance Optimization