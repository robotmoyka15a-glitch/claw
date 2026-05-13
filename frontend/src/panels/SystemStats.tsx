import { useState } from 'react';
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { SystemSnapshot } from '../api';
import { useWS } from '../hooks/useWS';

interface Point {
  t: number;
  cpu: number;
  ram: number;
  netIn: number;
  netOut: number;
}

export function SystemStats() {
  const [points, setPoints] = useState<Point[]>([]);
  const [latest, setLatest] = useState<SystemSnapshot | null>(null);

  useWS<SystemSnapshot>('/ws/system', (snap) => {
    setLatest(snap);
    setPoints((prev) => {
      const next = [
        ...prev,
        {
          t: Math.round(snap.ts),
          cpu: snap.cpu_percent,
          ram: snap.ram_percent,
          netIn: snap.net_recv_mb,
          netOut: snap.net_sent_mb,
        },
      ];
      return next.slice(-60);
    });
  });

  return (
    <div className="h-full flex flex-col gap-3">
      <div className="grid grid-cols-4 gap-2 text-sm">
        <Stat label="CPU" value={latest ? `${latest.cpu_percent.toFixed(0)}%` : '—'} />
        <Stat
          label="RAM"
          value={
            latest
              ? `${latest.ram_percent.toFixed(0)}% · ${(latest.ram_used_mb / 1024).toFixed(1)}/${(latest.ram_total_mb / 1024).toFixed(1)} GB`
              : '—'
          }
        />
        <Stat
          label="Disk"
          value={
            latest
              ? `${latest.disk_percent.toFixed(0)}% · ${latest.disk_used_gb}/${latest.disk_total_gb} GB`
              : '—'
          }
        />
        <Stat
          label="Net"
          value={
            latest
              ? `↓${latest.net_recv_mb.toFixed(2)} ↑${latest.net_sent_mb.toFixed(2)} MB/s`
              : '—'
          }
        />
      </div>

      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points}>
            <defs>
              <linearGradient id="g-cpu" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f5b301" stopOpacity={0.7} />
                <stop offset="100%" stopColor="#f5b301" stopOpacity={0.05} />
              </linearGradient>
              <linearGradient id="g-ram" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#60a5fa" stopOpacity={0.7} />
                <stop offset="100%" stopColor="#60a5fa" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <XAxis dataKey="t" hide />
            <YAxis domain={[0, 100]} tick={{ fill: '#6b7488', fontSize: 10 }} width={30} />
            <Tooltip
              contentStyle={{ background: '#141822', border: '1px solid #2a3249' }}
              labelStyle={{ color: '#e6e8ef' }}
            />
            <Area type="monotone" dataKey="cpu" stroke="#f5b301" fill="url(#g-cpu)" />
            <Area type="monotone" dataKey="ram" stroke="#60a5fa" fill="url(#g-ram)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[#0f1420] rounded p-2">
      <div className="text-xs text-gray-400">{label}</div>
      <div className="font-mono">{value}</div>
    </div>
  );
}
