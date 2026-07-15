<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
const router = useRouter()
const auth = useAuthStore()
function goHome() {
  const role = auth.user?.role
  router.replace(role === 'TEACHER' ? '/projects' : role === 'AUDITOR' ? '/chain' : '/dashboard')
}
defineProps<{
  code: string
  text: string
}>()
</script>
<template><main class="error-page"><strong>{{code}}</strong><h1>{{text}}</h1><el-button type="primary" @click="goHome">返回首页</el-button></main></template>
