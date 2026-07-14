export function camelize(value: unknown): any {
  if (Array.isArray(value)) return value.map(camelize)
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase()), camelize(item)]))
  return value
}
export function snakeize(value: unknown): any {
  if (Array.isArray(value)) return value.map(snakeize)
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`), snakeize(item)]))
  return value
}