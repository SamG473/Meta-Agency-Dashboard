/* The dashboard reads only from our own API, which reads only from Postgres.
   Nothing here ever touches Meta. */

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
  return fetch(`/api/board?days=${days}`, { signal }).then(json)
}

export function fetchMetrics(signal) {
  return fetch('/api/metrics', { signal }).then(json)
}

export function fetchConfig(signal) {
  return fetch('/api/config', { signal }).then(json)
}

export function fetchAnalytics(accountId, days, signal) {
  const params = new URLSearchParams({ days: String(days) })
  if (accountId) params.set('account_id', accountId)
  return fetch(`/api/analytics?${params}`, { signal }).then(json)
}

export function saveTarget(accountId, { clientName, goalMetric, targetValue }) {
  return fetch(`/api/targets/${encodeURIComponent(accountId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      client_name: clientName ?? null,
      goal_metric: goalMetric ?? null,
      target_value: targetValue ?? null,
    }),
  }).then(json)
}
