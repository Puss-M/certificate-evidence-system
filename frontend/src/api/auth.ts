import request from '@/utils/request'
import type { Role, UserInfo } from '@/types'
import { useMock, wait } from './mock'
import { camelize, snakeize } from './helpers'
export interface InvitationRegistration { invitationToken: string; username: string; displayName: string; password: string }
export interface ManagedUser { userId: number; username: string; displayName: string; role: Role; isActive: boolean; createdAt: string }
export interface TeacherInvitation { invitationToken: string; role: 'TEACHER'; expiresAt: string }

function toLoginResult(data: Record<string, unknown>): { token: string; user: UserInfo } {
  return { token: String(data.token), user: { id: Number(data.userId || 0), username: String(data.username), displayName: String(data.displayName), role: data.role as Role } }
}

export async function loginApi(username: string, password: string): Promise<{ token: string; user: UserInfo }> {
  if (useMock) {
    await wait(300)
    if (!['admin', 'teacher', 'auditor'].includes(username) || password !== '123456') throw new Error('用户名或密码错误')
    const role = ({ admin: 'ADMIN', teacher: 'TEACHER', auditor: 'AUDITOR' } as Record<string, Role>)[username]
    return { token: `mock-${role.toLowerCase()}-token`, user: { id: 1, username, displayName: role === 'ADMIN' ? '系统管理员' : role === 'TEACHER' ? '实训教师' : '审计员', role } }
  }
  const data = camelize(await request.post('/auth/login', { username, password })) as Record<string, unknown>
  return toLoginResult(data)
}

export async function logoutApi(): Promise<void> {
  if (!useMock) await request.post('/auth/logout')
}

export async function registerInvitationApi(payload: InvitationRegistration): Promise<{ token: string; user: UserInfo }> {
  if (useMock) throw new Error('Mock 模式不支持邀请注册')
  const data = camelize(await request.post('/auth/register/invitation', snakeize(payload))) as Record<string, unknown>
  return toLoginResult(data)
}

export async function getManagedUsers(): Promise<ManagedUser[]> {
  if (useMock) return []
  return camelize(await request.get('/admin/users')) as ManagedUser[]
}

export async function updateManagedUserStatus(userId: number, isActive: boolean): Promise<ManagedUser> {
  return camelize(await request.patch(`/admin/users/${userId}/status`, { is_active: isActive })) as ManagedUser
}

export async function createTeacherInvitation(expiresInHours: number): Promise<TeacherInvitation> {
  return camelize(await request.post('/admin/invitations', { expires_in_hours: expiresInHours })) as TeacherInvitation
}
