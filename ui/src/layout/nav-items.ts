export type NavItem = {
  key: string;
  label: string;
  icon: string;
  slug: string;
  soon?: boolean;
};

export type NavGroup = {
  title?: string;
  items: NavItem[];
};

export const NAV_GROUPS: NavGroup[] = [
  {
    items: [
      { key: "general", label: "General", icon: "compass", slug: "general", soon: true },
    ],
  },
  {
    title: "Execution",
    items: [
      { key: "todos", label: "To Do's", icon: "check", slug: "todos" },
      { key: "pipeline", label: "Pipeline", icon: "layers", slug: "deals" },
      { key: "benchmark", label: "Benchmark", icon: "trendUp", slug: "benchmark", soon: true },
      { key: "alerts", label: "Alerts", icon: "alert", slug: "alerts", soon: true },
    ],
  },
  {
    title: "Strategy",
    items: [
      { key: "forecast", label: "Forecast", icon: "target", slug: "forecast" },
      { key: "oneone", label: "1:1", icon: "users", slug: "oneone" },
      { key: "uplift", label: "Uplift", icon: "sparkle", slug: "uplift", soon: true },
    ],
  },
];
