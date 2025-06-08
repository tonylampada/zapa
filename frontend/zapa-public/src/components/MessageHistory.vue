<template>
  <div class="flex flex-col h-full">
    <!-- Search Bar -->
    <div class="p-4 border-b">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="Search messages..."
        class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
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
          message.direction === 'outgoing' ? 'justify-end' : 'justify-start'
        ]"
      >
        <div
          :class="[
            'max-w-xs lg:max-w-md px-4 py-2 rounded-lg',
            message.direction === 'outgoing' 
              ? 'bg-green-500 text-white' 
              : 'bg-gray-200 text-gray-900'
          ]"
        >
          <p class="text-sm whitespace-pre-wrap">{{ message.content }}</p>
          <p 
            :class="[
              'text-xs mt-1',
              message.direction === 'outgoing' ? 'text-green-100' : 'text-gray-500'
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
      
      <!-- Empty state -->
      <div v-if="!loading && messages.length === 0" class="text-center py-8">
        <p class="text-gray-500">No messages yet. Start a conversation on WhatsApp!</p>
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
  const date = new Date(timestamp)
  return date.toLocaleTimeString('en-US', { 
    hour: 'numeric', 
    minute: '2-digit',
    hour12: true 
  })
}

function formatDate(timestamp) {
  const date = new Date(timestamp)
  return date.toLocaleDateString('en-US', { 
    month: 'short', 
    day: 'numeric', 
    year: 'numeric' 
  })
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