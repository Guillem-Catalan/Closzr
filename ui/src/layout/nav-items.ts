export type NavSubItem = {
  key: string;
  label: string;
  icon: string;
  slug: string;
  soon?: boolean;
};

export type NavItem = {
  key: string;
  label: string;
  icon: string;
  slug?: string;
  soon?: boolean;
  children?: NavSubItem[];
};

export const NAV_ITEMS: NavItem[] = [
  { key: "general", label: "General", icon: "compass", slug: "general", soon: true },
  {
    key: "execution",
    label: "Execution",
    icon: "route",
    children: [
      { key: "todos", label: "To Do's", icon: "check", slug: "todos" },
      { key: "pipeline", label: "Pipeline", icon: "layers", slug: "deals" },
      { key: "benchmark", label: "Benchmark", icon: "trendUp", slug: "benchmark" },
      { key: "alerts", label: "Alerts", icon: "alert", slug: "alerts", soon: true },
    ],
  },
  {
    key: "team",
    label: "Team",
    icon: "users",
    children: [
      { key: "forecast", label: "Forecast", icon: "target", slug: "forecast" },
      { key: "oneone", label: "1:1", icon: "message", slug: "oneone" },
      { key: "uplift", label: "Uplift", icon: "sparkle", slug: "uplift", soon: true },
    ],
  },
];
