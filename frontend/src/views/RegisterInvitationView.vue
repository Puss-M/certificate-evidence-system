<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { roleHome } from '@/router'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const token = ref(new URLSearchParams(window.location.hash.slice(1)).get('token') || '')
if (window.location.hash) window.history.replaceState(null, document.title, route.path)
const form = reactive({ username: '', displayName: '', password: '', passwordConfirm: '' })

async function submit() {
  if (!token.value) return ElMessage.error('邀请链接缺少邀请码')
  if (form.password !== form.passwordConfirm) return ElMessage.warning('两次输入的密码不一致')
  loading.value = true
  try {
    await auth.registerFromInvitation({ invitationToken: token.value, username: form.username, displayName: form.displayName, password: form.password })
    ElMessage.success('注册成功')
    router.replace(roleHome(auth.user?.role))
  } catch (error) {
    if (!(error as { __messageShown?: boolean })?.__messageShown) ElMessage.error(error instanceof Error ? error.message : '注册失败')
  } finally { loading.value = false }
}
</script>

<template>
  <main class="login-page">
    <section class="login-hero"><div class="hero-content"><span class="eyebrow">TEAM INVITATION</span><h1>加入可信证书<br />协作管理平台</h1><p>邀请码仅供项目组成员使用。注册后可按教师角色处理模拟证书业务。</p></div></section>
    <section class="login-panel"><div class="login-box"><div class="mobile-brand">可信证书管理平台</div><h2>受邀教师注册</h2><p v-if="token">邀请码已识别，请设置协作账号。</p><p v-else>请从管理员发送的完整邀请链接进入。</p><el-form label-position="top" @keyup.enter="submit"><el-form-item label="显示名称"><el-input v-model="form.displayName" size="large" maxlength="64" /></el-form-item><el-form-item label="用户名"><el-input v-model="form.username" size="large" autocomplete="username" placeholder="字母、数字、点、下划线或连字符" /></el-form-item><el-form-item label="密码"><el-input v-model="form.password" type="password" size="large" show-password autocomplete="new-password" placeholder="至少 12 位" /></el-form-item><el-form-item label="确认密码"><el-input v-model="form.passwordConfirm" type="password" size="large" show-password autocomplete="new-password" /></el-form-item><el-button type="primary" size="large" :disabled="!token" :loading="loading" class="login-button" @click="submit">完成注册</el-button></el-form></div></section>
  </main>
</template>
