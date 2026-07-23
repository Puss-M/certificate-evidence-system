<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const loading = ref(false)
const form = reactive({ currentPassword: '', newPassword: '', confirmPassword: '' })
async function submit() {
  if (form.newPassword.length < 12) return ElMessage.warning('新密码至少需要 12 位')
  if (form.newPassword !== form.confirmPassword) return ElMessage.warning('两次输入的新密码不一致')
  loading.value = true
  try { await auth.changePassword(form.currentPassword, form.newPassword); ElMessage.success('密码已更新'); router.replace('/student') } finally { loading.value = false }
}
</script>
<template><main class="password-page"><section class="password-box"><p class="eyebrow">首次登录</p><h1>设置新的登录密码</h1><p>为保护你的证书下载和二维码，请先修改管理员发放的初始密码。</p><el-form label-position="top" @keyup.enter="submit"><el-form-item label="当前初始密码"><el-input v-model="form.currentPassword" type="password" show-password autocomplete="current-password"/></el-form-item><el-form-item label="新密码"><el-input v-model="form.newPassword" type="password" show-password autocomplete="new-password"/></el-form-item><el-form-item label="确认新密码"><el-input v-model="form.confirmPassword" type="password" show-password autocomplete="new-password"/></el-form-item><el-button type="primary" :loading="loading" @click="submit">保存并进入学生中心</el-button></el-form></section></main></template>
<style scoped>.password-page{min-height:100vh;display:grid;place-items:center;background:#f4f7fb;padding:24px}.password-box{width:min(100%,440px);background:#fff;border:1px solid #e7edf5;border-radius:12px;padding:34px;box-shadow:0 18px 48px rgba(30,41,59,.08)}.eyebrow{color:#2563eb;font-weight:700;margin:0 0 10px}.password-box h1{margin:0 0 12px}.password-box>p:not(.eyebrow){color:#64748b;line-height:1.7;margin-bottom:24px}.password-box .el-button{width:100%}</style>
