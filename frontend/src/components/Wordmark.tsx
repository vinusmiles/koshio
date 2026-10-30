/** The Koshio mark: a coin slot (kosh = treasury) above the name. */
export function Wordmark({ size = "md" }: { size?: "md" | "lg" }) {
  const big = size === "lg";
  return (
    <span className="inline-flex items-center gap-2.5">
      <svg width={big ? 36 : 26} height={big ? 36 : 26} viewBox="0 0 32 32" aria-hidden="true">
        <rect width="32" height="32" rx="9" className="fill-ink" />
        <rect x="9" y="10" width="14" height="3" rx="1.5" className="fill-brass" />
        <circle cx="16" cy="20.5" r="4.5" fill="none" strokeWidth="2.4" className="stroke-brass" />
      </svg>
      <span className={`font-extrabold tracking-tight ${big ? "text-3xl" : "text-xl"}`}>Koshio</span>
    </span>
  );
}
