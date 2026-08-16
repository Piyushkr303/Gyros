import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { liveStoreHooks, type ReducerStoreHooks } from "../../store/storeHooks";
import { GlassPanel } from "../common/GlassPanel";
import { StatTile } from "../common/StatTile";

interface Props {
  hooks?: ReducerStoreHooks;
}

export function TokenDashboard({ hooks = liveStoreHooks }: Props = {}) {
  const records = hooks.useTokenRecords();

  const stats = useMemo(() => {
    const totalInput = records.reduce((sum, r) => sum + r.input_tokens, 0);
    const totalOutput = records.reduce((sum, r) => sum + r.output_tokens, 0);
    const avoided = records.filter((r) => r.llm_call_avoided).length;
    const made = records.filter((r) => !r.llm_call_avoided).length;

    const byAgent = new Map<string, number>();
    for (const r of records) {
      byAgent.set(r.agent, (byAgent.get(r.agent) ?? 0) + r.input_tokens + r.output_tokens);
    }
    const chartData = Array.from(byAgent.entries()).map(([agent, tokens]) => ({ agent, tokens }));

    return { totalInput, totalOutput, avoided, made, chartData, total: totalInput + totalOutput };
  }, [records]);

  return (
    <GlassPanel title="Token Dashboard" subtitle="Real usage, never hardcoded">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <StatTile label="Total Tokens" value={stats.total} accent="accent" />
        <StatTile label="Input" value={stats.totalInput} />
        <StatTile label="Output" value={stats.totalOutput} />
        <StatTile label="LLM Calls Avoided" value={stats.avoided} accent="ok" />
      </div>
      <div className="mt-4 h-40">
        {stats.chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={stats.chartData}>
              <CartesianGrid stroke="#1c2333" strokeDasharray="3 3" />
              <XAxis dataKey="agent" tick={{ fontSize: 10, fill: "#64748b" }} interval={0} angle={-20} textAnchor="end" height={50} />
              <YAxis tick={{ fontSize: 10, fill: "#64748b" }} />
              <Tooltip contentStyle={{ background: "#0b0f1a", border: "1px solid #1c2333", fontSize: 12 }} />
              <Bar dataKey="tokens" fill="#5eead4" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-xs text-mission-muted">No token activity yet.</p>
        )}
      </div>
      <p className="mt-2 text-[11px] text-mission-muted">
        {stats.made} real LLM call(s), {stats.avoided} avoided via deterministic tooling.
      </p>
    </GlassPanel>
  );
}
