<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import type { Certificate } from '@/types'
import { certificateDownloadUrl, deleteCertificate, evidenceCertificate, getCertificates, reissueCertificate, revokeCertificate } from '@/api/certificates'

const router=useRouter()
const loading=ref(false),detail=ref(false),reissueDialog=ref(false),rows=ref<Certificate[]>([]),total=ref(0),current=ref<Certificate>()
const showHistory=ref(false)
const query=reactive({current:1,size:10,keyword:'',status:'',latest_only:true})
const reissueForm=reactive({reason:'',issue_date:''})
const evidenceLoading=ref<number>(),revokeLoading=ref<number>(),reissueLoading=ref(false)

async function load(){loading.value=true;try{const p=await getCertificates(query);rows.value=p.records;total.value=p.total}catch{rows.value=[]}finally{loading.value=false}}
function changeHistory(){query.latest_only=!showHistory.value;query.current=1;load()}
function reset(){query.keyword='';query.status='';showHistory.value=false;query.latest_only=true;query.current=1;load()}
function isEvidenced(row:Certificate){return Boolean(row.receipt_id)||['CONFIRMED','EVIDENCED'].includes(row.evidence_status||'')}
function viewReceipt(row:Certificate){router.push({path:'/chain',query:row.receipt_id?{receipt_id:row.receipt_id}:{keyword:row.certificate_no}})}
function download(row:Certificate){if(!row.pdf_path)return ElMessage.warning('该证书尚未生成 PDF，暂时无法下载');window.open(certificateDownloadUrl(row.certificate_no),'_blank','noopener,noreferrer')}
async function evidence(row:Certificate){if(evidenceLoading.value||isEvidenced(row))return;evidenceLoading.value=row.certificate_id;try{await evidenceCertificate(row.certificate_id);ElMessage.success('存证成功');await load()}finally{evidenceLoading.value=undefined}}
async function revoke(row:Certificate){if(revokeLoading.value)return;const {value:reason}=await ElMessageBox.prompt('请输入撤销原因','撤销证书',{inputValidator:v=>Boolean(v)||'必须填写撤销原因'});await ElMessageBox.confirm(`确认撤销证书 ${row.certificate_no}？撤销后不可恢复。`,'二次确认',{type:'warning'});revokeLoading.value=row.certificate_id;try{await revokeCertificate(row.certificate_id,reason);ElMessage.success('证书已撤销');await load()}finally{revokeLoading.value=undefined}}
function openReissue(row:Certificate){current.value=row;Object.assign(reissueForm,{reason:'',issue_date:''});reissueDialog.value=true}
async function reissue(){if(reissueLoading.value)return;if(!current.value||!reissueForm.reason||!reissueForm.issue_date)return ElMessage.warning('请填写补发原因和签发日期');reissueLoading.value=true;try{await reissueCertificate(current.value.certificate_id,reissueForm);ElMessage.success('补发成功，新证书已创建');reissueDialog.value=false;await load()}finally{reissueLoading.value=false}}
function show(row:Certificate){current.value=row;detail.value=true}
async function remove(row:Certificate){await ElMessageBox.confirm(`确认删除草稿证书 ${row.certificate_no}？`,'删除证书',{type:'warning'});await deleteCertificate(row.certificate_id);ElMessage.success('删除成功');load()}
onMounted(load)
</script>

<template>
  <div>
    <PageHeader title="证书管理" description="查询、查看和下载已由批次生成的证书"/>
    <section class="panel">
      <div class="toolbar">
        <el-input v-model="query.keyword" placeholder="证书编号、学生或项目" clearable style="width:290px"/>
        <el-select v-model="query.status" placeholder="状态" clearable style="width:150px"><el-option v-for="s in ['DRAFT','GENERATED','EVIDENCED','VALID','REVOKED','REISSUED','EXPIRED']" :key="s" :label="s" :value="s"/></el-select>
        <el-switch v-model="showHistory" active-text="显示历史证书" @change="changeHistory"/>
        <el-button type="primary" @click="query.current=1;load()">查询</el-button><el-button @click="reset">重置</el-button>
      </div>
      <el-table v-loading="loading" :data="rows" empty-text="暂无证书数据">
        <el-table-column prop="certificate_no" label="证书编号" min-width="180"/>
        <el-table-column prop="student_name" label="学生姓名" min-width="110"/>
        <el-table-column prop="batch_id" label="批次ID" width="90"/>
        <el-table-column prop="certificate_hash" label="证书哈希" min-width="220" show-overflow-tooltip/>
        <el-table-column prop="receipt_id" label="回执编号" min-width="170" show-overflow-tooltip><template #default="s">{{s.row.receipt_id||'—'}}</template></el-table-column>
        <el-table-column label="状态" width="110"><template #default="s"><StatusTag :value="s.row.status"/></template></el-table-column>
        <el-table-column label="存证状态" width="110"><template #default="s"><StatusTag :value="s.row.evidence_status"/></template></el-table-column>
        <el-table-column label="操作" min-width="350" fixed="right">
          <template #default="s">
            <el-button link type="primary" @click="show(s.row)">详情</el-button>
            <el-button link type="primary" :disabled="!s.row.pdf_path" @click="download(s.row)">下载</el-button>
            <el-button v-if="isEvidenced(s.row)" link type="success" @click="viewReceipt(s.row)">查看回执</el-button>
            <el-button v-else link type="success" :loading="evidenceLoading===s.row.certificate_id" @click="evidence(s.row)">存证</el-button>
            <el-button v-if="s.row.status!=='REVOKED'&&s.row.status!=='REISSUED'" link type="danger" :loading="revokeLoading===s.row.certificate_id" @click="revoke(s.row)">撤销</el-button>
            <el-button v-if="s.row.status==='REVOKED'" link type="warning" @click="openReissue(s.row)">补发</el-button>
            <el-button v-if="s.row.status==='DRAFT'" link type="danger" @click="remove(s.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination"><el-pagination v-model:current-page="query.current" v-model:page-size="query.size" :total="total" layout="total, sizes, prev, pager, next" @change="load"/></div>
    </section>

    <el-drawer v-model="detail" title="证书详情" size="520">
      <div v-if="current" class="detail-list">
        <div><span>证书编号</span><b>{{current.certificate_no}}</b></div><div><span>学生</span><b>{{current.student_name}}</b></div><div><span>项目</span><b>{{current.project_name}}</b></div><div><span>签发机构</span><b>{{current.institution_name||'—'}}</b></div><div><span>批次ID</span><b>{{current.batch_id}}</b></div><div><span>证书哈希</span><b>{{current.certificate_hash||'—'}}</b></div><div><span>回执编号</span><b>{{current.receipt_id||'—'}}</b></div>
      </div>
      <el-button v-if="current?.pdf_path" type="primary" style="width:100%;margin-top:20px" @click="download(current)">下载证书 PDF</el-button>
    </el-drawer>

    <el-dialog v-model="reissueDialog" title="补发证书" width="500">
      <el-alert v-if="current" :title="`原证书：${current.certificate_no}`" type="info" :closable="false"/>
      <el-form label-position="top" style="margin-top:16px" :disabled="reissueLoading"><el-form-item label="补发原因" required><el-input v-model="reissueForm.reason" type="textarea"/></el-form-item><el-form-item label="新签发日期" required><el-date-picker v-model="reissueForm.issue_date" type="date" value-format="YYYY-MM-DD"/></el-form-item></el-form>
      <template #footer><el-button :disabled="reissueLoading" @click="reissueDialog=false">取消</el-button><el-button type="primary" :loading="reissueLoading" @click="reissue">{{reissueLoading?'正在补发':'确认补发'}}</el-button></template>
    </el-dialog>
  </div>
</template>