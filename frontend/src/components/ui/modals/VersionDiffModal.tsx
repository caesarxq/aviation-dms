import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "../../../api/client";
import { Modal } from "../Modal";
import { InlineSuggestionView } from "../../documents/InlineSuggestionView";
import { htmlToText } from "../../../utils/diff";

export function VersionDiffModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [docId, setDocId] = useState("");
  const [versionA, setVersionA] = useState("");
  const [versionB, setVersionB] = useState("");

  const { data: docs = [] } = useQuery({
    queryKey: ["version-diff-modal-docs"],
    queryFn: () => api.get("/p0/documents").then((r: any) => r.data),
  });

  const { data: versions = [] } = useQuery({
    queryKey: ["version-diff-modal-versions", docId],
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
    <Modal open={open} onClose={onClose} title="Version Diff" className="max-w-5xl">
      <div className="grid grid-cols-3 gap-3 mb-3">
        <div>
          <label className="block text-[10px] font-medium text-white/70 mb-1">Document</label>
          <select id="docid_37" name="docid"
            className="w-full border border-white/20 rounded p-1.5 text-sm bg-white/10 text-white focus:border-kfl-blue focus:outline-none"
            value={docId}
            onChange={(e) => { setDocId(e.target.value); setVersionA(""); setVersionB(""); }}
          >
            <option value="">— Select document —</option>
            {docs.map((d: any) => (
              <option key={d.document_id} value={d.document_id}>
                {d.document_id} — {d.title}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-[10px] font-medium text-white/70 mb-1">Version A</label>
          <select id="versiona_52" name="versiona"
            className="w-full border border-white/20 rounded p-1.5 text-sm bg-white/10 text-white focus:border-kfl-blue focus:outline-none"
            value={versionA}
            onChange={(e) => setVersionA(e.target.value)}
            disabled={!docId}
          >
            <option value="">— Select version —</option>
            {versions.map((v: any) => (
              <option key={v.version_id} value={v.version_id}>
                {v.version_number} ({v.state})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-[10px] font-medium text-white/70 mb-1">Version B</label>
          <select id="versionb_68" name="versionb"
            className="w-full border border-white/20 rounded p-1.5 text-sm bg-white/10 text-white focus:border-kfl-blue focus:outline-none"
            value={versionB}
            onChange={(e) => setVersionB(e.target.value)}
            disabled={!docId}
          >
            <option value="">— Select version —</option>
            {versions.map((v: any) => (
              <option key={v.version_id} value={v.version_id}>
                {v.version_number} ({v.state})
              </option>
            ))}
          </select>
        </div>
      </div>

      {versionA && versionB ? (
        contentA || contentB ? (
          <InlineSuggestionView originalText={contentA} proposedText={contentB} />
        ) : (
          <div className="mt-4 p-4 text-center text-kfl-muted text-sm">No content to compare.</div>
        )
      ) : (
        <div className="mt-4 p-4 text-center text-kfl-muted text-sm">Select a document and two versions to compare.</div>
      )}
    </Modal>
  );
}
