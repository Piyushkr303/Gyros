import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { GlassPanel } from "../../components/common/GlassPanel";
import { StatTile } from "../../components/common/StatTile";
import { useReviewStore } from "../../store/reviewStore";

const SEVERITY_COLOR: Record<string, string> = {
  CRITICAL: "#f87171",
  HIGH: "#fb923c",
  MEDIUM: "#facc15",
  LOW: "#5eead4",
};

export function MetricsPage() {
  const agents = useReviewStore((s) => s.agents);
  const findings = useReviewStore((s) => s.findings);
  const edges = useReviewStore((s) => s.edges);
  const events = useReviewStore((s) => s.events);

  const stats = useMemo(() => {
    const findingList = Object.values(findings);
    const agentList = Object.values(agents);

    const durationData = agentList
      .filter((a) => a.durationMs !== undefined)
      .map((a) => ({ agent: a.id, ms: a.durationMs ?? 0 }));

    const severityCounts = new Map<string, number>();
    for (const f of findingList) severityCounts.set(f.severity, (severityCounts.get(f.severity) ?? 0) + 1);
    const severityData = Array.from(severityCounts.entries()).map(([severity, count]) => ({ severity, count }));

    const findingsByAgent = new Map<string, number>();
    for (const f of findingList) findingsByAgent.set(f.detecting_agent, (findingsByAgent.get(f.detecting_agent) ?? 0) + 1);
    const findingsByAgentData = Array.from(findingsByAgent.entries()).map(([agent, count]) => ({ agent, count }));

    const edgeList = Object.values(edges);
    const passed = edgeList.filter((e) => e.state === "passed").length;
    const failed = edgeList.filter((e) => e.state === "failed").length;
    const skipped = edgeList.filter((e) => e.state === "skipped" || e.state === "idle").length;

    const totalMs =
      events.length >= 2
        ? new Date(events[events.length - 1].timestamp).getTime() - new Date(events[0].timestamp).getTime()
        : 0;

    return { durationData, severityData, findingsByAgentData, passed, failed, skipped, totalMs, edgeTotal: edgeList.length };
  }, [agents, findings, edges, events]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Review Elapsed" value={`${(stats.totalMs / 1000).toFixed(1)}s`} accent="accent" />
        <StatTile label="Edges Passed" value={`${stats.passed} / ${stats.edgeTotal}`} accent="ok" />
        <StatTile label="Edges Failed" value={stats.failed} accent="danger" />
        <StatTile label="Edges Idle/Skipped" value={stats.skipped} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <GlassPanel title="Agent Duration" subtitle="ms per agent run">
          <div className="h-56">
            {stats.durationData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={stats.durationData}>
                  <CartesianGrid stroke="#1c2333" strokeDasharray="3 3" />
                  <XAxis dataKey="agent" tick={{ fontSize: 10, fill: "#64748b" }} interval={0} angle={-20} textAnchor="end" height={50} />
                  <YAxis tick={{ fontSize: 10, fill: "#64748b" }} />
                  <Tooltip contentStyle={{ background: "#0b0f1a", border: "1px solid #1c2333", fontSize: 12 }} />
                  <Bar dataKey="ms" fill="#818cf8" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-xs text-mission-muted">No completed agent runs yet.</p>
            )}
          </div>
        </GlassPanel>

        <GlassPanel title="Findings by Severity">
          <div className="h-56">
            {stats.severityData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={stats.severityData} dataKey="count" nameKey="severity" outerRadius={80} label>
                    {stats.severityData.map((entry) => (
                      <Cell key={entry.severity} fill={SEVERITY_COLOR[entry.severity] ?? "#94a3b8"} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#0b0f1a", border: "1px solid #1c2333", fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-xs text-mission-muted">No findings yet.</p>
            )}
          </div>
        </GlassPanel>

        <GlassPanel title="Findings by Detecting Agent" className="lg:col-span-2">
          <div className="h-56">
            {stats.findingsByAgentData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={stats.findingsByAgentData}>
                  <CartesianGrid stroke="#1c2333" strokeDasharray="3 3" />
                  <XAxis dataKey="agent" tick={{ fontSize: 10, fill: "#64748b" }} interval={0} angle={-20} textAnchor="end" height={50} />
                  <YAxis tick={{ fontSize: 10, fill: "#64748b" }} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: "#0b0f1a", border: "1px solid #1c2333", fontSize: 12 }} />
                  <Bar dataKey="count" fill="#5eead4" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-xs text-mission-muted">No findings yet.</p>
            )}
          </div>
        </GlassPanel>
      </div>
    </div>
  );
}
