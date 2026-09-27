"use client";

import { ReactNode } from "react";
import { ResponsiveContainer } from "recharts";

interface ChartFrameProps {
  children: ReactNode;
  height?: number;
  label?: string;
}

export function ChartFrame({ children, height = 260, label }: ChartFrameProps) {
  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        {/* ResponsiveContainer requires a single child */}
        <>{children}</>
      </ResponsiveContainer>
      {label && (
        <p className="mt-2 text-center text-xs text-slate-400 dark:text-slate-500">
          {label}
        </p>
      )}
    </div>
  );
}
