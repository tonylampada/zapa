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
                <dt class="text-gray-600">Messages Sent</dt>
                <dd class="font-medium">{{ stats.messages_sent }}</dd>
              </div>
              <div class="flex justify-between">
                <dt class="text-gray-600">Messages Received</dt>
                <dd class="font-medium">{{ stats.messages_received }}</dd>
              </div>
              <div class="flex justify-between">
                <dt class="text-gray-600">AI Provider</dt>
                <dd class="font-medium capitalize">{{ stats.provider || 'Not configured' }}</dd>
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
                :disabled="exporting"
                class="w-full py-2 px-4 border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
              >
                {{ exporting ? 'Exporting...' : 'Export as JSON' }}
              </button>
              <button
                @click="exportMessages('csv')"
                :disabled="exporting"
                class="w-full py-2 px-4 border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
              >
                {{ exporting ? 'Exporting...' : 'Export as CSV' }}
              </button>
            </div>
            <p v-if="exportError" class="mt-2 text-sm text-red-600">
              {{ exportError }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useMessagesStore } from '@/stores/messages'
import { useStatsStore } from '@/stores/stats'
import MessageHistory from '@/components/MessageHistory.vue'
import LLMSettings from '@/components/LLMSettings.vue'

const router = useRouter()
const authStore = useAuthStore()
const messagesStore = useMessagesStore()
const statsStore = useStatsStore()

const exporting = ref(false)
const exportError = ref('')

const userPhone = computed(() => authStore.user?.phoneNumber || '')
const stats = computed(() => statsStore.stats)

onMounted(() => {
  statsStore.loadStats()
})

function logout() {
  authStore.logout()
  router.push('/login')
}

async function exportMessages(format) {
  exporting.value = true
  exportError.value = ''
  
  try {
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
  } catch (error) {
    exportError.value = 'Failed to export messages. Please try again.'
    console.error('Export error:', error)
  } finally {
    exporting.value = false
  }
}
</script>