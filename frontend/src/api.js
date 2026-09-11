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
    throw new Error(detail || `Request failed (${res.status})`)
  }
  return res.json()
}

export function fetchBoard(days, signal) {
  return fetch(`/api/board?days=${days}`, { signal }).then(json)
}

export function fetchMetrics(signal) {
  return fetch('/api/metrics', { signal }).then(json)
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
