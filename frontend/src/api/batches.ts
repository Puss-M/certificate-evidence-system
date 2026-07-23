import request from '@/utils/request'
import type { Batch, BatchCreateRequest, MerkleRootResult, PageQuery, PageResult } from '@/types'
import { batches, pageOf, templates as mockTemplates, useMock, wait } from './mock'
import { snakeize } from './helpers'
const mockMerkleRoots=new Map<number,MerkleRootResult>()
export async function getBatches(query:PageQuery):Promise<PageResult<Batch>>{if(useMock){await wait();return pageOf(batches,query)}return await request.get('/admin/batches',{params:snakeize(query)})}
export async function createBatch(data:BatchCreateRequest){if(useMock){await wait();const id=Date.now(),template=mockTemplates.find(item=>item.template_id===data.template_id);batches.unshift({batch_id:id,batch_no:`BATCH-${id}`,batch_name:data.batch_name||`BATCH-${id}`,project_id:data.project_id||template?.project_id,project_name:data.project_name||template?.project_name||'',template_id:data.template_id,student_count:0,generated:0,evidenced:0,status:'DRAFT'});return}await request.post('/admin/batches',snakeize(data))}
export async function updateBatch(batch_id:number,data:Partial<Batch>){if(useMock){await wait();Object.assign(batches.find(x=>x.batch_id===batch_id)||{},data);return}await request.put(`/admin/batches/${batch_id}`,snakeize(data))}
export async function deleteBatch(batch_id:number){if(useMock){await wait();batches.splice(batches.findIndex(x=>x.batch_id===batch_id),1);return}await request.delete(`/admin/batches/${batch_id}`)}
export async function getMerkleRoot(batch_id:number):Promise<MerkleRootResult|undefined>{
  if(useMock){await wait();return mockMerkleRoots.get(batch_id)}
  try{return await request.get(`/admin/batches/${batch_id}/merkle-root`,{skipErrorMessage:true} as any)}
  catch(error:any){if(error.response?.status===404)return undefined;throw error}
}
export async function generateMerkleRoot(batch_id:number):Promise<MerkleRootResult>{if(useMock){await wait();const result={batch_id,root_id:`ROOT-${batch_id}`,root_no:`ROOT-${batch_id}`,merkle_root:'a'.repeat(64),leaf_order_rule:'CERTIFICATE_NO_ASC',odd_leaf_rule:'DUPLICATE_LAST',previous_root_hash:'0'.repeat(64),current_root_hash:'b'.repeat(64),leaf_count:batches.find(x=>x.batch_id===batch_id)?.generated||0};mockMerkleRoots.set(batch_id,result);return result}return await request.post(`/admin/batches/${batch_id}/merkle-root`)}
