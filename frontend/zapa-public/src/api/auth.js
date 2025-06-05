import apiClient from './client'

export default {
  requestCode(phoneNumber) {
    return apiClient.post('/auth/request-code', {
      phone_number: phoneNumber
    })
  },

  verifyCode(phoneNumber, code) {
    return apiClient.post('/auth/verify', {
      phone_number: phoneNumber,
      code: code
    })
  },

  getCurrentUser() {
    return apiClient.get('/auth/me')
  },

  setAuthToken(token) {
    apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`
  },

  clearAuthToken() {
    delete apiClient.defaults.headers.common['Authorization']
  }
}