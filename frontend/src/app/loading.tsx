export default function Loading() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center page-bg">
      <div className="text-center">
        <div className="mx-auto h-9 w-9 animate-spin rounded-full border-2 border-tata-blue border-t-transparent" />
        <p className="mt-3 text-sm font-medium text-tata-ink">Loading page…</p>
        <p className="mt-1 text-xs text-tata-muted">First visit may take a few seconds in dev mode</p>
      </div>
    </div>
  );
}
