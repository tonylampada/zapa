import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import messagesApi from '@/api/messages'

export const useMessagesStore = defineStore('messages', () => {
  const messages = ref([])
  const loading = ref(false)
  const hasMore = ref(true)
  const currentSkip = ref(0)
  const searchQuery = ref('')
  
  async function loadMessages(reset = false) {
    if (loading.value) return
    
    loading.value = true
    
    try {
      if (reset) {
        currentSkip.value = 0
        messages.value = []
        hasMore.value = true
      }
      
      const params = {
        skip: currentSkip.value,
        limit: 50
      }
      
      if (searchQuery.value) {
        params.search = searchQuery.value
      }
      
      const response = await messagesApi.getMessages(params)
      
      if (response.length < 50) {
        hasMore.value = false
      }
      
      if (reset) {
        messages.value = response
      } else {
        messages.value.push(...response)
      }
      
      currentSkip.value += response.length
    } catch (error) {
      console.error('Failed to load messages:', error)
    } finally {
      loading.value = false
    }
  }
  
  async function loadMore() {
    if (!hasMore.value || loading.value) return
    await loadMessages(false)
  }
  
  async function refreshLatest() {
    try {
      const recent = await messagesApi.getRecentMessages(10)
      
      // Merge new messages, avoiding duplicates
      const existingIds = new Set(messages.value.map(m => m.id))
      const newMessages = recent.filter(m => !existingIds.has(m.id))
      
      if (newMessages.length > 0) {
        messages.value.unshift(...newMessages)
      }
    } catch (error) {
      console.error('Failed to refresh messages:', error)
    }
  }
  
  async function searchMessages(query) {
    searchQuery.value = query
    await loadMessages(true)
  }
  
  async function exportMessages(format) {
    try {
      const response = await messagesApi.exportMessages(format)
      
      if (format === 'json') {
        return JSON.stringify(response.data, null, 2)
      } else {
        return response.data
      }
    } catch (error) {
      console.error('Failed to export messages:', error)
      throw error
    }
  }
  
  return {
    messages,
    loading,
    hasMore,
    searchQuery,
    loadMessages,
    loadMore,
    refreshLatest,
    searchMessages,
    exportMessages
  }
})