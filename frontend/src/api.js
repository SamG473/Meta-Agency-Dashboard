/* The dashboard reads only from our own API, which reads only from Postgres.
   Nothing here ever touches Meta. */

/* Where that API lives. Empty in development, where Vite proxies /api to the
   local uvicorn — so a local run is unchanged by anything below. In production
   the dashboard and the API sit on different hosts, and VITE_API_BASE_URL,
   baked in at build time, names the deployed API. */
const RAW_API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').trim()

/* Render hands one service the address of another as a bare hostname, so a
   missing scheme is the normal case rather than a mistake. Trailing slashes go
   too, because every path below starts with one. */
export const API_BASE = RAW_API_BASE
  ? (/^https?:\/\//i.test(RAW_API_BASE) ? RAW_API_BASE : `https://${RAW_API_BASE}`).replace(
      /\/+$/,
      '',
    )
  : ''

/* True when the API is a separate deployment rather than the dev proxy. The UI
   uses it to explain a slow first load: free hosting sleeps when idle, which
   local development never does. */
export const API_IS_REMOTE = API_BASE !== ''

function apiUrl(path) {
  return `${API_BASE}${path}`
}

async function json(res) {
  if (!res.ok) {
    let detail = ''
    try {
      detail = (await res.json())?.detail ?? ''
    } catch {
      /* response had no JSON body */
    }
    // The status rides along on the error so a caller can tell "you asked for
    // something that isn't here" from "the API is down" and recover differently.
    const error = new Error(detail || `Request failed (${res.status})`)
    error.status = res.status
    throw error
  }
  return res.json()
}

export function fetchBoard(days, signal) {
  return fetch(apiUrl(`/api/board?days=${days}`), { signal }).then(json)
}

export function fetchMetrics(signal) {
  return fetch(apiUrl('/api/metrics'), { signal }).then(json)
}

export function fetchConfig(signal) {
  return fetch(apiUrl('/api/config'), { signal }).then(json)
}

export function fetchAnalytics(accountId, days, signal) {
  const params = new URLSearchParams({ days: String(days) })
  if (accountId) params.set('account_id', accountId)
  return fetch(apiUrl(`/api/analytics?${params}`), { signal }).then(json)
}

export function saveTarget(accountId, { clientName, goalMetric, targetValue }) {
  return fetch(apiUrl(`/api/targets/${encodeURIComponent(accountId)}`), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      client_name: clientName ?? null,
      goal_metric: goalMetric ?? null,
      target_value: targetValue ?? null,
    }),
  }).then(json)
}
