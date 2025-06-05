import apiClient from './client'

export default {
  getMessages(params = {}) {
    return apiClient.get('/messages/', { params })
  },

  getRecentMessages(count = 10) {
    return apiClient.get('/messages/recent', { params: { count } })
  },

  searchMessages(query, params = {}) {
    return apiClient.get('/messages/search', {
      params: { query, ...params }
    })
  },

  getStats() {
    return apiClient.get('/messages/stats')
  },

  exportMessages(format = 'json') {
    return apiClient.get('/messages/export', { params: { format } })
  }
}