import { formatScore } from "@/lib/utils";

const SIZE = 160;
const STROKE = 10;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function arcColor(score: number): string {
  if (score >= 90) return "var(--color-pass)";
  if (score >= 70) return "var(--color-warn)";
  return "var(--color-fail)";
}

export function ScoreGauge({
  score,
  passed,
  size = SIZE,
}: {
  score: number;
  passed: boolean;
  size?: number;
}) {
  const scale = size / SIZE;
  const offset = CIRCUMFERENCE * (1 - score / 100);

  return (
    <div className="flex flex-col items-center gap-2">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        className="transform -rotate-90"
      >
        {/* Track */}
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke="var(--color-surface-3)"
          strokeWidth={STROKE}
        />
        {/* Filled arc */}
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke={arcColor(score)}
          strokeWidth={STROKE}
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-700 ease-out"
        />
        {/* Score text */}
        <text
          x={SIZE / 2}
          y={SIZE / 2}
          textAnchor="middle"
          dominantBaseline="central"
          fill="var(--color-text-primary)"
          fontSize={36 * scale}
          fontFamily="var(--font-mono)"
          fontWeight="bold"
          transform={`rotate(90, ${SIZE / 2}, ${SIZE / 2})`}
        >
          {formatScore(score)}
        </text>
      </svg>
      <span
        className="font-mono text-xs font-semibold tracking-widest"
        style={{ color: passed ? "var(--color-pass)" : "var(--color-fail)" }}
      >
        {passed ? "PASS" : "FAIL"}
      </span>
    </div>
  );
}
