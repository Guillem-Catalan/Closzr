import type { Period, RepStatRow } from "../../data/useRepStats";

type Props = {
  email: string;
  name: string;
  stats: RepStatRow[];
  period: Period;
  onBack: () => void;
  onPeriodChange: (p: Period) => void;
};

export default function RepDetail({ email, name, onBack }: Props) {
  return (
    <div>
      <button onClick={onBack} style={{
        background: "none", border: "none", cursor: "pointer", color: "var(--ink-3)",
        fontSize: 13, display: "flex", alignItems: "center", gap: 6, padding: 0, marginBottom: 16,
      }}>
        ← Back to overview
      </button>
      <h2 style={{ fontSize: 20, fontWeight: 700, color: "var(--ink-1)", margin: 0 }}>{name}</h2>
      <p style={{ color: "var(--ink-3)", fontSize: 13, marginTop: 4 }}>{email}</p>
      <p style={{ color: "var(--ink-3)", marginTop: 24 }}>Detail cards coming next...</p>
    </div>
  );
}
