import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { p2Api } from "../api/p2";

export function OutsourcedFunctions() {
  const qc = useQueryClient();
  const { data: items = [], isLoading } = useQuery({
    queryKey: ["outsourced-functions"],
    queryFn: () => p2Api.listOutsourcedFunctions(),
  });
  const [showForm, setShowForm] = useState(false);
  const [provider, setProvider] = useState("");
  const [scope, setScope] = useState("");

  const createMutation = useMutation({
    mutationFn: (data: any) => p2Api.createOutsourcedFunction(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["outsourced-functions"] });
      setShowForm(false);
      setProvider("");
      setScope("");
    },
  });

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">Outsourced Functions</h1>
        <button onClick={() => setShowForm(!showForm)} className="bg-kfl-teal text-white px-4 py-2 rounded">
          {showForm ? "Cancel" : "Add Provider"}
        </button>
      </div>
      {showForm && (
        <div className="bg-white p-4 rounded shadow mb-4">
          <input className="border p-2 w-full mb-2 rounded" placeholder="Provider name" value={provider} onChange={(e) => setProvider(e.target.value)} />
          <input className="border p-2 w-full mb-2 rounded" placeholder="Scope" value={scope} onChange={(e) => setScope(e.target.value)} />
          <button onClick={() => createMutation.mutate({ provider_name: provider, scope })} className="bg-kfl-teal text-white px-4 py-2 rounded">Create</button>
        </div>
      )}
      {isLoading ? (
        <p>Loading...</p>
      ) : (
        <table className="min-w-full bg-white border rounded shadow">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Provider</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Scope</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {items.map((i: any) => (
              <tr key={i.function_id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-sm font-medium">{i.provider_name}</td>
                <td className="px-4 py-2 text-sm">{i.scope}</td>
                <td className="px-4 py-2 text-sm">{i.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function SafetyKPIs() {
  const qc = useQueryClient();
  const { data: items = [], isLoading } = useQuery({
    queryKey: ["safety-kpis"],
    queryFn: () => p2Api.listSafetyKPIs(),
  });
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");

  const createMutation = useMutation({
    mutationFn: (data: any) => p2Api.createSafetyKPI(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["safety-kpis"] });
      setShowForm(false);
      setName("");
      setTarget("");
    },
  });

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">Safety KPIs</h1>
        <button onClick={() => setShowForm(!showForm)} className="bg-kfl-teal text-white px-4 py-2 rounded">
          {showForm ? "Cancel" : "Add KPI"}
        </button>
      </div>
      {showForm && (
        <div className="bg-white p-4 rounded shadow mb-4">
          <input className="border p-2 w-full mb-2 rounded" placeholder="KPI name" value={name} onChange={(e) => setName(e.target.value)} />
          <input className="border p-2 w-full mb-2 rounded" placeholder="Target" value={target} onChange={(e) => setTarget(e.target.value)} />
          <button onClick={() => createMutation.mutate({ kpi_name: name, target })} className="bg-kfl-teal text-white px-4 py-2 rounded">Create</button>
        </div>
      )}
      {isLoading ? (
        <p>Loading...</p>
      ) : (
        <table className="min-w-full bg-white border rounded shadow">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">KPI</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Target</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {items.map((i: any) => (
              <tr key={i.kpi_id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-sm font-medium">{i.kpi_name}</td>
                <td className="px-4 py-2 text-sm">{i.target}</td>
                <td className="px-4 py-2 text-sm">{i.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function SecurityReviews() {
  const qc = useQueryClient();
  const { data: items = [], isLoading } = useQuery({
    queryKey: ["security-reviews"],
    queryFn: () => p2Api.listSecurityReviews(),
  });
  const [showForm, setShowForm] = useState(false);
  const [date, setDate] = useState("");

  const createMutation = useMutation({
    mutationFn: (data: any) => p2Api.createSecurityReview(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-reviews"] });
      setShowForm(false);
      setDate("");
    },
  });

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">Security Review Meetings</h1>
        <button onClick={() => setShowForm(!showForm)} className="bg-kfl-teal text-white px-4 py-2 rounded">
          {showForm ? "Cancel" : "Schedule Review"}
        </button>
      </div>
      {showForm && (
        <div className="bg-white p-4 rounded shadow mb-4">
          <input type="date" className="border p-2 w-full mb-2 rounded" value={date} onChange={(e) => setDate(e.target.value)} />
          <button onClick={() => createMutation.mutate({ meeting_date: date })} className="bg-kfl-teal text-white px-4 py-2 rounded">Schedule</button>
        </div>
      )}
      {isLoading ? (
        <p>Loading...</p>
      ) : (
        <table className="min-w-full bg-white border rounded shadow">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Meeting Date</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Attendees</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {items.map((i: any) => (
              <tr key={i.review_id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-sm font-medium">{i.meeting_date}</td>
                <td className="px-4 py-2 text-sm">{i.status}</td>
                <td className="px-4 py-2 text-sm">{i.attendees || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function DGResponsibilityMatrix() {
  const qc = useQueryClient();
  const { data: items = [], isLoading } = useQuery({
    queryKey: ["dg-matrix"],
    queryFn: () => p2Api.listDGMatrix(),
  });
  const [showForm, setShowForm] = useState(false);
  const [project, setProject] = useState("");
  const [stage, setStage] = useState("");
  const [role, setRole] = useState("");

  const createMutation = useMutation({
    mutationFn: (data: any) => p2Api.createDGMatrix(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dg-matrix"] });
      setShowForm(false);
      setProject("");
      setStage("");
      setRole("");
    },
  });

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">DG Responsibility Matrix</h1>
        <button onClick={() => setShowForm(!showForm)} className="bg-kfl-teal text-white px-4 py-2 rounded">
          {showForm ? "Cancel" : "Add Entry"}
        </button>
      </div>
      {showForm && (
        <div className="bg-white p-4 rounded shadow mb-4">
          <input className="border p-2 w-full mb-2 rounded" placeholder="Project / Route" value={project} onChange={(e) => setProject(e.target.value)} />
          <input className="border p-2 w-full mb-2 rounded" placeholder="Process Stage" value={stage} onChange={(e) => setStage(e.target.value)} />
          <input className="border p-2 w-full mb-2 rounded" placeholder="Responsible Role" value={role} onChange={(e) => setRole(e.target.value)} />
          <button onClick={() => createMutation.mutate({ project_or_route: project, process_stage: stage, responsible_role: role })} className="bg-kfl-teal text-white px-4 py-2 rounded">Create</button>
        </div>
      )}
      {isLoading ? (
        <p>Loading...</p>
      ) : (
        <table className="min-w-full bg-white border rounded shadow">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Project / Route</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Process Stage</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Responsible Role</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {items.map((i: any) => (
              <tr key={i.matrix_id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-sm font-medium">{i.project_or_route}</td>
                <td className="px-4 py-2 text-sm">{i.process_stage}</td>
                <td className="px-4 py-2 text-sm">{i.responsible_role}</td>
                <td className="px-4 py-2 text-sm">{i.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
