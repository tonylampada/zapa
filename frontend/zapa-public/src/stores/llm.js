import { defineStore } from 'pinia'
import { ref } from 'vue'
import llmApi from '@/api/llm'

export const useLLMStore = defineStore('llm', () => {
  const currentConfig = ref(null)
  const providers = ref([])
  
  async function loadConfiguration() {
    try {
      const config = await llmApi.getConfig()
      currentConfig.value = config
      return config
    } catch (error) {
      if (error.response?.status === 404) {
        currentConfig.value = null
        return null
      }
      throw error
    }
  }
  
  async function loadProviders() {
    try {
      const response = await llmApi.getProviders()
      providers.value = response
      return response
    } catch (error) {
      console.error('Failed to load providers:', error)
      return []
    }
  }
  
  async function saveConfiguration(config) {
    try {
      const response = await llmApi.saveConfig(config)
      currentConfig.value = response
      return { success: true, data: response }
    } catch (error) {
      return { 
        success: false, 
        message: error.response?.data?.detail || 'Failed to save configuration' 
      }
    }
  }
  
  async function testConfiguration() {
    try {
      const response = await llmApi.testConfig()
      return { success: true, ...response }
    } catch (error) {
      return { 
        success: false, 
        message: error.response?.data?.detail || 'Failed to test configuration' 
      }
    }
  }
  
  async function deleteConfiguration() {
    try {
      await llmApi.deleteConfig()
      currentConfig.value = null
      return { success: true }
    } catch (error) {
      return { 
        success: false, 
        message: error.response?.data?.detail || 'Failed to delete configuration' 
      }
    }
  }
  
  return {
    currentConfig,
    providers,
    loadConfiguration,
    loadProviders,
    saveConfiguration,
    testConfiguration,
    deleteConfiguration
  }
})