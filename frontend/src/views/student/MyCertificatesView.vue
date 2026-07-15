<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import type { Certificate } from '@/types'
import { getMyCertificates, getSavedStudentNo } from '@/api/studentCertificates'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const studentNo = ref(String(route.query.student_no || getSavedStudentNo()))
const rows = ref<Certificate[]>([])

async function load() {
  if (!studentNo.value) return ElMessage.warning('请输入学号')
  loading.value = true
  try {
    rows.value = await getMyCertificates(studentNo.value)
  } catch {
    rows.value = []
  } finally {
    loading.value = false
  }
}

function openDetail(row: Certificate) {
  router.push({ path: `/student/certificates/${row.certificate_no}`, query: { student_no: studentNo.value } })
}

onMounted(load)
</script>

<template>
  <div class="student-page">
    <header class="plain-topbar"><b>可信证书学生端</b><div><el-button link @click="router.push('/student')">个人中心</el-button><el-button link @click="router.push('/public/verify')">公共验真</el-button></div></header>
    <main class="plain-main">
      <PageHeader title="我的证书" description="查看本人证书状态、存证情况和验真入口">
        <el-input v-model="studentNo" placeholder="学号" clearable style="width:220px" />
        <el-button type="primary" :loading="loading" @click="load">查询</el-button>
      </PageHeader>
      <section class="panel">
        <el-table v-loading="loading" :data="rows" empty-text="暂无证书数据">
          <el-table-column prop="certificate_no" label="证书编号" min-width="190" />
          <el-table-column prop="project_name" label="项目名称" min-width="220" />
          <el-table-column prop="issue_date" label="签发日期" width="130" />
          <el-table-column label="证书状态" width="120"><template #default="s"><StatusTag :value="s.row.status" /></template></el-table-column>
          <el-table-column label="存证状态" width="120"><template #default="s"><StatusTag :value="s.row.evidence_status" /></template></el-table-column>
          <el-table-column prop="receipt_id" label="回执编号" min-width="170" show-overflow-tooltip><template #default="s">{{ s.row.receipt_id || '—' }}</template></el-table-column>
          <el-table-column label="操作" width="130"><template #default="s"><el-button link type="primary" @click="openDetail(s.row)">详情</el-button></template></el-table-column>
        </el-table>
      </section>
    </main>
  </div>
</template>

<style scoped>
.student-page{min-height:100vh;background:#f4f7fb}.plain-topbar{height:66px;background:#fff;border-bottom:1px solid #e7edf5;display:flex;align-items:center;justify-content:space-between;padding:0 42px}.plain-main{max-width:1180px;margin:0 auto;padding:28px 30px 42px}
</style>
