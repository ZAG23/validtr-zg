import { cn } from "@/lib/utils";

export function StatusBadge({ passed }: { passed: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded font-mono text-xs font-semibold tracking-wider",
        passed
          ? "bg-pass/15 text-pass border border-pass/30"
          : "bg-fail/15 text-fail border border-fail/30",
      )}
    >
      {passed ? "PASS" : "FAIL"}
    </span>
  );
}
