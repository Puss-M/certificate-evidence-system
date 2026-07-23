<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import { createTeacherInvitation, getManagedUsers, updateManagedUserStatus, type ManagedUser } from '@/api/auth'

const users = ref<ManagedUser[]>([])
const loading = ref(false)
const inviteHours = ref(48)
const invitationUrl = ref('')

async function load() {
  loading.value = true
  try { users.value = await getManagedUsers() } finally { loading.value = false }
}

async function createInvite() {
  const invitation = await createTeacherInvitation(inviteHours.value)
  invitationUrl.value = `${window.location.origin}/register#token=${encodeURIComponent(invitation.invitationToken)}`
  ElMessage.success(`教师邀请已创建，有效至 ${new Date(invitation.expiresAt).toLocaleString()}`)
}

async function copyInvitation() {
  try { await navigator.clipboard.writeText(invitationUrl.value); ElMessage.success('邀请链接已复制') }
  catch { ElMessage.info('请手动复制邀请链接') }
}

async function toggleUser(row: ManagedUser) {
  if (row.role === 'ADMIN') return ElMessage.warning('管理员账号不能在此页面禁用')
  const updated = await updateManagedUserStatus(row.userId, !row.isActive)
  const index = users.value.findIndex(item => item.userId === updated.userId)
  if (index >= 0) users.value[index] = updated
  ElMessage.success(updated.isActive ? '账号已启用' : '账号已禁用，现有登录已失效')
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <PageHeader title="协作账号" description="仅管理员可创建教师邀请和管理团队协作账号。" />
    <section class="panel"><div class="panel-title"><div><h3>创建教师邀请</h3><p>邀请码只能使用一次，管理员应通过可信渠道发送链接。</p></div></div><div class="inline-form"><el-input-number v-model="inviteHours" :min="1" :max="168" /><span>小时后过期</span><el-button type="primary" @click="createInvite">创建邀请</el-button></div><el-input v-if="invitationUrl" v-model="invitationUrl" readonly class="invitation-url"><template #append><el-button @click="copyInvitation">复制</el-button></template></el-input></section>
    <section class="panel"><div class="panel-title"><div><h3>账号列表</h3><p>禁用账号会同时撤销其所有有效登录。</p></div><el-button @click="load">刷新</el-button></div><el-table :data="users" empty-text="暂无账号"><el-table-column prop="displayName" label="名称" min-width="130"/><el-table-column prop="username" label="用户名" min-width="150"/><el-table-column prop="role" label="角色" width="120"/><el-table-column label="状态" width="110"><template #default="scope"><el-tag :type="scope.row.isActive ? 'success' : 'info'">{{ scope.row.isActive ? '启用' : '禁用' }}</el-tag></template></el-table-column><el-table-column prop="createdAt" label="创建时间" min-width="180"/><el-table-column label="操作" width="120"><template #default="scope"><el-button v-if="scope.row.role !== 'ADMIN'" text :type="scope.row.isActive ? 'danger' : 'primary'" @click="toggleUser(scope.row)">{{ scope.row.isActive ? '禁用' : '启用' }}</el-button></template></el-table-column></el-table></section>
  </div>
</template>

<style scoped>
.inline-form { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.invitation-url { margin-top: 16px; }
</style>
