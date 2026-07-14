<script setup lang="ts">
defineProps<{
  code: string
  text: string
}>()
</script>
<template><main class="error-page"><strong>{{code}}</strong><h1>{{text}}</h1><el-button type="primary" @click="$router.push('/dashboard')">返回首页</el-button></main></template>
