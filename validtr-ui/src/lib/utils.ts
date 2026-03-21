import clsx, { type ClassValue } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatScore(score: number): string {
  return score % 1 === 0 ? String(score) : score.toFixed(1);
}

export function scoreColor(score: number): string {
  if (score >= 90) return "text-pass";
  if (score >= 70) return "text-warn";
  return "text-fail";
}

export function scoreBg(score: number): string {
  if (score >= 90) return "bg-pass";
  if (score >= 70) return "bg-warn";
  return "bg-fail";
}

export function truncate(str: string, len: number): string {
  if (str.length <= len) return str;
  return str.slice(0, len) + "...";
}

export function relativeTime(timestamp: number): string {
  const diff = Date.now() - timestamp;
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
