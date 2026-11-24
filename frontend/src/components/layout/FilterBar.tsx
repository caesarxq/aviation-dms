import { useState, useEffect, useRef, useCallback } from "react";
import { Search, X, ChevronRight } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import api from "../../api/client";

interface SearchResult {
  type: string;
  id: string;
  title: string;
  subtitle: string;
  url: string;
}

interface FilterBarProps {
  placeholder?: string;
  className?: string;
}

const TYPE_LABELS: Record<string, string> = {
  document: "Document",
  audit: "Audit Finding",
  license: "Personnel License",
  aircraft: "Aircraft",
  mission: "Mission",
};

const TYPE_ICONS: Record<string, string> = {
  document: "📄",
  audit: "🔍",
  license: "🪪",
  aircraft: "✈️",
  mission: "✈️",
};

export function FilterBar({ placeholder = "Search documents, audits, licenses, aircraft, missions…", className }: FilterBarProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const [searchParams, setSearchParams] = useSearchParams();

  // Initialize query from URL search param
  useEffect(() => {
    const q = searchParams.get("q") || "";
    setQuery(q);
    if (q) {
      setOpen(true);
    }
  }, []);

  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  const handleSearch = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    try {
      const data = await api.get<SearchResult[]>(
        "/p0/search",
        { params: { q, types: "document,audit,license,aircraft,mission" } },
      );
      setResults(data.data);
      setOpen(true);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!query.trim()) {
      setResults([]);
      setOpen(false);
      return;
    }
    debounceRef.current = setTimeout(() => handleSearch(query), 250);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, handleSearch]);

  const handleSelect = (result: SearchResult) => {
    setQuery("");
    setResults([]);
    setOpen(false);
    if (inputRef.current) inputRef.current.value = "";
    // Update URL param for shareability
    setSearchParams({ q: "" }, { replace: true });
    window.location.assign(result.url);
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Enter" && results.length > 0) {
      handleSelect(results[0]);
    }
    if (event.key === "Escape") {
      setOpen(false);
      setQuery("");
      setResults([]);
      setSearchParams({ q: "" }, { replace: true });
    }
  };

  const clearSearch = () => {
    setQuery("");
    setResults([]);
    setOpen(false);
    setSearchParams({ q: "" }, { replace: true });
    if (inputRef.current) inputRef.current.value = "";
    if (inputRef.current) inputRef.current.focus();
  };

  return (
    <div className={`relative w-full ${className ?? ""}`}>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-kfl-muted" />
        <input
          ref={inputRef}
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="w-full pl-9 pr-4 py-2 text-sm border border-kfl-border rounded-lg bg-kfl-surface focus:outline-none focus:ring-2 focus:ring-kfl-blue transition-all"
        />
        {query && (
          <button
            type="button"
            onClick={clearSearch}
            className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-kfl-muted hover:text-kfl-text"
            aria-label="Clear search"
          >
            <X size={14} />
          </button>
        )}
      </div>

      {open && results.length > 0 && (
        <div className="absolute z-50 mt-1 w-full max-w-md rounded-lg border border-kfl-border bg-kfl-surface shadow-xl overflow-hidden">
          <div className="border-b border-kfl-border p-2 flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-kfl-muted">Search results</span>
            {loading && <span className="text-[10px] text-kfl-muted">Loading…</span>}
          </div>
          <div className="max-h-60 overflow-y-auto">
            {results.map((result) => (
              <button
                key={result.id}
                type="button"
                onClick={() => handleSelect(result)}
                className="w-full text-left px-3 py-2 hover:bg-kfl-surface-subtle border-b border-kfl-border/50 last:border-0 transition-colors"
              >
                <div className="flex items-start gap-2">
                  <span className="shrink-0 text-[12px] mt-0.5">{TYPE_ICONS[result.type] ?? "📋"}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-baseline">
                      <span className="text-sm font-medium text-kfl-text truncate">{result.title}</span>
                      <span className="ml-1 text-[10px] text-kfl-muted">{TYPE_LABELS[result.type] ?? result.type}</span>
                    </div>
                    <span className="text-xs text-kfl-muted truncate">{result.subtitle}</span>
                  </div>
                  <ChevronRight size={12} className="text-kfl-muted shrink-0" />
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default FilterBar;
