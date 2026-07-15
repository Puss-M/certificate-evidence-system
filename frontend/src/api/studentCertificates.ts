import request from '@/utils/request'
import type { Certificate } from '@/types'
import { certificates, useMock, wait } from './mock'

const apiBase = import.meta.env.VITE_API_BASE_URL || '/api'

function rememberStudentNo(studentNo: string) {
  localStorage.setItem('certificate_student_no', studentNo)
}

export function getSavedStudentNo() {
  return localStorage.getItem('certificate_student_no') || 'S20260001'
}

export async function getMyCertificates(studentNo: string): Promise<Certificate[]> {
  rememberStudentNo(studentNo)
  if (useMock) {
    await wait()
    return certificates.filter(item => item.student_no === studentNo)
  }
  return await request.get('/student/certificates', { params: { student_no: studentNo } })
}

export async function getStudentCertificateDetail(certificateNo: string, studentNo: string): Promise<Certificate> {
  rememberStudentNo(studentNo)
  if (useMock) {
    await wait()
    const row = certificates.find(item => item.certificate_no === certificateNo && item.student_no === studentNo)
    if (!row) throw new Error('未找到该学生的证书')
    return row
  }
  return await request.get(`/student/certificates/${encodeURIComponent(certificateNo)}`, { params: { student_no: studentNo } })
}

export function buildStudentDownloadUrl(certificateNo: string, studentNo: string) {
  return `${apiBase}/student/certificates/${encodeURIComponent(certificateNo)}/download?student_no=${encodeURIComponent(studentNo)}`
}

export function buildStudentQrCodeUrl(certificateNo: string, studentNo: string) {
  if (useMock) return ''
  return `${apiBase}/student/certificates/${encodeURIComponent(certificateNo)}/qrcode?student_no=${encodeURIComponent(studentNo)}`
}
