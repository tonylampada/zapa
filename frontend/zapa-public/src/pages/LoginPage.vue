<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50 px-4">
    <div class="max-w-md w-full space-y-8">
      <div class="text-center">
        <h2 class="text-3xl font-bold text-gray-900">
          Sign in to Zapa
        </h2>
        <p class="mt-2 text-gray-600">
          Enter your WhatsApp number to receive a verification code
        </p>
      </div>
      
      <form @submit.prevent="handleSubmit" class="mt-8 space-y-6">
        <!-- Phone Input Step -->
        <div v-if="!codeSent" class="space-y-4">
          <div>
            <label for="phone" class="block text-sm font-medium text-gray-700">
              WhatsApp Phone Number
            </label>
            <input
              id="phone"
              v-model="phoneNumber"
              type="tel"
              required
              placeholder="+1234567890"
              class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-green-500 focus:border-green-500"
              :disabled="loading"
            />
            <p v-if="phoneError" class="mt-1 text-sm text-red-600">
              {{ phoneError }}
            </p>
          </div>
          
          <button
            type="submit"
            :disabled="loading || !phoneNumber"
            class="w-full py-2 px-4 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ loading ? 'Sending...' : 'Send Code' }}
          </button>
        </div>
        
        <!-- Code Input Step -->
        <div v-else class="space-y-4">
          <div>
            <label for="code" class="block text-sm font-medium text-gray-700">
              Verification Code
            </label>
            <input
              id="code"
              v-model="verificationCode"
              type="text"
              required
              placeholder="123456"
              maxlength="6"
              class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-center text-2xl tracking-widest focus:outline-none focus:ring-green-500 focus:border-green-500"
              :disabled="loading"
              @input="handleCodeInput"
            />
            <p class="mt-1 text-sm text-gray-600">
              Code sent to {{ phoneNumber }}
            </p>
            <p v-if="codeError" class="mt-1 text-sm text-red-600">
              {{ codeError }}
            </p>
          </div>
          
          <button
            type="submit"
            :disabled="loading || verificationCode.length !== 6"
            class="w-full py-2 px-4 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ loading ? 'Verifying...' : 'Verify' }}
          </button>
          
          <button
            type="button"
            @click="resetForm"
            class="w-full py-2 px-4 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
          >
            Change Number
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const phoneNumber = ref('')
const verificationCode = ref('')
const codeSent = ref(false)
const loading = ref(false)
const phoneError = ref('')
const codeError = ref('')

async function handleSubmit() {
  if (!codeSent.value) {
    await sendCode()
  } else {
    await verifyCode()
  }
}

async function sendCode() {
  loading.value = true
  phoneError.value = ''
  
  const result = await authStore.requestCode(phoneNumber.value)
  
  if (result.success) {
    codeSent.value = true
  } else {
    phoneError.value = result.message
  }
  
  loading.value = false
}

async function verifyCode() {
  loading.value = true
  codeError.value = ''
  
  const result = await authStore.verifyCode(
    phoneNumber.value,
    verificationCode.value
  )
  
  if (result.success) {
    router.push('/dashboard')
  } else {
    codeError.value = result.message
  }
  
  loading.value = false
}

function handleCodeInput(event) {
  // Only allow digits
  event.target.value = event.target.value.replace(/\D/g, '')
  verificationCode.value = event.target.value
}

function resetForm() {
  codeSent.value = false
  verificationCode.value = ''
  codeError.value = ''
}
</script>