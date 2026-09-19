import { useEffect, useRef, useState } from 'react'
import { metricValue } from '../format.js'
import { saveTarget } from '../api.js'

/* The target value, in the units of this client's own goal metric. Writes to
   our store only — this never reaches Meta, and nothing here can alter a live
   campaign. */
export default function TargetCell({ account, onSaved }) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(account.target_value ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (editing) inputRef.current?.select()
  }, [editing])

  function open() {
    setValue(account.target_value ?? '')
    setError(null)
    setEditing(true)
  }

  async function commit(event) {
    event.preventDefault()
    const trimmed = String(value).trim()
    const parsed = trimmed === '' ? null : Number(trimmed)

    if (parsed !== null && (!Number.isFinite(parsed) || parsed <= 0)) {
      setError('Enter an amount above zero, or clear the field to remove the target.')
      return
    }

    setSaving(true)
    setError(null)
    try {
      await saveTarget(account.account_id, {
        clientName: account.client_name === account.account_id ? null : account.client_name,
        goalMetric: account.goal_metric,
        targetValue: parsed,
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
        className={`target__btn${account.target_value == null ? ' target__btn--empty' : ''}`}
        onClick={open}
        aria-label={
          account.target_value == null
            ? `Set a ${account.goal_label} target for ${account.client_name}`
            : `Change the ${account.goal_label} target for ${account.client_name}, currently ${metricValue(account.target_value, account.goal_unit)}`
        }
      >
        {account.target_value == null
          ? 'Set target'
          : metricValue(account.target_value, account.goal_unit)}
      </button>
    )
  }

  return (
    <form className="target__form" onSubmit={commit}>
      <label className="visually-hidden" htmlFor={`target-${account.account_id}`}>
        {account.goal_label} target for {account.client_name}
      </label>
      <input
        id={`target-${account.account_id}`}
        ref={inputRef}
        className="target__input"
        type="number"
        step="0.01"
        min="0"
        inputMode="decimal"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === 'Escape' && setEditing(false)}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `target-error-${account.account_id}` : undefined}
      />
      <button type="submit" className="target__save" disabled={saving}>
        {saving ? 'Saving' : 'Save'}
      </button>
      <button type="button" className="target__cancel" onClick={() => setEditing(false)}>
        Cancel
      </button>
      {error && (
        <span id={`target-error-${account.account_id}`} role="alert" className="target__error">
          {error}
        </span>
      )}
    </form>
  )
}
