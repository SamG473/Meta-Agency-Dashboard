import { WINDOWS } from '../reportingWindow.js'

export default function WindowSelector({ days, onChange }) {
  return (
    <div className="windows" role="group" aria-label="Reporting window">
      {WINDOWS.map((w) => (
        <button
          key={w.days}
          type="button"
          className="windows__btn"
          aria-pressed={days === w.days}
          onClick={() => onChange(w.days)}
        >
          {w.label}
        </button>
      ))}
    </div>
  )
}
