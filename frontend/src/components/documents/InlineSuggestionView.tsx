import { inlineSuggestionSegments } from "../../utils/diff";

export function InlineSuggestionView({ originalText, proposedText }: { originalText: string; proposedText: string }) {
  const segments = inlineSuggestionSegments(originalText, proposedText);
  const hasChanges = segments.some((segment) => segment.type === "added" || segment.type === "removed");
  const additions = segments.filter((segment) => segment.type === "added").length;
  const deletions = segments.filter((segment) => segment.type === "removed").length;

  return (
    <section className="rounded-lg border border-kfl-border bg-white" aria-label="Live suggestion markup">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-kfl-border bg-kfl-surface-subtle px-4 py-3">
        <div>
          <h3 className="text-sm font-bold text-kfl-text">Live suggestion markup</h3>
          <p className="mt-1 text-xs text-kfl-muted">Changes update as you type. Green text is proposed; red strike-through is removed.</p>
        </div>
        <div className="flex gap-3 text-xs font-semibold">
          <span className="text-emerald-700">+{additions} additions</span>
          <span className="text-red-700">−{deletions} deletions</span>
        </div>
      </div>
      <div className="min-h-[220px] whitespace-pre-wrap break-words p-4 text-sm leading-7 text-kfl-text" data-testid="inline-suggestion-stream">
        {!hasChanges ? (
          <span className="text-kfl-muted">No proposed changes yet. Edit the document to see suggestions here.</span>
        ) : (
          segments.map((segment, index) => {
            if (segment.type === "break") return <br key={index} />;
            if (segment.type === "removed") return <del key={index} className="rounded bg-red-100 px-0.5 text-red-800 line-through decoration-red-500">{segment.value}</del>;
            if (segment.type === "added") return <ins key={index} className="rounded bg-emerald-100 px-0.5 text-emerald-800 no-underline">{segment.value}</ins>;
            return <span key={index}>{segment.value}</span>;
          })
        )}
      </div>
    </section>
  );
}
