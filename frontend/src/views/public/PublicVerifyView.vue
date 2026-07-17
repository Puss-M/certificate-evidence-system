<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { CircleCheck, Document, Search } from '@element-plus/icons-vue'
import StatusTag from '@/components/StatusTag.vue'
import type { MerkleProofResult, VerificationResult } from '@/types'
import { getMerkleProof, verifyByCertificateNo, verifyByPdf } from '@/api/verification'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const certificateNo = ref(String(route.params.certificateNo || ''))
const selectedFile = ref<File>()
const result = ref<VerificationResult>()
const merkleProof = ref<MerkleProofResult>()
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

async function loadMerkleProof(no: string) {
  merkleProof.value = undefined
  merkleProof.value = await getMerkleProof(no)
}

async function verifyNo() {
  if (!certificateNo.value) return ElMessage.warning('请输入证书编号')
  loading.value = true
  try {
    const no = certificateNo.value.trim()
    result.value = await verifyByCertificateNo(no)
    await loadMerkleProof(no)
    router.replace(`/public/verify/${encodeURIComponent(no)}`)
  } finally {
    loading.value = false
  }
}

async function verifyFile() {
  if (!certificateNo.value) return ElMessage.warning('请输入证书编号')
  if (!selectedFile.value) return ElMessage.warning('请选择 PDF 文件')
  loading.value = true
  try {
    const no = certificateNo.value.trim()
    result.value = await verifyByPdf(no, selectedFile.value)
    await loadMerkleProof(no)
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
        <div class="merkle-panel">
          <div class="merkle-title">
            <div>
              <span>批次 Root 与测试链回执</span>
              <h3>{{ merkleProof ? '已生成 Merkle Proof' : '暂无 Merkle Root' }}</h3>
            </div>
            <StatusTag :value="merkleProof?.verified ? 'PASS' : 'PENDING'" />
          </div>
          <template v-if="merkleProof">
            <div class="result-grid merkle-grid">
              <div><span>Root 编号</span><b>{{ merkleProof.root_no }}</b></div>
              <div><span>叶子序号</span><b>{{ merkleProof.leaf_index }}</b></div>
              <div><span>叶子数量</span><b>{{ merkleProof.leaf_count }}</b></div>
              <div><span>Proof 验证</span><b>{{ merkleProof.proof_valid ? '通过' : '失败' }}</b></div>
              <div><span>排序规则</span><b>{{ merkleProof.leaf_order_rule }}</b></div>
              <div><span>奇数叶规则</span><b>{{ merkleProof.odd_leaf_rule }}</b></div>
              <div><span>测试链交易</span><b>{{ merkleProof.tx_hash ? '已写入' : '未配置或未写入' }}</b></div>
              <div><span>Proof 步数</span><b>{{ merkleProof.proof.length }}</b></div>
            </div>
            <dl class="hash-list">
              <dt>Merkle Root</dt><dd>{{ merkleProof.merkle_root }}</dd>
              <dt>Root 链当前哈希</dt><dd>{{ merkleProof.current_root_hash }}</dd>
              <dt>Root 链上一哈希</dt><dd>{{ merkleProof.previous_root_hash || '—' }}</dd>
              <dt>测试链交易哈希</dt><dd>{{ merkleProof.tx_hash || '暂无链上交易哈希，本地 Root 仍可用于 Proof 验证' }}</dd>
            </dl>
          </template>
          <p v-else class="merkle-empty">该证书所在批次尚未生成 Merkle Root，或本地测试链回执尚未写入；不影响编号验真和 PDF 哈希复验。</p>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.verify-page{min-height:100vh;background:#f4f7fb}.verify-topbar{height:70px;background:#fff;border-bottom:1px solid #e6edf5;display:flex;justify-content:space-between;align-items:center;padding:0 46px}.verify-topbar b,.verify-topbar span{display:block}.verify-topbar span{font-size:12px;color:#7d8a9d;margin-top:4px}.verify-main{max-width:1180px;margin:0 auto;padding:34px 30px 46px}.verify-workbench{display:grid;grid-template-columns:minmax(0,1fr) 520px;gap:28px;align-items:end;margin-bottom:22px}.verify-copy p{color:#2563eb;font-weight:700;margin:0 0 10px}.verify-copy h1{font-size:38px;line-height:1.25;margin:0 0 12px;max-width:620px}.verify-copy span{color:#718096}.verify-panel{background:#fff;border:1px solid #e7edf5;border-radius:14px;padding:20px}.verify-form{display:flex;gap:10px}.verify-form .el-input{flex:1}.upload-row{align-items:center}.file-picker{height:32px;min-width:150px;display:flex;align-items:center;justify-content:center;gap:7px;border:1px solid #dcdfe6;border-radius:4px;padding:0 11px;color:#606266;cursor:pointer;background:#fff}.file-picker input{display:none}.file-picker span{max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.verify-result{border-left:5px solid #e2e8f0}.verify-result.pass{border-left-color:#10b981}.verify-result.danger{border-left-color:#ef4444}.verify-result.warning{border-left-color:#f59e0b}.result-head{display:flex;align-items:center;gap:16px;border-bottom:1px solid #edf0f4;padding-bottom:18px}.result-head>div:nth-child(2){flex:1}.result-head span{color:#7b8798}.result-head h2{font-size:22px;margin:5px 0 0}.result-icon{width:46px;height:46px;border-radius:12px;display:grid;place-items:center;background:#eaf2ff;color:#2563eb;font-size:22px}.result-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:#e7edf5;border:1px solid #e7edf5;border-radius:10px;overflow:hidden;margin-top:18px}.result-grid>div{background:#fff;padding:15px}.result-grid span,.result-grid b{display:block}.result-grid span{font-size:12px;color:#7d8a9d}.result-grid b{margin-top:5px}.hash-list{margin:18px 0 0}.hash-list dt{font-size:12px;color:#7d8a9d;margin-top:14px}.hash-list dd{margin:6px 0 0;word-break:break-all;font-family:Consolas,monospace;font-size:12px}.merkle-panel{margin-top:22px;padding-top:20px;border-top:1px solid #edf0f4}.merkle-title{display:flex;justify-content:space-between;align-items:flex-start;gap:14px}.merkle-title span{font-size:12px;color:#7d8a9d}.merkle-title h3{margin:5px 0 0;font-size:18px}.merkle-grid{grid-template-columns:repeat(4,1fr)}.merkle-empty{margin:14px 0 0;color:#718096;line-height:1.7}
@media (max-width: 768px){.verify-topbar{height:auto;min-height:62px;padding:10px 16px;gap:12px;flex-wrap:wrap}.verify-main{padding:22px 14px 32px}.verify-workbench{grid-template-columns:1fr;gap:18px}.verify-copy h1{font-size:28px}.verify-panel{padding:14px}.verify-form{flex-direction:column}.upload-row{align-items:stretch}.file-picker{box-sizing:border-box;width:100%}.file-picker span{max-width:calc(100vw - 100px)}.result-head{align-items:flex-start;flex-wrap:wrap}.result-head>div:nth-child(2){min-width:0}.result-head h2{font-size:18px}.result-grid{grid-template-columns:1fr 1fr}.result-grid b{overflow-wrap:anywhere}}
@media (max-width: 480px){.result-grid{grid-template-columns:1fr}}
</style>
