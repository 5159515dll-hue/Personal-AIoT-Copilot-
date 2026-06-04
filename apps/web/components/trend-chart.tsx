"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { formatTime } from "@/lib/format";
import type { SensorReading } from "@/lib/types";

export function TrendChart({
  readings,
  color = "#0D9488"
}: {
  readings: SensorReading[];
  color?: string;
}) {
  const data = readings.map((reading) => ({
    time: formatTime(reading.timestamp),
    value: reading.value,
    quality: reading.quality
  }));

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 18, left: -12, bottom: 0 }}>
          <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
          <XAxis dataKey="time" tick={{ fill: "#64748B", fontSize: 12 }} minTickGap={28} />
          <YAxis tick={{ fill: "#64748B", fontSize: 12 }} />
          <Tooltip
            contentStyle={{
              border: "1px solid #D9E2EC",
              borderRadius: 8,
              boxShadow: "0 12px 28px rgba(15, 23, 42, 0.12)"
            }}
          />
          <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

