<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import type { Certificate } from '@/types'
import { buildStudentDownloadUrl, buildStudentQrCodeUrl, getSavedStudentNo, getStudentCertificateDetail, isStudentCertificateMockMode } from '@/api/studentCertificates'
import { downloadDataUrl, downloadDemoCertificatePdf } from '@/utils/demoCertificate'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const studentNo = ref(String(route.query.student_no || getSavedStudentNo()))
const certificate = ref<Certificate>()
const certificateNo = computed(() => String(route.params.certificateNo || ''))
const verifyLink = computed(() => `${location.origin}/public/verify/${encodeURIComponent(certificateNo.value)}`)
const downloadUrl = computed(() => buildStudentDownloadUrl(certificateNo.value, studentNo.value))
const qrcodeUrl = computed(() => buildStudentQrCodeUrl(certificateNo.value, studentNo.value))

async function load() {
  loading.value = true
  try {
    certificate.value = await getStudentCertificateDetail(certificateNo.value, studentNo.value)
  } finally {
    loading.value = false
  }
}

async function copyVerifyLink() {
  await navigator.clipboard.writeText(verifyLink.value)
  ElMessage.success('验真链接已复制')
}

function downloadPdf() {
  if (isStudentCertificateMockMode() && certificate.value) {
    downloadDemoCertificatePdf(certificate.value, verifyLink.value)
    return
  }
  window.open(downloadUrl.value, '_blank')
}

function downloadQrCode() {
  if (!qrcodeUrl.value) return
  downloadDataUrl(qrcodeUrl.value, `${certificateNo.value}_qrcode.${qrcodeUrl.value.startsWith('data:image/svg') ? 'svg' : 'png'}`)
}

onMounted(load)
</script>

<template>
  <div class="student-page">
    <header class="plain-topbar"><b>可信证书学生端</b><div><el-button link @click="router.push({path:'/student/certificates',query:{student_no:studentNo}})">我的证书</el-button><el-button link @click="router.push('/public/verify')">公共验真</el-button></div></header>
    <main class="plain-main">
      <PageHeader title="证书详情" description="下载 PDF、展示二维码并查看链上/链式存证回执">
        <el-button @click="copyVerifyLink">复制验真链接</el-button>
        <el-button type="primary" @click="downloadPdf">下载 PDF</el-button>
      </PageHeader>

      <section v-loading="loading" class="detail-grid" v-if="certificate">
        <div class="panel certificate-summary">
          <div class="certificate-title">
            <div>
              <span>实训证书</span>
              <h2>{{ certificate.project_name || '实训结业证书' }}</h2>
            </div>
            <StatusTag :value="certificate.status" />
          </div>
          <div class="certificate-preview">
            <p>Certificate</p>
            <h3>{{ certificate.student_name }}</h3>
            <span>{{ certificate.project_name }}</span>
            <small>{{ certificate.certificate_no }}</small>
          </div>
          <dl>
            <dt>证书编号</dt><dd>{{ certificate.certificate_no }}</dd>
            <dt>学生姓名</dt><dd>{{ certificate.student_name }}</dd>
            <dt>学号</dt><dd>{{ certificate.student_no }}</dd>
            <dt>签发日期</dt><dd>{{ certificate.issue_date || '—' }}</dd>
            <dt>存证状态</dt><dd><StatusTag :value="certificate.evidence_status" /></dd>
            <dt>存证回执</dt><dd>{{ certificate.receipt_id || '—' }}</dd>
            <dt>Root 编号</dt><dd>{{ certificate.root_id || '暂未生成' }}</dd>
            <dt>补发证书</dt><dd>{{ certificate.new_certificate_no || '—' }}</dd>
            <dt>证书哈希</dt><dd class="break">{{ certificate.certificate_hash || '—' }}</dd>
            <dt>验真链接</dt><dd class="break">{{ verifyLink }}</dd>
          </dl>
        </div>
        <aside class="panel share-panel">
          <h3>二维码展示</h3>
          <img v-if="qrcodeUrl" :src="qrcodeUrl" alt="证书验真二维码" />
          <div v-else class="qr-fallback">QR</div>
          <p>第三方扫码后进入公共验真页面，可查看证书状态、哈希校验和存证回执。</p>
          <div class="share-actions">
            <el-button type="primary" @click="router.push(`/public/verify/${certificate.certificate_no}`)">打开验真页</el-button>
            <el-button @click="downloadQrCode">下载二维码</el-button>
          </div>
        </aside>
      </section>
    </main>
  </div>
</template>

<style scoped>
.student-page{min-height:100vh;background:#f4f7fb}.plain-topbar{height:66px;background:#fff;border-bottom:1px solid #e7edf5;display:flex;align-items:center;justify-content:space-between;padding:0 42px}.plain-main{max-width:1180px;margin:0 auto;padding:28px 30px 42px}.detail-grid{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:20px}.certificate-title{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;border-bottom:1px solid #edf0f4;padding-bottom:16px}.certificate-title span{display:block;color:#2563eb;font-weight:700;margin-bottom:6px}.certificate-title h2{margin:0;font-size:24px}.certificate-preview{margin:18px 0 4px;padding:26px;border:6px double #d8b36a;border-radius:8px;background:#fffdf7;text-align:center}.certificate-preview p{margin:0 0 10px;color:#9a7433;font-family:Georgia,serif;font-size:12px;text-transform:uppercase}.certificate-preview h3{margin:0;font-family:Georgia,serif;font-size:34px;color:#172033}.certificate-preview span,.certificate-preview small{display:block}.certificate-preview span{margin-top:12px;color:#475569}.certificate-preview small{margin-top:14px;color:#7a8798;font-family:Consolas,monospace}.certificate-summary dl{display:grid;grid-template-columns:110px minmax(0,1fr);gap:16px 18px;margin:20px 0 0}.certificate-summary dt{color:#7a8798}.certificate-summary dd{margin:0;font-weight:600}.share-panel{text-align:center}.share-panel h3{margin-top:0}.share-panel img,.qr-fallback{width:210px;height:210px;margin:12px auto 18px;border:1px solid #d9e2ee;border-radius:8px;background:#fff;object-fit:contain}.qr-fallback{display:grid;place-items:center;color:#2563eb;font-weight:800;font-size:32px}.share-panel p{color:#758196;line-height:1.7;text-align:left}.share-actions{display:grid;gap:10px}.share-actions .el-button{width:100%;margin-left:0}.break{word-break:break-all;font-family:Consolas,monospace;font-size:12px}
@media (max-width: 768px){.plain-topbar{height:auto;min-height:62px;padding:10px 16px;gap:12px;flex-wrap:wrap}.plain-main{padding:20px 14px 32px}.detail-grid{grid-template-columns:1fr}.certificate-title{flex-wrap:wrap}.certificate-summary dl{grid-template-columns:1fr;gap:6px}.certificate-summary dd{margin-bottom:10px}.share-panel img,.qr-fallback{width:180px;height:180px}}
</style>
