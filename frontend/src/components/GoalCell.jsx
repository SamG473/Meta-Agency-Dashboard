import { useState } from 'react'
import { saveTarget } from '../api.js'

/* Which metric this client is measured on. Writes the whole record, because
   the goal and its target are one setting — changing the metric without the
   target would leave a number in the wrong units. */
export default function GoalCell({ account, metrics, onSaved }) {
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  async function choose(event) {
    const next = event.target.value
    if (next === account.goal_metric) {
      setEditing(false)
      return
    }
    setSaving(true)
    setError(null)
    try {
      await saveTarget(account.account_id, {
        clientName: account.client_name === account.account_id ? null : account.client_name,
        goalMetric: next,
        // The old target belonged to the old metric's units, so it is cleared
        // rather than silently reinterpreted as a value in the new metric.
        targetValue: null,
      })
      setEditing(false)
      onSaved?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (!editing) {
    return (
      <button
        type="button"
        className="goal__btn"
        onClick={() => setEditing(true)}
        aria-label={`Change the goal metric for ${account.client_name}, currently ${account.goal_label}`}
      >
        {account.goal_label}
      </button>
    )
  }

  return (
    <span className="goal__form">
      <label className="visually-hidden" htmlFor={`goal-${account.account_id}`}>
        Goal metric for {account.client_name}
      </label>
      <select
        id={`goal-${account.account_id}`}
        className="goal__select"
        defaultValue={account.goal_metric}
        disabled={saving}
        onChange={choose}
        onBlur={() => setEditing(false)}
        onKeyDown={(e) => e.key === 'Escape' && setEditing(false)}
      >
        {metrics.map((m) => (
          <option key={m.key} value={m.key}>
            {m.label}
          </option>
        ))}
      </select>
      {error && (
        <span role="alert" className="target__error">
          {error}
        </span>
      )}
    </span>
  )
}
