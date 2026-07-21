import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { supabase } from "../../data/supabase";

export type OrgPerson = {
  email: string;
  full_name: string;
  hs_owner_id: string | null;
  role: string;
  channel: string;
  team_name: string;
  reports_to: string | null;
  hierarchy_level: number;
  is_active: boolean;
  target_mrr: number;
  additional_teams: string[];
};

export type OrgNode = OrgPerson & { children: OrgNode[]; descendantCount: number };

export type OrgGroup = { label: string; roots: OrgNode[] };

export type PendingChange =
  | { type: "move"; email: string; oldReportsTo: string | null; newReportsTo: string; reassignDeals: boolean }
  | { type: "remove"; email: string; reassignTo?: string }
  | { type: "add"; person: Partial<OrgPerson> }
  | { type: "disconnect"; email: string };

function countDescendants(node: OrgNode): number {
  let count = 0;
  for (const child of node.children) {
    count += 1 + countDescendants(child);
  }
  node.descendantCount = count;
  return count;
}

function buildTree(rows: OrgPerson[]): OrgNode[] {
  const map = new Map<string, OrgNode>();
  for (const r of rows) map.set(r.email, { ...r, children: [], descendantCount: 0 });

  const roots: OrgNode[] = [];
  for (const node of map.values()) {
    if (node.reports_to && map.has(node.reports_to)) {
      map.get(node.reports_to)!.children.push(node);
    } else {
      roots.push(node);
    }
  }
  for (const root of roots) countDescendants(root);
  return roots;
}

function collectSubtreeEmails(rows: OrgPerson[], rootEmail: string): Set<string> {
  const childrenOf = new Map<string, string[]>();
  for (const r of rows) {
    if (r.reports_to) {
      if (!childrenOf.has(r.reports_to)) childrenOf.set(r.reports_to, []);
      childrenOf.get(r.reports_to)!.push(r.email);
    }
  }
  const result = new Set<string>();
  result.add(rootEmail);
  const queue = [rootEmail];
  while (queue.length) {
    const email = queue.shift()!;
    for (const child of childrenOf.get(email) || []) {
      if (!result.has(child)) {
        result.add(child);
        queue.push(child);
      }
    }
  }
  return result;
}

function groupRoots(roots: OrgNode[]): OrgGroup[] {
  const buckets: Record<string, OrgNode[]> = {};
  for (const root of roots) {
    let key: string;
    if (root.channel === "direct_sales") key = "Direct Sales";
    else if (root.channel === "partners" && root.team_name.startsWith("Mexico")) key = "Mexico";
    else if (root.channel === "partners") key = "Partners";
    else if (root.channel === "xl") key = "XL";
    else continue;

    if (!buckets[key]) buckets[key] = [];
    buckets[key].push(root);
  }

  const order = ["Direct Sales", "Mexico", "Partners", "XL"];
  return order.filter(k => buckets[k]).map(k => ({ label: k, roots: buckets[k] }));
}

export function useOrgchart(userEmail: string, userRole: string) {
  const [allRows, setAllRows] = useState<OrgPerson[]>([]);
  const [groups, setGroups] = useState<OrgGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<OrgPerson | null>(null);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [pendingChanges, setPendingChanges] = useState<PendingChange[]>([]);
  const [disconnected, setDisconnected] = useState<Set<string>>(new Set());
  const snapshotRef = useRef<OrgPerson[]>([]);

  const isAdmin = userRole === "Admin" || userRole === "Manager";

  const editScope = useMemo(() => {
    if (!allRows.length || !userEmail) return new Set<string>();
    if (isAdmin) return new Set(allRows.map(r => r.email));
    const subtree = collectSubtreeEmails(allRows, userEmail);
    for (const email of disconnected) subtree.add(email);
    return subtree;
  }, [allRows, userEmail, isAdmin, disconnected]);

  const canEdit = editScope.size > 1;

  const rebuildGroups = useCallback((rows: OrgPerson[]) => {
    if (isAdmin) {
      const tree = buildTree(rows);
      setGroups(groupRoots(tree));
    } else {
      const userRow = rows.find(r => r.email === userEmail);
      if (!userRow) {
        setGroups([]);
        return;
      }
      const channelRows = rows.filter(r => r.channel === userRow.channel);
      const tree = buildTree(channelRows);
      setGroups(groupRoots(tree));
    }
  }, [isAdmin, userEmail]);

  useEffect(() => {
    (async () => {
      const { data, error } = await supabase
        .from("orgchart")
        .select("*")
        .order("hierarchy_level");

      if (error || !data) {
        setLoading(false);
        return;
      }

      const rows = data as OrgPerson[];
      setAllRows(rows);
      rebuildGroups(rows);
      setLoading(false);
    })();
  }, [userEmail, userRole, rebuildGroups]);

  const defaultExpanded = useMemo(() => {
    if (isAdmin) return null;
    return editScope;
  }, [isAdmin, editScope]);

  const updatePerson = useCallback(
    async (email: string, changes: Partial<OrgPerson>) => {
      setSaving(true);
      const { error } = await supabase
        .from("orgchart")
        .update(changes)
        .eq("email", email);

      if (!error) {
        setAllRows(prev => {
          const next = prev.map(r => (r.email === email ? { ...r, ...changes } : r));
          rebuildGroups(next);
          if (selected?.email === email) setSelected({ ...selected, ...changes });
          return next;
        });
      }
      setSaving(false);
      return !error;
    },
    [selected, rebuildGroups],
  );

  // ── Edit mode ────────────────────────────────────────────────

  const startEditing = useCallback(() => {
    snapshotRef.current = allRows.map(r => ({ ...r }));
    setEditing(true);
    setPendingChanges([]);
    setDisconnected(new Set());
    setSelected(null);
  }, [allRows]);

  const discardChanges = useCallback(() => {
    setAllRows(snapshotRef.current);
    rebuildGroups(snapshotRef.current);
    setEditing(false);
    setPendingChanges([]);
    setDisconnected(new Set());
  }, [rebuildGroups]);

  const disconnectPerson = useCallback((email: string) => {
    setAllRows(prev => {
      const next = prev.map(r =>
        r.email === email ? { ...r, reports_to: null } : r
      );
      rebuildGroups(next);
      return next;
    });
    setDisconnected(prev => new Set(prev).add(email));
    setPendingChanges(pc => [...pc, { type: "disconnect", email }]);
  }, [rebuildGroups]);

  const disconnectSubtree = useCallback((rootEmail: string) => {
    const emails = collectSubtreeEmails(allRows, rootEmail);
    setDisconnected(prev => {
      const next = new Set(prev);
      for (const e of emails) next.add(e);
      return next;
    });
    setPendingChanges(pc => [...pc, { type: "disconnect", email: rootEmail }]);
  }, [allRows]);

  const reconnectChildren = useCallback((parentEmail: string) => {
    setAllRows(prev => {
      const parent = prev.find(r => r.email === parentEmail);
      const grandparent = parent?.reports_to || null;
      const next = prev.map(r => {
        if (r.email === parentEmail) return { ...r, reports_to: null };
        if (r.reports_to === parentEmail) return { ...r, reports_to: grandparent };
        return r;
      });
      rebuildGroups(next);
      return next;
    });
    setDisconnected(prev => new Set(prev).add(parentEmail));
    setPendingChanges(pc => [...pc, { type: "disconnect", email: parentEmail }]);
  }, [rebuildGroups]);

  const movePerson = useCallback((email: string, newReportsTo: string, reassignDeals = true) => {
    setAllRows(prev => {
      const person = prev.find(r => r.email === email);
      const oldReportsTo = person?.reports_to || null;
      const next = prev.map(r =>
        r.email === email ? { ...r, reports_to: newReportsTo } : r
      );
      rebuildGroups(next);
      setPendingChanges(pc => [
        ...pc,
        { type: "move", email, oldReportsTo, newReportsTo, reassignDeals },
      ]);
      return next;
    });
    setDisconnected(prev => {
      if (!prev.has(email)) return prev;
      const next = new Set(prev);
      next.delete(email);
      return next;
    });
  }, [rebuildGroups]);

  const removePerson = useCallback((email: string, reassignTo?: string) => {
    setAllRows(prev => {
      const next = prev.filter(r => r.email !== email);
      rebuildGroups(next);
      setPendingChanges(pc => [...pc, { type: "remove", email, reassignTo }]);
      return next;
    });
  }, [rebuildGroups]);

  const addPerson = useCallback((person: Partial<OrgPerson>) => {
    setAllRows(prev => {
      const full: OrgPerson = {
        email: person.email || "",
        full_name: person.full_name || "",
        hs_owner_id: person.hs_owner_id || null,
        role: person.role || "AE",
        channel: person.channel || "",
        team_name: person.team_name || "",
        reports_to: person.reports_to || null,
        hierarchy_level: person.hierarchy_level || 99,
        is_active: true,
        target_mrr: person.target_mrr || 0,
        additional_teams: person.additional_teams || [],
      };
      const next = [...prev, full];
      rebuildGroups(next);
      setPendingChanges(pc => [...pc, { type: "add", person: full }]);
      return next;
    });
  }, [rebuildGroups]);

  return {
    groups,
    loading,
    selected,
    setSelected,
    updatePerson,
    saving,
    allRows,
    canEdit,
    editing,
    startEditing,
    discardChanges,
    movePerson,
    removePerson,
    addPerson,
    pendingChanges,
    editScope,
    defaultExpanded,
    disconnected,
    disconnectPerson,
    disconnectSubtree,
    reconnectChildren,
  };
}
