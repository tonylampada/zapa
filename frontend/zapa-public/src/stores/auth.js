import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import authApi from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('auth_token'))
  const user = ref(null)
  const router = useRouter()
  
  const isAuthenticated = computed(() => !!token.value)
  
  async function requestCode(phoneNumber) {
    try {
      const response = await authApi.requestCode(phoneNumber)
      return { success: true, message: response.message }
    } catch (error) {
      return { 
        success: false, 
        message: error.response?.data?.detail || 'Failed to send code' 
      }
    }
  }
  
  async function verifyCode(phoneNumber, code) {
    try {
      const response = await authApi.verifyCode(phoneNumber, code)
      
      // Store token
      token.value = response.access_token
      localStorage.setItem('auth_token', response.access_token)
      
      // Store user info
      user.value = {
        id: response.user_id,
        phoneNumber: response.phone_number
      }
      
      // Configure axios defaults
      authApi.setAuthToken(response.access_token)
      
      return { success: true }
    } catch (error) {
      return { 
        success: false, 
        message: error.response?.data?.detail || 'Invalid code' 
      }
    }
  }
  
  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('auth_token')
    authApi.clearAuthToken()
    router.push('/login')
  }
  
  // Initialize auth if token exists
  if (token.value) {
    authApi.setAuthToken(token.value)
    // Could verify token validity here
  }
  
  return {
    token,
    user,
    isAuthenticated,
    requestCode,
    verifyCode,
    logout
  }
})