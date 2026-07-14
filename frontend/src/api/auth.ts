import request from '@/utils/request'
import type { Role, UserInfo } from '@/types'
import { useMock, wait } from './mock'
import { camelize } from './helpers'
export async function loginApi(username: string, password: string): Promise<{ token: string; user: UserInfo }> {
  if (useMock) {
    await wait(300)
    if (!['admin', 'teacher', 'auditor'].includes(username) || password !== '123456') throw new Error('用户名或密码错误')
    const role = ({ admin: 'ADMIN', teacher: 'TEACHER', auditor: 'AUDITOR' } as Record<string, Role>)[username]
    return { token: `mock-${role.toLowerCase()}-token`, user: { id: 1, username, displayName: role === 'ADMIN' ? '系统管理员' : role === 'TEACHER' ? '实训教师' : '审计员', role } }
  }
  const data = camelize(await request.post('/auth/login', { username, password }))
  return { token: data.token, user: { id: data.userId || 0, username, displayName: data.displayName, role: data.role } }
}