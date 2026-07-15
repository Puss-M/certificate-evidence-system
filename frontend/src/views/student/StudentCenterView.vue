<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { DocumentChecked, Link, User } from '@element-plus/icons-vue'
import StatusTag from '@/components/StatusTag.vue'
import type { Certificate } from '@/types'
import { getMyCertificates, getSavedStudentNo } from '@/api/studentCertificates'

const router = useRouter()
const loading = ref(false)
const studentNo = ref(getSavedStudentNo())
const certificates = ref<Certificate[]>([])

const studentName = computed(() => certificates.value[0]?.student_name || '演示学生')
const validCount = computed(() => certificates.value.filter(item => item.status === 'VALID').length)
const evidencedCount = computed(() => certificates.value.filter(item => item.evidence_status === 'CONFIRMED').length)
const latest = computed(() => certificates.value.slice(0, 3))

async function load() {
  if (!studentNo.value) return ElMessage.warning('请输入学号')
  loading.value = true
  try {
    certificates.value = await getMyCertificates(studentNo.value)
  } catch {
    certificates.value = []
  } finally {
    loading.value = false
  }
}

function openCertificate(row: Certificate) {
  router.push({ path: `/student/certificates/${row.certificate_no}`, query: { student_no: studentNo.value } })
}

onMounted(load)
</script>

<template>
  <div class="student-page">
    <header class="student-topbar">
      <div class="student-brand"><span>链</span><div><b>可信证书学生端</b><small>实训证书与学业证明</small></div></div>
      <nav><el-button link @click="router.push('/public/verify')">公共验真</el-button><el-button type="primary" @click="router.push({path:'/student/certificates',query:{student_no:studentNo}})">我的证书</el-button></nav>
    </header>

    <main class="student-main">
      <section class="student-hero">
        <div>
          <p>学生个人中心</p>
          <h1>{{ studentName }}</h1>
          <span>{{ studentNo }} · 查看、下载和分享自己的可信证书</span>
        </div>
        <div class="student-search">
          <el-input v-model="studentNo" placeholder="输入演示学号，如 S20260001" clearable />
          <el-button type="primary" :loading="loading" @click="load">查询</el-button>
        </div>
      </section>

      <section class="student-metrics">
        <div><el-icon><DocumentChecked /></el-icon><span>证书总数</span><b>{{ certificates.length }}</b></div>
        <div><el-icon><User /></el-icon><span>有效证书</span><b>{{ validCount }}</b></div>
        <div><el-icon><Link /></el-icon><span>已存证</span><b>{{ evidencedCount }}</b></div>
      </section>

      <section class="panel">
        <div class="panel-title"><div><h3>最近证书</h3><p>从这里进入详情页下载 PDF、展示二维码或复制验真链接</p></div><el-button @click="router.push({path:'/student/certificates',query:{student_no:studentNo}})">查看全部</el-button></div>
        <el-table v-loading="loading" :data="latest" empty-text="暂无证书">
          <el-table-column prop="certificate_no" label="证书编号" min-width="180" />
          <el-table-column prop="project_name" label="项目名称" min-width="220" />
          <el-table-column prop="issue_date" label="签发日期" width="130" />
          <el-table-column label="状态" width="110"><template #default="s"><StatusTag :value="s.row.status" /></template></el-table-column>
          <el-table-column label="操作" width="120"><template #default="s"><el-button link type="primary" @click="openCertificate(s.row)">详情</el-button></template></el-table-column>
        </el-table>
      </section>
    </main>
  </div>
</template>

<style scoped>
.student-page{min-height:100vh;background:#f4f7fb}.student-topbar{height:70px;background:#fff;border-bottom:1px solid #e7edf5;display:flex;align-items:center;justify-content:space-between;padding:0 46px}.student-brand{display:flex;align-items:center;gap:12px}.student-brand>span{width:38px;height:38px;border-radius:10px;display:grid;place-items:center;background:#2563eb;color:#fff;font-weight:800}.student-brand b,.student-brand small{display:block}.student-brand small{color:#7d8a9d;margin-top:3px}.student-main{max-width:1120px;margin:0 auto;padding:30px}.student-hero{display:flex;justify-content:space-between;gap:24px;align-items:flex-end;margin-bottom:20px}.student-hero p{margin:0 0 8px;color:#2563eb;font-weight:700}.student-hero h1{font-size:34px;margin:0 0 8px}.student-hero span{color:#778396}.student-search{width:430px;display:flex;gap:10px}.student-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:20px}.student-metrics>div{background:#fff;border:1px solid #e7edf5;border-radius:12px;padding:20px;display:grid;grid-template-columns:42px 1fr;gap:4px 12px;align-items:center}.student-metrics .el-icon{grid-row:1/3;width:42px;height:42px;border-radius:10px;background:#eaf2ff;color:#2563eb}.student-metrics span{color:#7a8798}.student-metrics b{font-size:25px}
</style>
