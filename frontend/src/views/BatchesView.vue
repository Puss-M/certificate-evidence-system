<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import type { Batch, IssueResult, MerkleRootResult, Student, Template } from '@/types'
import { createBatch, deleteBatch, generateMerkleRoot, getBatches, getMerkleRoot } from '@/api/batches'
import { evidenceBatch, issueCertificates, issueCertificatesWithSignature } from '@/api/certificates'
import { getStudents } from '@/api/students'
import { getTemplates } from '@/api/templates'

const loading=ref(false),dialog=ref(false),detail=ref(false),generateDrawer=ref(false)
const rows=ref<Batch[]>([]),total=ref(0),current=ref<Batch>()
const students=ref<Student[]>([]),templates=ref<Template[]>([])
const rootLoading=ref<number>(),rootQueryLoading=ref<number>(),roots=ref<Record<number,MerkleRootResult>>({}),evidenceLoading=ref<number>()
const generateLoading=ref(false),issueResult=ref<IssueResult>()
const signatureFile=ref<File>(),signaturePreviewUrl=ref(''),signatureInputKey=ref(0)
const currentTemplate=computed(()=>templates.value.find(item=>item.template_id===current.value?.template_id))
const needsMentorSignature=computed(()=>currentTemplate.value?.fields.includes('mentor_signature')??false)
const query=reactive({current:1,size:10,keyword:'',status:''})
const form=reactive({template_id:0})
const generateForm=reactive({student_ids:[] as number[],issue_date:''})

async function load(){loading.value=true;try{const p=await getBatches(query);rows.value=p.records;total.value=p.total;await Promise.allSettled(p.records.map(async row=>{const result=await getMerkleRoot(row.batch_id);if(result)roots.value[row.batch_id]=result;else delete roots.value[row.batch_id]}))}catch{rows.value=[]}finally{loading.value=false}}
function reset(){query.keyword='';query.current=1;load()}
async function ensureTemplates(){if(!templates.value.length){const page=await getTemplates({current:1,size:100,keyword:'',status:''});templates.value=page.records}}
async function openCreate(){form.template_id=0;await ensureTemplates();dialog.value=true}
function templateName(templateId:number){return templates.value.find(item=>item.template_id===templateId)?.name||`模板 #${templateId}`}
async function save(){if(!form.template_id)return ElMessage.warning('请选择证书模板');await createBatch({template_id:form.template_id});ElMessage.success('批次创建成功，批次编号由系统自动生成');dialog.value=false;load()}
async function remove(row:Batch){await ElMessageBox.confirm(`确认删除批次“${row.batch_no}”吗？`,'删除批次',{type:'warning'});await deleteBatch(row.batch_id);ElMessage.success('删除成功');load()}
function canEvidence(row:Batch){return row.generated>0&&row.evidenced<row.generated}
async function evidence(row:Batch){if(evidenceLoading.value||!canEvidence(row))return;evidenceLoading.value=row.batch_id;try{await evidenceBatch(row.batch_id);ElMessage.success('批量存证完成');await load()}finally{evidenceLoading.value=undefined}}
function resetSignature(){if(signaturePreviewUrl.value)URL.revokeObjectURL(signaturePreviewUrl.value);signaturePreviewUrl.value='';signatureFile.value=undefined;signatureInputKey.value++}
function selectSignature(event:Event){const input=event.target as HTMLInputElement;const file=input.files?.[0];if(!file)return;if(!['image/png','image/jpeg'].includes(file.type)){ElMessage.warning('请上传 PNG 或 JPG 格式的导师签名图片');input.value='';return}if(file.size>5*1024*1024){ElMessage.warning('导师签名图片不能超过 5MB');input.value='';return}if(signaturePreviewUrl.value)URL.revokeObjectURL(signaturePreviewUrl.value);signatureFile.value=file;signaturePreviewUrl.value=URL.createObjectURL(file)}
async function openGenerate(row:Batch){current.value=row;generateForm.student_ids=[];generateForm.issue_date='';issueResult.value=undefined;resetSignature();await ensureTemplates();if(!students.value.length){const page=await getStudents({current:1,size:100,keyword:'',status:''});students.value=page.records}generateDrawer.value=true}
async function generateCertificates(){if(generateLoading.value||!current.value)return;const template=currentTemplate.value;const projectId=current.value.project_id||template?.project_id||0;if(!projectId)return ElMessage.warning('当前模板尚未绑定实训项目，请先编辑模板');if(!generateForm.student_ids.length||!generateForm.issue_date)return ElMessage.warning('请选择学生和签发日期');if(needsMentorSignature.value&&!signatureFile.value)return ElMessage.warning('当前模板包含导师签章，请上传导师签名图片');const requestData={project_id:projectId,template_id:current.value.template_id,batch_id:current.value.batch_id,student_ids:generateForm.student_ids,issue_date:generateForm.issue_date};generateLoading.value=true;try{issueResult.value=needsMentorSignature.value?await issueCertificatesWithSignature({...requestData,mentor_signature:signatureFile.value!}):await issueCertificates(requestData);ElMessage.success(`证书生成完成：成功 ${issueResult.value.success_count} 张，失败 ${issueResult.value.failed_count} 张`);await load()}finally{generateLoading.value=false}}
async function createRoot(row:Batch){if(rootLoading.value)return;rootLoading.value=row.batch_id;try{const existing=await getMerkleRoot(row.batch_id);if(existing){roots.value[row.batch_id]=existing;current.value=row;detail.value=true;ElMessage.info('该批次已生成 Merkle Root，已打开现有结果');return}await ElMessageBox.confirm('生成后 Root 将作为历史事实保存，不能覆盖或删除。确认继续吗？','生成 Merkle Root',{type:'warning'});const result=await generateMerkleRoot(row.batch_id);roots.value[row.batch_id]=result;current.value=row;detail.value=true;ElMessage.success(result.tx_hash?'Merkle Root 已生成并写入测试链':'Merkle Root 已生成，本次未返回链上交易哈希')}finally{rootLoading.value=undefined}}
async function show(row:Batch){current.value=row;detail.value=true;await ensureTemplates();rootQueryLoading.value=row.batch_id;try{const result=await getMerkleRoot(row.batch_id);if(result)roots.value[row.batch_id]=result;else delete roots.value[row.batch_id]}finally{if(rootQueryLoading.value===row.batch_id)rootQueryLoading.value=undefined}}
function copy(value?:string){if(value){navigator.clipboard.writeText(value);ElMessage.success('已复制')}}
onMounted(async()=>{await ensureTemplates();await load()})
onBeforeUnmount(resetSignature)
</script>

<template>
  <div>
    <PageHeader title="证书批次" description="按模板创建批次，并在批次中统一生成证书">
      <el-button type="primary" @click="openCreate">创建批次</el-button>
    </PageHeader>
    <section class="panel">
      <div class="toolbar">
        <el-input v-model="query.keyword" placeholder="批次编号或项目" clearable style="width:280px"/>
        <el-button type="primary" @click="query.current=1;load()">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>
      <el-table v-loading="loading" :data="rows" empty-text="暂无批次数据">
        <el-table-column prop="batch_no" label="批次编号" min-width="190"/>
        <el-table-column label="证书模板" min-width="190"><template #default="s">{{templateName(s.row.template_id)}}</template></el-table-column>
        <el-table-column prop="project_name" label="绑定项目" min-width="180"><template #default="s">{{s.row.project_name||'由模板确定'}}</template></el-table-column>
        <el-table-column label="操作" min-width="390">
          <template #default="s">
            <el-button link type="primary" @click="show(s.row)">详情</el-button>
            <el-button link type="primary" @click="openGenerate(s.row)">生成证书</el-button>
            <el-button link type="success" :disabled="!canEvidence(s.row)" :loading="evidenceLoading===s.row.batch_id" :title="s.row.generated===0?'请先生成证书':'该批次已全部存证'" @click="evidence(s.row)">{{s.row.evidenced>=s.row.generated&&s.row.generated>0?'已全部存证':'批量存证'}}</el-button>
            <el-button link type="warning" :loading="rootLoading===s.row.batch_id" @click="roots[s.row.batch_id]?show(s.row):createRoot(s.row)">{{roots[s.row.batch_id]?'查看Root':'生成Root'}}</el-button>
            <el-button link type="danger" @click="remove(s.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination"><el-pagination v-model:current-page="query.current" v-model:page-size="query.size" :total="total" layout="total, sizes, prev, pager, next" @change="load"/></div>
    </section>

    <el-dialog v-model="dialog" title="创建批次" width="560">
      <el-alert title="批次编号由系统自动生成，实训项目由证书模板的绑定关系确定。" type="info" :closable="false" style="margin-bottom:18px"/>
      <el-form label-position="top">
        <el-form-item label="证书模板" required>
          <el-select v-model="form.template_id" filterable placeholder="请选择已绑定项目的证书模板" style="width:100%">
            <el-option v-for="item in templates" :key="item.template_id" :label="`${item.name}（${item.project_name||'未绑定项目'}）`" :value="item.template_id" :disabled="!item.project_id||!item.enabled"/>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" @click="save">创建批次</el-button></template>
    </el-dialog>

    <el-drawer v-model="generateDrawer" title="生成证书" size="600">
      <el-alert v-if="current" :title="`批次：${current.batch_no}　模板：${templateName(current.template_id)}`" type="info" :closable="false"/>
      <el-form label-position="top" style="margin-top:18px" :disabled="generateLoading">
        <el-form-item label="选择学生" required>
          <el-select v-model="generateForm.student_ids" multiple filterable collapse-tags style="width:100%">
            <el-option v-for="student in students" :key="student.student_id" :label="`${student.student_no} ${student.student_name}`" :value="student.student_id"/>
          </el-select>
        </el-form-item>
        <el-form-item label="签发日期" required><el-date-picker v-model="generateForm.issue_date" type="date" value-format="YYYY-MM-DD" style="width:100%"/></el-form-item>
        <el-form-item v-if="needsMentorSignature" label="导师签名图片" required>
          <div class="signature-upload">
            <input :key="signatureInputKey" type="file" accept="image/png,image/jpeg" @change="selectSignature"/>
            <p>支持 PNG、JPG，建议使用透明背景横版签名图；后端会自动居中裁剪为 4:1。本图片仅用于本次生成，不会保存。</p>
            <img v-if="signaturePreviewUrl" :src="signaturePreviewUrl" alt="导师签名预览"/>
          </div>
        </el-form-item>
        <el-button type="primary" style="width:100%" :loading="generateLoading" @click="generateCertificates">{{generateLoading?'正在生成':'生成证书'}}</el-button>
      </el-form>
      <el-result v-if="issueResult" :icon="issueResult.failed_count?'warning':'success'" :title="`成功 ${issueResult.success_count} 张，失败 ${issueResult.failed_count} 张`">
        <template #extra><el-table v-if="issueResult.failures.length" :data="issueResult.failures" size="small"><el-table-column prop="student_name" label="学生"/><el-table-column prop="reason" label="失败原因"/></el-table></template>
      </el-result>
    </el-drawer>

    <el-drawer v-model="detail" title="批次详情" size="620">
      <div v-if="current" class="detail-list">
        <div><span>批次编号</span><b>{{current.batch_no}}</b></div>
        <div><span>证书模板</span><b>{{templateName(current.template_id)}}</b></div>
        <div><span>绑定项目</span><b>{{current.project_name||'由模板确定'}}</b></div>
      </div>
      <template v-if="current">
        <h3 class="evidence-title">存证信息（P2）</h3>
        <div v-loading="rootQueryLoading===current.batch_id" class="root-section">
          <el-empty v-if="!roots[current.batch_id]" description="该批次尚未生成 Merkle Root" :image-size="70"><el-button type="primary" :loading="rootLoading===current.batch_id" @click="createRoot(current)">生成 Merkle Root</el-button></el-empty>
          <div v-else class="root-info">
            <el-tag :type="roots[current.batch_id].tx_hash?'success':'info'">{{roots[current.batch_id].tx_hash?'测试链已返回交易哈希':'本地Root'}}</el-tag>
            <dl><dt>Root编号</dt><dd>{{roots[current.batch_id].root_no}}</dd><dt>Merkle Root</dt><dd @click="copy(roots[current.batch_id].merkle_root)">{{roots[current.batch_id].merkle_root}}</dd><dt>Root链哈希</dt><dd @click="copy(roots[current.batch_id].current_root_hash)">{{roots[current.batch_id].current_root_hash}}</dd><dt>证书叶子数</dt><dd>{{roots[current.batch_id].leaf_count}}</dd><dt>排序 / 奇数叶规则</dt><dd>{{roots[current.batch_id].leaf_order_rule}} / {{roots[current.batch_id].odd_leaf_rule}}</dd><dt>交易哈希</dt><dd v-if="roots[current.batch_id].tx_hash" @click="copy(roots[current.batch_id].tx_hash)">{{roots[current.batch_id].tx_hash}}</dd><dd v-else>本地 Root 暂无链上交易哈希</dd></dl>
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>
<style scoped>.evidence-title{margin:28px 0 14px;border-top:1px solid #edf0f4;padding-top:22px}.root-section{min-height:180px}.root-info dl{margin-top:16px}.root-info dt{font-size:12px;color:#7d8a9d;margin-top:14px}.root-info dd{margin:5px 0 0;font:12px Consolas,monospace;word-break:break-all;cursor:pointer}.root-info dd:last-child{cursor:default}.signature-upload{width:100%;padding:14px;border:1px dashed #cbd5e1;border-radius:8px;background:#f8fafc}.signature-upload input{display:block;width:100%}.signature-upload p{margin:9px 0 0;color:#7d8a9d;font-size:12px;line-height:1.6}.signature-upload img{display:block;max-width:320px;max-height:100px;margin-top:12px;padding:8px;background:#fff;border:1px solid #e5e7eb;border-radius:6px;object-fit:contain}</style>


