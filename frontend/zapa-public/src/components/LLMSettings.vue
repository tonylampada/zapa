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
          class="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
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
          class="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
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
              class="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
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
              class="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>
          
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Custom Instructions (Optional)
            </label>
            <textarea
              v-model="customInstructions"
              rows="3"
              placeholder="Add any special instructions for your AI assistant..."
              class="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>
        </div>
      </details>
      
      <!-- Actions -->
      <div class="flex space-x-4">
        <button
          type="submit"
          :disabled="saving || !selectedProvider || !apiKey"
          class="flex-1 py-2 px-4 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ saving ? 'Saving...' : 'Save Settings' }}
        </button>
        
        <button
          v-if="hasExistingConfig"
          type="button"
          @click="testConnection"
          :disabled="testing"
          class="py-2 px-4 border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
        >
          {{ testing ? 'Testing...' : 'Test Connection' }}
        </button>
        
        <button
          v-if="hasExistingConfig"
          type="button"
          @click="deleteConfig"
          class="py-2 px-4 border border-red-300 text-red-600 rounded-md hover:bg-red-50"
        >
          Delete
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
const customInstructions = ref('')
const saving = ref(false)
const testing = ref(false)
const statusMessage = ref(null)

const providers = ref([])

const availableModels = computed(() => {
  const provider = providers.value.find(p => p.value === selectedProvider.value)
  return provider?.models || []
})

const hasExistingConfig = computed(() => 
  llmStore.currentConfig !== null
)

// Load providers and existing configuration
onMounted(async () => {
  // Load available providers
  await llmStore.loadProviders()
  providers.value = llmStore.providers
  
  // Load existing configuration
  await llmStore.loadConfiguration()
  
  if (llmStore.currentConfig) {
    selectedProvider.value = llmStore.currentConfig.provider
    selectedModel.value = llmStore.currentConfig.model_settings.model
    temperature.value = llmStore.currentConfig.model_settings.temperature || 0.7
    maxTokens.value = llmStore.currentConfig.model_settings.max_tokens || 1000
    customInstructions.value = llmStore.currentConfig.model_settings.custom_instructions || ''
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
      max_tokens: maxTokens.value,
      custom_instructions: customInstructions.value
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
    
    // Clear message after 3 seconds
    setTimeout(() => {
      statusMessage.value = null
    }, 3000)
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
    text: result.message + (result.response_time_ms ? ` (${result.response_time_ms}ms)` : '')
  }
  
  testing.value = false
  
  // Clear message after 5 seconds
  setTimeout(() => {
    statusMessage.value = null
  }, 5000)
}

async function deleteConfig() {
  if (!confirm('Are you sure you want to delete your AI configuration?')) {
    return
  }
  
  const result = await llmStore.deleteConfiguration()
  
  if (result.success) {
    // Reset form
    selectedProvider.value = ''
    apiKey.value = ''
    selectedModel.value = ''
    temperature.value = 0.7
    maxTokens.value = 1000
    customInstructions.value = ''
    
    statusMessage.value = {
      type: 'success',
      text: 'Configuration deleted successfully'
    }
  } else {
    statusMessage.value = {
      type: 'error',
      text: result.message
    }
  }
}
</script>