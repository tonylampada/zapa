import apiClient from './client'

export default {
  getConfig() {
    return apiClient.get('/llm-config/')
  },

  saveConfig(config) {
    return apiClient.post('/llm-config/', config)
  },

  testConfig() {
    return apiClient.post('/llm-config/test')
  },

  deleteConfig() {
    return apiClient.delete('/llm-config/')
  },

  getProviders() {
    return apiClient.get('/llm-config/providers')
  }
}