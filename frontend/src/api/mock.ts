import type { AuditLog, Batch, Certificate, ChainRecord, PageQuery, PageResult, Project, Student, Template } from '@/types'
export const useMock = import.meta.env.VITE_USE_MOCK === 'true'
export const wait = (ms = 180) => new Promise(resolve => setTimeout(resolve, ms))
export function pageOf<T>(records: T[], query: PageQuery): PageResult<T> {
  const keyword = String(query.keyword || '').toLowerCase()
  const status = String(query.status || '')
  const filtered = records.filter(item => {
    const text = JSON.stringify(item).toLowerCase()
    const record = item as Record<string, unknown>
    const rowStatus = String(record.status || ('enabled' in record ? (record.enabled ? 'ENABLED' : 'DISABLED') : ''))
    const extrasMatch = Object.entries(query).every(([key, expected]) => ['current','size','keyword','status'].includes(key) || !expected || String(record[key] ?? '') === String(expected))
    return (!keyword || text.includes(keyword)) && (!status || rowStatus === status) && extrasMatch
  })
  const start = (query.current - 1) * query.size
  return { records: filtered.slice(start, start + query.size), total: filtered.length, current: query.current, size: query.size }
}
export const projects: Project[] = [
  { id: 1, name: '2026暑期软件开发实训', teacher: '张老师', startDate: '2026-07-01', endDate: '2026-07-14', status: 'ACTIVE' },
  { id: 2, name: 'Vue前端工程化实训', teacher: '刘老师', startDate: '2026-06-10', endDate: '2026-06-24', status: 'COMPLETED' }
]
export const students: Student[] = [
  { student_id: 1, student_no: 'S20260001', student_name: '张三', college: '示范学院', major: '软件工程', class_name: '软件工程2401' },
  { student_id: 2, student_no: 'S20260002', student_name: '李四', college: '示范学院', major: '软件工程', class_name: '软件工程2401' },
  { student_id: 3, student_no: 'S20260003', student_name: '王五', college: '示范学院', major: '计算机科学', class_name: '计算机2401' },
  { student_id: 4, student_no: 'S20260004', student_name: '赵六', college: '信息工程学院', major: '网络工程', class_name: '网络工程2401' },
  { student_id: 5, student_no: 'S20260005', student_name: '陈晨', college: '信息工程学院', major: '数据科学', class_name: '数据科学2401' },
  { student_id: 6, student_no: 'S20260006', student_name: '周敏', college: '人工智能学院', major: '人工智能', class_name: '人工智能2401' },
  { student_id: 7, student_no: 'S20260007', student_name: '吴迪', college: '示范学院', major: '软件工程', class_name: '软件工程2402' },
  { student_id: 8, student_no: 'S20260008', student_name: '郑楠', college: '数字媒体学院', major: '数字媒体技术', class_name: '数字媒体2401' },
  { student_id: 9, student_no: 'S20260009', student_name: '孙悦', college: '信息工程学院', major: '物联网工程', class_name: '物联网2401' },
  { student_id: 10, student_no: 'S20260010', student_name: '林浩', college: '人工智能学院', major: '智能科学', class_name: '智能科学2401' }
]
export const templates: Template[] = [
  { template_id: 1, name: '暑期实训结业证书', issuer: '示范学院', course_name: '软件开发综合实训', project_name: '2026暑期软件开发实训', certificate_title: '实训结业证书', content: '该生已完成规定的实训课程，考核合格，特发此证。', issue_year: '2026', fields: ['student_name','certificate_no','grade_level','mentor_signature','issue_date','qr_code'], enabled: true, updated_at: '2026-07-13 10:20' },
  { template_id: 2, name: '竞赛获奖证明', issuer: '创新创业中心', course_name: '创新创业实践', project_name: '大学生创新竞赛', certificate_title: '获奖证明', content: '该生在本次竞赛中表现优异，特此证明。', issue_year: '2026', fields: ['student_name','certificate_no','grade_level','issue_date','qr_code'], enabled: true, updated_at: '2026-07-12 09:10' },
  { template_id: 3, name: '前端工程实训证书', issuer: '信息工程学院', course_name: 'Vue 3 前端开发', project_name: 'Vue前端工程化实训', certificate_title: '前端工程实训证书', content: '该生已完成前端工程化实训任务并通过考核，特发此证。', issue_year: '2026', fields: ['student_name','certificate_no','issue_date','mentor_signature','qr_code'], enabled: true, updated_at: '2026-07-14 09:30' },
  { template_id: 4, name: '人工智能实践证明', issuer: '人工智能学院', course_name: '机器学习实践', project_name: '人工智能应用实训', certificate_title: '实践结业证明', content: '该生已完成机器学习实践课程，成绩合格。', issue_year: '2026', fields: ['student_name','certificate_no','grade_level','issue_date','qr_code'], enabled: false, updated_at: '2026-07-14 08:45' },
  { template_id: 5, name: '数据分析实训证书', issuer: '信息工程学院', course_name: '数据分析综合实践', project_name: '数据分析应用实训', certificate_title: '数据分析实训证书', content: '该生已完成数据分析综合实践并通过项目验收。', issue_year: '2026', fields: ['student_name','certificate_no','issue_date','qr_code'], enabled: true, updated_at: '2026-07-13 16:20' }
]
export const batches: Batch[] = [
  { batch_id: 1, batch_no: 'BATCH-202607-001', batch_name: '2026暑期实训第一批', project_name: '2026暑期软件开发实训', template_id: 1, student_count: 3, generated: 3, evidenced: 2, status: 'GENERATED' },
  { batch_id: 2, batch_no: 'BATCH-202607-002', batch_name: '前端实训结业批次', project_name: 'Vue前端工程化实训', template_id: 1, student_count: 2, generated: 2, evidenced: 2, status: 'COMPLETED' },
  { batch_id: 3, batch_no: 'BATCH-202607-003', batch_name: '软件工程实训第二批', project_name: '2026暑期软件开发实训', template_id: 1, student_count: 3, generated: 3, evidenced: 2, status: 'GENERATED' },
  { batch_id: 4, batch_no: 'BATCH-202607-004', batch_name: '人工智能实训预备批次', project_name: '人工智能应用实训', template_id: 4, student_count: 2, generated: 0, evidenced: 0, status: 'DRAFT' },
  { batch_id: 5, batch_no: 'BATCH-202607-005', batch_name: '数据分析实训第一批', project_name: '数据分析应用实训', template_id: 5, student_count: 2, generated: 2, evidenced: 1, status: 'GENERATED' },
  { batch_id: 6, batch_no: 'BATCH-202607-006', batch_name: '前端实训补发批次', project_name: 'Vue前端工程化实训', template_id: 3, student_count: 1, generated: 1, evidenced: 1, status: 'COMPLETED' }
]
export const certificates: Certificate[] = [
  { certificate_id: 1, certificate_no: 'CERT-20260713-0001', student_id: 1, student_no: 'S20260001', student_name: '张三', batch_id: 1, template_id: 1, pdf_path: '/mock/certificates/CERT-20260713-0001.pdf', certificate_hash: 'a472c36f998d2bc91cb6a871ca187bc438bf19b99351e9051d298f321f8092aa', qr_code_path: '/mock/qrcodes/CERT-20260713-0001.png', verify_url: '/public/verify/CERT-20260713-0001', receipt_id: 'RCP-20260713-0001', status: 'VALID', credential_type: 'CERTIFICATE', root_id: '', project_name: '2026暑期软件开发实训', issue_date: '2026-07-13', evidence_status: 'CONFIRMED' },
  { certificate_id: 2, certificate_no: 'CERT-20260713-0002', student_id: 2, student_no: 'S20260002', student_name: '李四', batch_id: 1, template_id: 1, pdf_path: '/mock/certificates/CERT-20260713-0002.pdf', certificate_hash: '164d93b6cc447dadcf987ab34ca2cb199e3bc17c3d2eb44d7fae8d012f2e1c54', qr_code_path: '/mock/qrcodes/CERT-20260713-0002.png', verify_url: '/public/verify/CERT-20260713-0002', receipt_id: '', status: 'VALID', credential_type: 'CERTIFICATE', root_id: '', project_name: '2026暑期软件开发实训', issue_date: '2026-07-13', evidence_status: 'PENDING' },
  { certificate_id: 3, certificate_no: 'CERT-20260710-0003', student_id: 3, student_no: 'S20260003', student_name: '王五', batch_id: 2, template_id: 1, pdf_path: '/mock/certificates/CERT-20260710-0003.pdf', certificate_hash: '9b22d65dace680fa30ba4558bda39360a662460d209bc86ae7db745582e4a77f', qr_code_path: '/mock/qrcodes/CERT-20260710-0003.png', verify_url: '/public/verify/CERT-20260710-0003', receipt_id: 'RCP-20260713-0002', status: 'REVOKED', credential_type: 'CERTIFICATE', root_id: '', project_name: 'Vue前端工程化实训', issue_date: '2026-07-10', evidence_status: 'CONFIRMED', new_certificate_no: 'CERT-20260713-0004' },
  { certificate_id: 4, certificate_no: 'CERT-20260714-0004', student_id: 4, student_no: 'S20260004', student_name: '赵六', batch_id: 3, template_id: 1, pdf_path: '/mock/certificates/CERT-20260714-0004.pdf', certificate_hash: '42b781c3846cf12ac650fa205ba49de20cb87c5350f73afbc94910f8763cc472', qr_code_path: '/mock/qrcodes/CERT-20260714-0004.png', verify_url: '/public/verify/CERT-20260714-0004', receipt_id: 'RCP-20260714-0003', status: 'VALID', credential_type: 'CERTIFICATE', root_id: '', project_name: '2026暑期软件开发实训', issue_date: '2026-07-14', evidence_status: 'CONFIRMED' },
  { certificate_id: 5, certificate_no: 'CERT-20260714-0005', student_id: 5, student_no: 'S20260005', student_name: '陈晨', batch_id: 5, template_id: 5, pdf_path: '/mock/certificates/CERT-20260714-0005.pdf', certificate_hash: '57f2023b90e8fb0a291124ebbaeaa9c6d4894820aef58d1771cc056e903e6498', qr_code_path: '/mock/qrcodes/CERT-20260714-0005.png', verify_url: '/public/verify/CERT-20260714-0005', receipt_id: '', status: 'VALID', credential_type: 'CERTIFICATE', root_id: '', project_name: '数据分析应用实训', issue_date: '2026-07-14', evidence_status: 'PENDING' },
  { certificate_id: 6, certificate_no: 'CERT-20260714-0006', student_id: 6, student_no: 'S20260006', student_name: '周敏', batch_id: 4, template_id: 4, pdf_path: '', certificate_hash: '', qr_code_path: '', verify_url: '', receipt_id: '', status: 'DRAFT', credential_type: 'CERTIFICATE', root_id: '', project_name: '人工智能应用实训', issue_date: '2026-07-14', evidence_status: 'PENDING' },
  { certificate_id: 7, certificate_no: 'CERT-20260714-0007', student_id: 7, student_no: 'S20260007', student_name: '吴迪', batch_id: 3, template_id: 1, pdf_path: '/mock/certificates/CERT-20260714-0007.pdf', certificate_hash: '86eb9c1500d89ff7024c09542a569b923c3d3d68c5f315686da792acbe2d1b49', qr_code_path: '/mock/qrcodes/CERT-20260714-0007.png', verify_url: '/public/verify/CERT-20260714-0007', receipt_id: 'RCP-20260714-0004', status: 'VALID', credential_type: 'CERTIFICATE', root_id: '', project_name: '2026暑期软件开发实训', issue_date: '2026-07-14', evidence_status: 'CONFIRMED' },
  { certificate_id: 8, certificate_no: 'CERT-20260714-0008', student_id: 8, student_no: 'S20260008', student_name: '郑楠', batch_id: 2, template_id: 3, pdf_path: '/mock/certificates/CERT-20260714-0008.pdf', certificate_hash: '936a876cf05d43fb240f5e033e35ebba4a101af21fe70fc552ed2bc6b8005997', qr_code_path: '/mock/qrcodes/CERT-20260714-0008.png', verify_url: '/public/verify/CERT-20260714-0008', receipt_id: 'RCP-20260714-0005', status: 'VALID', credential_type: 'CERTIFICATE', root_id: '', project_name: 'Vue前端工程化实训', issue_date: '2026-07-14', evidence_status: 'CONFIRMED' },
  { certificate_id: 9, certificate_no: 'CERT-20260714-0009', student_id: 9, student_no: 'S20260009', student_name: '孙悦', batch_id: 5, template_id: 5, pdf_path: '/mock/certificates/CERT-20260714-0009.pdf', certificate_hash: 'ab12d24df9345c9177459503c671fd3cb8bdc2a6bed7dc05bdf3664233fe23cc', qr_code_path: '/mock/qrcodes/CERT-20260714-0009.png', verify_url: '/public/verify/CERT-20260714-0009', receipt_id: '', status: 'VALID', credential_type: 'CERTIFICATE', root_id: '', project_name: '数据分析应用实训', issue_date: '2026-07-14', evidence_status: 'PENDING' },
  { certificate_id: 10, certificate_no: 'CERT-20260714-0010', student_id: 10, student_no: 'S20260010', student_name: '林浩', batch_id: 3, template_id: 1, pdf_path: '/mock/certificates/CERT-20260714-0010.pdf', certificate_hash: 'ccf4d9eb2ea348f58b09dc381d45ce63fa26b83ee284d297b70cfcbc4971165e', qr_code_path: '/mock/qrcodes/CERT-20260714-0010.png', verify_url: '/public/verify/CERT-20260714-0010', receipt_id: '', status: 'VALID', credential_type: 'CERTIFICATE', root_id: '', project_name: '2026暑期软件开发实训', issue_date: '2026-07-14', evidence_status: 'PENDING' }
]
export const receipts: ChainRecord[] = [
  { receipt_id: 'RCP-20260713-0001', certificate_id: 1, certificate_no: 'CERT-20260713-0001', certificate_hash: 'a472c36f998d2bc91cb6a871ca187bc438bf19b99351e9051d298f321f8092aa', evidence_type: 'LOCAL_HASH_CHAIN', previous_hash: '0'.repeat(64), current_block_hash: '825dba91d72bd9ce6956fe913b629e6e3a28b89d8f8d829c8f25fe2d783aa421', block_height: 1, evidence_time: '2026-07-13 12:00:00', status: 'CONFIRMED' },
  { receipt_id: 'RCP-20260713-0002', certificate_id: 3, certificate_no: 'CERT-20260710-0003', certificate_hash: '164d93b6cc447dadcf987ab34ca2cb199e3bc17c3d2eb44d7fae8d012f2e1c54', evidence_type: 'FISCO_BCOS', block_height: 128633, tx_hash: '0x72ab903dd8e8a8271c05db9d900c612d4b02859cd8577be415cf7b7ac91fc112', contract_address: '0x9c21aeb911c605ac983b99a1a82d7c69b7110001', evidence_time: '2026-07-13 12:01:10', status: 'CONFIRMED' }
]
export const auditLogs: AuditLog[] = [
  { id: 1, operator: 'admin', action: '证书存证', module: '可信存证', target: 'CERT-20260713-0001', result: 'SUCCESS', createdAt: '2026-07-13 12:00:00' },
  { id: 2, operator: 'teacher01', action: '批量签发', module: '证书管理', target: 'BATCH-202607-001', result: 'SUCCESS', createdAt: '2026-07-13 11:58:03' }
]