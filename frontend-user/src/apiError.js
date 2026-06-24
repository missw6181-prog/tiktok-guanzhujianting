export function apiError(err, fallback = '操作失败') {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join('；') || fallback
  return err?.response?.data?.error || err?.message || fallback
}
