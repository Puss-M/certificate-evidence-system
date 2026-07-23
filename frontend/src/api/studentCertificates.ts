import request from '@/utils/request'
import type { Certificate } from '@/types'
import { certificates, useMock, wait } from './mock'

export async function getMyCertificates(): Promise<Certificate[]> {
  if (useMock) {
    await wait()
    return certificates.filter(item => item.student_no === 'S20260001')
  }
  return await request.get('/student/certificates')
}

export async function getStudentCertificateDetail(certificateNo: string): Promise<Certificate> {
  if (useMock) {
    await wait()
    const row = certificates.find(item => item.certificate_no === certificateNo && item.student_no === 'S20260001')
    if (!row) throw new Error('未找到当前学生的证书')
    return row
  }
  return await request.get(`/student/certificates/${encodeURIComponent(certificateNo)}`)
}

export async function downloadStudentCertificate(certificateNo: string): Promise<Blob> {
  return await request.get(`/student/certificates/${encodeURIComponent(certificateNo)}/download`, { responseType: 'blob' }) as Blob
}

export async function getStudentQrCode(certificateNo: string): Promise<Blob | null> {
  if (useMock) return null
  return await request.get(`/student/certificates/${encodeURIComponent(certificateNo)}/qrcode`, { responseType: 'blob' }) as Blob
}
