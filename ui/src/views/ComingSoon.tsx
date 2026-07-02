import { Icon } from "./components";

export default function ComingSoon({ label }: { label?: string }) {
  return (
    <div className="cz-soon">
      <div className="cz-soon-icon">
        <Icon name="sparkle" size={28} />
      </div>
      <h3>{label ?? "Coming Soon"}</h3>
      <p>We're working on this. Stay tuned.</p>
    </div>
  );
}
