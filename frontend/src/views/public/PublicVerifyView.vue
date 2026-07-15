<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { CircleCheck, Document, Search } from '@element-plus/icons-vue'
import StatusTag from '@/components/StatusTag.vue'
import type { VerificationResult } from '@/types'
import { verifyByCertificateNo, verifyByPdf } from '@/api/verification'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const certificateNo = ref(String(route.params.certificateNo || ''))
const selectedFile = ref<File>()
const result = ref<VerificationResult>()
const resultTone = computed(() => {
  const value = result.value?.verify_result
  if (value === 'PASS') return 'pass'
  if (value === 'HASH_MISMATCH' || value === 'REVOKED' || value === 'NOT_FOUND' || value === 'SYSTEM_ERROR') return 'danger'
  return 'warning'
})

function chooseFile(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFile.value = input.files?.[0]
}

async function verifyNo() {
  if (!certificateNo.value) return ElMessage.warning('请输入证书编号')
  loading.value = true
  try {
    result.value = await verifyByCertificateNo(certificateNo.value.trim())
    router.replace(`/public/verify/${encodeURIComponent(certificateNo.value.trim())}`)
  } finally {
    loading.value = false
  }
}

async function verifyFile() {
  if (!certificateNo.value) return ElMessage.warning('请输入证书编号')
  if (!selectedFile.value) return ElMessage.warning('请选择 PDF 文件')
  loading.value = true
  try {
    result.value = await verifyByPdf(certificateNo.value.trim(), selectedFile.value)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (certificateNo.value) verifyNo()
})
</script>

<template>
  <div class="verify-page">
    <header class="verify-topbar">
      <div><b>可信证书验真</b><span>证书编号、扫码链接与 PDF 哈希复验</span></div>
      <nav><el-button link @click="router.push('/student')">学生端</el-button><el-button link @click="router.push('/login')">管理端</el-button></nav>
    </header>

    <main class="verify-main">
      <section class="verify-workbench">
        <div class="verify-copy">
          <p>公共验真端</p>
          <h1>校验证书状态、哈希指纹和存证回执</h1>
          <span>第三方可通过证书编号、二维码链接或上传 PDF 文件进行验真。</span>
        </div>
        <div class="verify-panel">
          <el-tabs>
            <el-tab-pane label="编号/扫码验真">
              <div class="verify-form">
                <el-input v-model="certificateNo" placeholder="例如 CERT-20260714-0001" clearable />
                <el-button type="primary" :icon="Search" :loading="loading" @click="verifyNo">立即验真</el-button>
              </div>
            </el-tab-pane>
            <el-tab-pane label="上传 PDF 验真">
              <div class="verify-form upload-row">
                <el-input v-model="certificateNo" placeholder="证书编号" clearable />
                <label class="file-picker">
                  <input type="file" accept="application/pdf,.pdf" @change="chooseFile" />
                  <el-icon><Document /></el-icon>
                  <span>{{ selectedFile?.name || '选择 PDF' }}</span>
                </label>
                <el-button type="primary" :loading="loading" @click="verifyFile">上传复验</el-button>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </section>

      <section v-if="result" class="verify-result panel" :class="resultTone">
        <div class="result-head">
          <div class="result-icon"><el-icon><CircleCheck /></el-icon></div>
          <div>
            <span>验真结果</span>
            <h2>{{ result.verify_message }}</h2>
          </div>
          <StatusTag :value="result.verify_result" />
        </div>
        <div class="result-grid">
          <div><span>证书编号</span><b>{{ result.certificate_no }}</b></div>
          <div><span>学生姓名</span><b>{{ result.student_name || '—' }}</b></div>
          <div><span>项目名称</span><b>{{ result.project_name || '—' }}</b></div>
          <div><span>当前状态</span><b>{{ result.status || '—' }}</b></div>
          <div><span>哈希一致</span><b>{{ result.hash_match ? '是' : '否' }}</b></div>
          <div><span>回执存在</span><b>{{ result.receipt_exists ? '是' : '否' }}</b></div>
          <div><span>回执编号</span><b>{{ result.receipt_id || '—' }}</b></div>
          <div><span>撤销时间</span><b>{{ result.revoked_at || '—' }}</b></div>
        </div>
        <dl class="hash-list">
          <dt>系统存证哈希</dt><dd>{{ result.stored_hash || result.certificate_hash || '—' }}</dd>
          <dt>上传文件哈希</dt><dd>{{ result.uploaded_hash || '未上传 PDF 时不显示' }}</dd>
          <dt>撤销原因</dt><dd>{{ result.revocation_reason || '—' }}</dd>
        </dl>
      </section>
    </main>
  </div>
</template>

<style scoped>
.verify-page{min-height:100vh;background:#f4f7fb}.verify-topbar{height:70px;background:#fff;border-bottom:1px solid #e6edf5;display:flex;justify-content:space-between;align-items:center;padding:0 46px}.verify-topbar b,.verify-topbar span{display:block}.verify-topbar span{font-size:12px;color:#7d8a9d;margin-top:4px}.verify-main{max-width:1180px;margin:0 auto;padding:34px 30px 46px}.verify-workbench{display:grid;grid-template-columns:minmax(0,1fr) 520px;gap:28px;align-items:end;margin-bottom:22px}.verify-copy p{color:#2563eb;font-weight:700;margin:0 0 10px}.verify-copy h1{font-size:38px;line-height:1.25;margin:0 0 12px;max-width:620px}.verify-copy span{color:#718096}.verify-panel{background:#fff;border:1px solid #e7edf5;border-radius:14px;padding:20px}.verify-form{display:flex;gap:10px}.verify-form .el-input{flex:1}.upload-row{align-items:center}.file-picker{height:32px;min-width:150px;display:flex;align-items:center;justify-content:center;gap:7px;border:1px solid #dcdfe6;border-radius:4px;padding:0 11px;color:#606266;cursor:pointer;background:#fff}.file-picker input{display:none}.file-picker span{max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.verify-result{border-left:5px solid #e2e8f0}.verify-result.pass{border-left-color:#10b981}.verify-result.danger{border-left-color:#ef4444}.verify-result.warning{border-left-color:#f59e0b}.result-head{display:flex;align-items:center;gap:16px;border-bottom:1px solid #edf0f4;padding-bottom:18px}.result-head>div:nth-child(2){flex:1}.result-head span{color:#7b8798}.result-head h2{font-size:22px;margin:5px 0 0}.result-icon{width:46px;height:46px;border-radius:12px;display:grid;place-items:center;background:#eaf2ff;color:#2563eb;font-size:22px}.result-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:#e7edf5;border:1px solid #e7edf5;border-radius:10px;overflow:hidden;margin-top:18px}.result-grid>div{background:#fff;padding:15px}.result-grid span,.result-grid b{display:block}.result-grid span{font-size:12px;color:#7d8a9d}.result-grid b{margin-top:5px}.hash-list{margin:18px 0 0}.hash-list dt{font-size:12px;color:#7d8a9d;margin-top:14px}.hash-list dd{margin:6px 0 0;word-break:break-all;font-family:Consolas,monospace;font-size:12px}
</style>
