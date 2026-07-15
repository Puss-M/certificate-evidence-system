import request from '@/utils/request'
import type { VerificationResult } from '@/types'
import { certificates, receipts, useMock, wait } from './mock'

function buildResult(partial: Partial<VerificationResult> & Pick<VerificationResult, 'certificate_no' | 'result'>): VerificationResult {
  const messageMap: Record<string, string> = {
    PASS: '证书有效，哈希一致，存证回执存在。',
    REVOKED: '证书已撤销，不再有效。',
    REISSUED: '旧证书已补发，请查看新证书。',
    HASH_MISMATCH: '上传文件与存证版本不一致，可能已被篡改。',
    NOT_FOUND: '未查询到该证书编号。',
    NO_RECEIPT: '证书存在，但未完成存证或回执不存在。',
    SYSTEM_ERROR: '验真服务暂不可用。'
  }
  const message = partial.message || partial.verify_message || messageMap[partial.result] || '验真完成。'
  return {
    result: partial.result,
    verify_result: partial.verify_result || partial.result,
    certificate_no: partial.certificate_no,
    student_name: partial.student_name,
    project_name: partial.project_name,
    institution_name: partial.institution_name,
    certificate_hash: partial.certificate_hash,
    stored_hash: partial.stored_hash || partial.certificate_hash,
    receipt_id: partial.receipt_id,
    receipt_exists: partial.receipt_exists ?? false,
    status: partial.status,
    message,
    verify_message: message,
    hash_match: partial.hash_match ?? false,
    uploaded_hash: partial.uploaded_hash,
    revocation_reason: partial.revocation_reason,
    revoked_at: partial.revoked_at
  }
}

export async function verifyByCertificateNo(certificateNo: string): Promise<VerificationResult> {
  if (useMock) {
    await wait()
    const row = certificates.find(item => item.certificate_no === certificateNo)
    if (!row) return buildResult({ certificate_no: certificateNo, result: 'NOT_FOUND' })
    const receiptExists = Boolean(row.receipt_id && receipts.some(item => item.receipt_id === row.receipt_id))
    if (row.status === 'REVOKED' || row.status === 'REISSUED' || row.status === 'EXPIRED') {
      return buildResult({ certificate_no: certificateNo, result: row.status, status: row.status, student_name: row.student_name, project_name: row.project_name, certificate_hash: row.certificate_hash, receipt_id: row.receipt_id, receipt_exists: receiptExists, hash_match: receiptExists })
    }
    return buildResult({ certificate_no: certificateNo, result: receiptExists ? 'PASS' : 'NO_RECEIPT', status: row.status, student_name: row.student_name, project_name: row.project_name, certificate_hash: row.certificate_hash, receipt_id: row.receipt_id, receipt_exists: receiptExists, hash_match: receiptExists })
  }
  return await request.get(`/verification/${encodeURIComponent(certificateNo)}`)
}

export async function verifyByPdf(certificateNo: string, file: File): Promise<VerificationResult> {
  if (useMock) {
    await wait(360)
    const row = certificates.find(item => item.certificate_no === certificateNo)
    if (!row) return buildResult({ certificate_no: certificateNo, result: 'NOT_FOUND' })
    const isTampered = file.name.toLowerCase().includes('tamper') || file.name.includes('篡改')
    return buildResult({ certificate_no: certificateNo, result: isTampered ? 'HASH_MISMATCH' : row.status === 'REVOKED' ? 'REVOKED' : 'PASS', status: row.status, student_name: row.student_name, project_name: row.project_name, certificate_hash: row.certificate_hash, stored_hash: row.certificate_hash, uploaded_hash: isTampered ? '0'.repeat(64) : row.certificate_hash, receipt_id: row.receipt_id, receipt_exists: Boolean(row.receipt_id), hash_match: !isTampered && row.status !== 'REVOKED' })
  }
  const form = new FormData()
  form.append('file', file)
  return await request.post(`/verification/${encodeURIComponent(certificateNo)}/file`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
}
