<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { canRoleAccessPath, roleHome } from '@/router'
import { ElMessage } from 'element-plus'

const form = reactive({ username: '', password: '' })
const loading = ref(false)
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
async function submit() {
  if (!form.username || !form.password) return ElMessage.warning('请输入用户名和密码')
  loading.value = true
  try { await auth.login(form.username, form.password); ElMessage.success('登录成功'); const home=roleHome(auth.user?.role);const redirect=typeof route.query.redirect==='string'?route.query.redirect:'';router.replace(canRoleAccessPath(redirect,auth.user?.role)?redirect:home) }
  catch (e) { if (!(e as { __messageShown?: boolean })?.__messageShown) ElMessage.error(e instanceof Error ? e.message : '登录失败') }
  finally { loading.value = false }
}
</script>
<template>
  <main class="login-page">
    <section class="login-hero"><div class="hero-content"><span class="eyebrow">BLOCKCHAIN CREDENTIAL NETWORK</span><h1>让每一份学习成果<br />都可信、可验、可追溯</h1><p>通过本地哈希链存证、文件哈希校验与完整审计，为实训证书和学业证明建立可信数字底座。</p><div class="trust-row"><div><b>SHA-256</b><span>文件指纹</span></div><div><b>哈希链</b><span>存证回执</span></div><div><b>全流程</b><span>审计追溯</span></div></div></div></section>
    <section class="login-panel"><div class="login-box"><div class="mobile-brand">可信证书管理平台</div><h2>管理端登录</h2><p>登录后管理证书签发与可信存证</p><el-form label-position="top" @keyup.enter="submit"><el-form-item label="用户名"><el-input v-model="form.username" size="large" autocomplete="username" placeholder="请输入用户名" /></el-form-item><el-form-item label="密码"><el-input v-model="form.password" type="password" size="large" show-password autocomplete="current-password" placeholder="请输入密码" /></el-form-item><el-button type="primary" size="large" :loading="loading" class="login-button" @click="submit">进入管理后台</el-button></el-form><div class="demo-tip">受邀教师请使用管理员发送的注册链接完成注册。</div></div></section>
  </main>
</template>
