import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { UserInfo } from '@/types'
import { loginApi } from '@/api/auth'

const TOKEN_KEY = 'certificate_admin_token'
const USER_KEY = 'certificate_admin_user'

function loadStoredUser(): UserInfo | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    const value = JSON.parse(raw) as Partial<UserInfo>
    if (!value.username || !value.displayName || !['ADMIN', 'TEACHER', 'AUDITOR'].includes(String(value.role))) {
      throw new Error('invalid stored user')
    }
    return value as UserInfo
  } catch {
    localStorage.removeItem(USER_KEY)
    localStorage.removeItem(TOKEN_KEY)
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserInfo | null>(loadStoredUser())
  const token = ref(user.value ? (localStorage.getItem(TOKEN_KEY) || '') : '')
  const isLoggedIn = computed(() => Boolean(token.value && user.value))
  const isAdmin = computed(() => user.value?.role === 'ADMIN')

  async function login(username: string, password: string) {
    const result = await loginApi(username, password)
    token.value = result.token
    user.value = result.user
    localStorage.setItem(TOKEN_KEY, token.value)
    localStorage.setItem(USER_KEY, JSON.stringify(user.value))
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  return { token, user, isLoggedIn, isAdmin, login, logout }
})