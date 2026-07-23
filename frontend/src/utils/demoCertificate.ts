import type { Certificate } from '@/types'

function escapePdfText(value: string) {
  return value.replace(/[^\x20-\x7e]/g, ' ').replace(/\\/g, '\\\\').replace(/\(/g, '\\(').replace(/\)/g, '\\)')
}

function makePdf(lines: string[]) {
  const content = [
    'BT',
    '/F1 22 Tf',
    '72 760 Td',
    '(Training Certificate) Tj',
    '/F1 12 Tf',
    ...lines.flatMap((line, index) => [`0 ${index === 0 ? -42 : -24} Td`, `(${escapePdfText(line)}) Tj`]),
    'ET',
  ].join('\n')
  const objects = [
    '1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n',
    '2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n',
    '3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n',
    '4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n',
    `5 0 obj\n<< /Length ${content.length} >>\nstream\n${content}\nendstream\nendobj\n`,
  ]
  let offset = '%PDF-1.4\n'.length
  const xref = objects.map(object => {
    const current = offset
    offset += object.length
    return current
  })
  const body = objects.join('')
  const xrefStart = '%PDF-1.4\n'.length + body.length
  const table = [
    'xref',
    `0 ${objects.length + 1}`,
    '0000000000 65535 f ',
    ...xref.map(item => `${String(item).padStart(10, '0')} 00000 n `),
    'trailer',
    `<< /Size ${objects.length + 1} /Root 1 0 R >>`,
    'startxref',
    String(xrefStart),
    '%%EOF',
  ].join('\n')
  return `%PDF-1.4\n${body}${table}`
}

export function downloadDemoCertificatePdf(certificate: Certificate, verifyLink: string) {
  const pdf = makePdf([
    `Certificate No: ${certificate.certificate_no}`,
    `Student: ${certificate.student_name} (${certificate.student_no})`,
    `Project: ${certificate.project_name}`,
    `Issue Date: ${certificate.issue_date || '-'}`,
    `Status: ${certificate.status}`,
    `Receipt: ${certificate.receipt_id || 'NO_RECEIPT'}`,
    `SHA-256: ${certificate.certificate_hash || '-'}`,
    `Verify: ${verifyLink}`,
  ])
  const blob = new Blob([pdf], { type: 'application/pdf' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${certificate.certificate_no}.pdf`
  link.click()
  URL.revokeObjectURL(url)
}

export function downloadDataUrl(dataUrl: string, filename: string) {
  const link = document.createElement('a')
  link.href = dataUrl
  link.download = filename
  link.click()
}
