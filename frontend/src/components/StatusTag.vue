<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ value: string }>()
const type = computed(() => ({ VALID: 'success', CONFIRMED: 'success', ENABLED: 'success', ACTIVE: 'success', SUCCESS: 'success', REVOKED: 'danger', FAILED: 'danger', TAMPERED: 'danger', PENDING: 'warning', PROCESSING: 'warning', DRAFT: 'info', GENERATED: 'warning', EVIDENCED: 'success', REISSUED: 'warning', EXPIRED: 'info', IMPORTED: 'warning', CANCELLED: 'info' }[props.value] || 'info'))
const labels: Record<string, string> = { VALID: '有效', CONFIRMED: '已确认', ENABLED: '启用', ACTIVE: '进行中', SUCCESS: '成功', REVOKED: '已撤销', FAILED: '失败', TAMPERED: '疑似篡改', PENDING: '待处理', PROCESSING: '处理中', COMPLETED: '已完成', DRAFT: '草稿', GENERATED: '已生成', EVIDENCED: '已存证', REISSUED: '已补发', EXPIRED: '已过期', IMPORTED: '已导入', CANCELLED: '已取消' }
</script>
<template><el-tag :type="type as any" effect="light" round>{{ labels[value] || value }}</el-tag></template>
