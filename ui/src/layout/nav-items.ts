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
      { key: "alerts", label: "Alerts", icon: "alert", slug: "todos" },
      { key: "pipeline", label: "Pipeline", icon: "layers", slug: "deals" },
      { key: "benchmark", label: "Benchmark", icon: "trendUp", slug: "benchmark" },
      { key: "performance", label: "Performance", icon: "award", slug: "performance", soon: true },
    ],
  },
  {
    key: "team",
    label: "Team",
    icon: "users",
    children: [
      { key: "forecast", label: "Forecast", icon: "target", slug: "forecast" },
      { key: "oneone", label: "1:1", icon: "message", slug: "oneone" },
      { key: "analytics", label: "Analytics", icon: "trendUp", slug: "team-analytics", soon: true },
      { key: "orgchart", label: "Orgchart", icon: "users", slug: "orgchart" },
    ],
  },
  {
    key: "product",
    label: "Product",
    icon: "sparkle",
    children: [
      { key: "uplift", label: "Uplift", icon: "sparkle", slug: "uplift", soon: true },
      { key: "insights", label: "Insights", icon: "book", slug: "insights", soon: true },
    ],
  },
  {
    key: "partners",
    label: "Partners",
    icon: "building",
    children: [
      { key: "partner-pipeline", label: "Pipeline", icon: "layers", slug: "partner-pipeline", soon: true },
      { key: "partner-forecast", label: "Forecast", icon: "target", slug: "partner-forecast", soon: true },
      { key: "partner-analytics", label: "Analytics", icon: "trendUp", slug: "partner-analytics", soon: true },
    ],
  },
];
