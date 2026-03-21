export function EmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="font-mono text-4xl text-text-muted mb-4">{">"}_</div>
      <h3 className="text-lg font-medium text-text-secondary mb-2">{title}</h3>
      <p className="text-sm text-text-muted max-w-md">{description}</p>
    </div>
  );
}
