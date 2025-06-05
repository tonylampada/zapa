import { defineStore } from 'pinia'
import { ref } from 'vue'
import messagesApi from '@/api/messages'
import { useLLMStore } from './llm'

export const useStatsStore = defineStore('stats', () => {
  const stats = ref({
    total_messages: 0,
    messages_sent: 0,
    messages_received: 0,
    this_week: 0,
    provider: null
  })
  
  async function loadStats() {
    try {
      // Load message stats
      const messageStats = await messagesApi.getStats()
      
      // Calculate this week's messages
      const thisWeek = calculateThisWeekMessages(messageStats)
      
      // Get LLM provider
      const llmStore = useLLMStore()
      await llmStore.loadConfiguration()
      
      stats.value = {
        total_messages: messageStats.total_messages,
        messages_sent: messageStats.messages_sent,
        messages_received: messageStats.messages_received,
        this_week: thisWeek,
        provider: llmStore.currentConfig?.provider || null
      }
      
      return stats.value
    } catch (error) {
      console.error('Failed to load stats:', error)
      return stats.value
    }
  }
  
  function calculateThisWeekMessages(messageStats) {
    // Simple calculation - in production would use actual date filtering
    if (!messageStats.average_messages_per_day) return 0
    return Math.round(messageStats.average_messages_per_day * 7)
  }
  
  return {
    stats,
    loadStats
  }
})