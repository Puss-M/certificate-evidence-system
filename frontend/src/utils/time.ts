export function formatUtcToLocal(value?: string): string {
  if (!value) return '—'

  const normalized = value.includes('T') ? value : value.replace(' ', 'T')
  const hasTimezone = /Z$|[+-]\d{2}:?\d{2}$/.test(normalized)
  const date = new Date(hasTimezone ? normalized : `${normalized}Z`)

  if (Number.isNaN(date.getTime())) return value

  const pad = (part: number) => String(part).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}
