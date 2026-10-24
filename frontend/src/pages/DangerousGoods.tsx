import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { Plus, Package, Share2 } from "lucide-react";
import { useToast } from "../components/ui/Toast";
import FormField from "../components/ui/FormField";
import { DGResponsibilityMatrixModal } from "../components/ui/modals/DGResponsibilityMatrixModal";
import { useValidation } from "../utils/validation";

function dgStatusClass(status: string) {
  switch (status) {
    case "accepted": return "app-status app-status-healthy";
    case "pending": return "app-status app-status-info";
    case "rejected": return "app-status app-status-critical";
    default: return "app-status app-status-info";
  }
}

export function DangerousGoods() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const { data: shipments = [], isLoading } = useQuery({
    queryKey: ["dg-shipments"],
    queryFn: () => api.get("/p1/dg-shipments").then((r: any) => r.data),
  });
  const [showForm, setShowForm] = useState(false);
  const [showDGModal, setShowDGModal] = useState(false);
  const [properShippingName, setProperShippingName] = useState("");
  const [dgClass, setDgClass] = useState("3");
  const [unNumber, setUnNumber] = useState("");
  const [dgError, setDgError] = useState("");

  const { errors: dgShipFieldErrors, isValid: dgShipIsValid } = useValidation(
    { proper_shipping_name: properShippingName, dg_class: dgClass },
    {
      proper_shipping_name: { required: true, minLength: 2 },
      dg_class: { required: true },
    }
  );

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/p1/dg-shipments", data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dg-shipments"] });
      setShowForm(false);
      setProperShippingName("");
      setDgClass("3");
      setUnNumber("");
      setDgError("");
      toast({ title: "DG shipment created", message: "The dangerous goods shipment has been registered.", type: "success" });
    },
    onError: () => {
      setDgError("Failed to create shipment. Please try again.");
    },
  });

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Dangerous Goods</div>
          <h1 className="app-title">Dangerous Goods Shipments</h1>
          <p className="app-subtitle">Track DG shipments, acceptance checks, and training records.</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="app-btn-primary"
        >
          <Plus size={16} /> {showForm ? "Cancel" : "New Shipment"}
        </button>
        <button
          onClick={() => setShowDGModal(true)}
          className="app-btn-secondary"
        >
          <Share2 size={16} /> Assign DG Responsibility
        </button>
      </header>

      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="app-surface p-4">
          <div className="app-label">Total Shipments</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{shipments.length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Accepted</div>
          <div className="mt-2 text-2xl font-bold text-emerald-700">{shipments.filter((s: any) => s.status === "accepted").length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Pending</div>
          <div className="mt-2 text-2xl font-bold text-amber-700">{shipments.filter((s: any) => s.status === "pending").length}</div>
        </div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="relative min-w-0 flex-1 md:max-w-md">
            <Package size={16} className="pointer-events-none absolute left-3 top-3 text-kfl-muted" />
            <input id="search_shipments_88" name="search_shipments"
              value={showForm ? properShippingName : ""}
              onChange={(e) => setProperShippingName(e.target.value)}
              placeholder="Search shipments…"
              className="app-input pl-9 relative z-10"
            />
          </div>
          <select id="select_field_95" name="select_field" className="app-input w-full md:w-auto">
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="accepted">Accepted</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>

        {showForm && (
          <div className="app-surface p-5 mb-5">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <div className="app-label mb-1">New DG Shipment</div>
                <p className="text-xs text-kfl-muted">Register a dangerous goods shipment for acceptance.</p>
              </div>
              <button onClick={() => setShowForm(false)} className="app-btn-secondary px-3 py-2">Cancel</button>
            </div>
            {dgError && (
              <div className="mb-3 p-3 rounded bg-rose-50/60 border border-rose-200 text-rose-800 text-sm">
                {dgError}
              </div>
            )}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FormField htmlFor="field_120" label="Proper shipping name" hint="Use the name shown in the dangerous goods declaration." required>
                <input id="field_120" name="proper_shipping_name" aria-describedby="field_120-error" aria-invalid={!!dgShipFieldErrors.proper_shipping_name} className={`app-input ${dgShipFieldErrors.proper_shipping_name ? "border-rose-400" : ""}`} placeholder="Lithium ion batteries" value={properShippingName} onChange={(e) => setProperShippingName(e.target.value)} />
                {dgShipFieldErrors.proper_shipping_name && <p id="field_120-error" className="text-[11px] text-rose-700 mt-1">{dgShipFieldErrors.proper_shipping_name}</p>}
              </FormField>
              <FormField htmlFor="field_124" label="DG class" hint="Enter the applicable hazard class, for example Class 3." required>
                <input id="field_124" name="dg_class" aria-describedby="field_124-error" aria-invalid={!!dgShipFieldErrors.dg_class} className={`app-input ${dgShipFieldErrors.dg_class ? "border-rose-400" : ""}`} placeholder="Class 3" value={dgClass} onChange={(e) => setDgClass(e.target.value)} />
                {dgShipFieldErrors.dg_class && <p id="field_124-error" className="text-[11px] text-rose-700 mt-1">{dgShipFieldErrors.dg_class}</p>}
              </FormField>
              <FormField htmlFor="field_128" label="UN number" hint="Use the four-digit UN number where applicable.">
                <input id="field_128" name="un_number" className="app-input" placeholder="UN3480" value={unNumber} onChange={(e) => setUnNumber(e.target.value)} />
              </FormField>
            </div>
            <button
              disabled={!dgShipIsValid || createMutation.isPending}
              onClick={() => {
                setDgError("");
                createMutation.mutate({ proper_shipping_name: properShippingName, dg_class: dgClass, un_number: unNumber });
              }}
              className="app-btn-primary w-full"
            >
              {createMutation.isPending ? "Creating…" : "Create Shipment"}
            </button>
          </div>
        )}

        {isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading shipments…</div>
        ) : shipments.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <Package size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No DG shipments.</p>
            <p className="mt-1 text-xs text-kfl-muted">Register your first DG shipment to begin acceptance tracking.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">ID</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Shipping Name</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">DG Class</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">UN Number</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {shipments.map((s: any) => (
                  <tr key={s.shipment_id} className="transition hover:bg-kfl-surface-subtle">
                    <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{s.shipment_id}</td>
                    <td className="px-4 py-4 text-sm font-medium text-kfl-text">{s.proper_shipping_name}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{s.dg_class}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{s.un_number || "—"}</td>
                    <td className="px-4 py-4">
                      <span className={dgStatusClass(s.status)}>{s.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <DGResponsibilityMatrixModal open={showDGModal} onClose={() => setShowDGModal(false)} />
    </div>
  );
}