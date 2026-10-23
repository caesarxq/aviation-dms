import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "../api/client";
import { InlineSuggestionView } from "../components/documents/InlineSuggestionView";
import { htmlToText } from "../utils/diff";

export function VersionDiff() {
  const [docId, setDocId] = useState("");
  const [versionA, setVersionA] = useState("");
  const [versionB, setVersionB] = useState("");

  const { data: docs = [] } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.get("/p0/documents").then((r: any) => r.data),
  });

  const { data: versions = [], isLoading } = useQuery({
    queryKey: ["versions", docId],
    queryFn: () => docId
      ? api.get(`/p0/documents/${docId}/versions`).then((r: any) => r.data)
      : Promise.resolve([]),
    enabled: !!docId,
  });

  const verA = versions.find((v: any) => v.version_id === versionA);
  const verB = versions.find((v: any) => v.version_id === versionB);

  const contentA = htmlToText(verA?.content || "");
  const contentB = htmlToText(verB?.content || "");

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Document Control</div>
          <h1 className="app-title">Version Diff</h1>
          <p className="app-subtitle">Track changes as one readable suggestion stream instead of a side-by-side comparison.</p>
        </div>
      </header>

      {/* Selectors */}
      <div className="app-surface p-4 mb-4">
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="text-sm font-semibold text-kfl-muted mb-2 block">Document</label>
            <select className="border border-kfl-border rounded p-2 text-sm w-full" value={docId} onChange={e => { setDocId(e.target.value); setVersionA(""); setVersionB(""); }}>
              <option value="">— Select document —</option>
              {docs.map((d: any) => <option key={d.document_id} value={d.document_id}>{d.document_id} — {d.title}</option>)}
            </select>
          </div>
          <div>
            <label className="text-sm font-semibold text-kfl-muted mb-2 block">Version A (left)</label>
            <select className="border border-kfl-border rounded p-2 text-sm w-full" value={versionA} onChange={e => setVersionA(e.target.value)} disabled={!docId}>
              <option value="">— Select version —</option>
              {versions.map((v: any) => <option key={v.version_id} value={v.version_id}>{v.version_number} ({v.state})</option>)}
            </select>
          </div>
          <div>
            <label className="text-sm font-semibold text-kfl-muted mb-2 block">Version B (right)</label>
            <select className="border border-kfl-border rounded p-2 text-sm w-full" value={versionB} onChange={e => setVersionB(e.target.value)} disabled={!docId}>
              <option value="">— Select version —</option>
              {versions.map((v: any) => <option key={v.version_id} value={v.version_id}>{v.version_number} ({v.state})</option>)}
            </select>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="p-8 text-kfl-muted">Loading versions…</div>
      ) : versionA && versionB ? (
        (contentA || contentB) ? (
          <InlineSuggestionView originalText={contentA} proposedText={contentB} />
        ) : (
          <div className="app-surface p-8 text-center text-kfl-muted">No content to compare.</div>
        )
      ) : (
        <div className="app-surface p-8 text-center text-kfl-muted">Select a document and two versions to compare.</div>
      )}
    </div>
  );
}

export default VersionDiff;
