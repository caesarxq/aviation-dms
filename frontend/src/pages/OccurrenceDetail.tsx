import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";

export function OccurrenceDetail() {
  const { occurrenceId } = useParams();
  const { data: occ, isLoading } = useQuery({
    queryKey: ["occurrence", occurrenceId],
    queryFn: () => safetyApi.getOccurrence(occurrenceId!),
    enabled: !!occurrenceId,
  });

  if (isLoading) return <div className="p-6">Loading...</div>;
  if (!occ) return <div className="p-6">Not found</div>;

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-2">{occ.title}</h1>
      <p className="text-gray-600 mb-4">{occ.serial_number} — {occ.status}</p>
      <div className="bg-white p-4 rounded shadow mb-4">
        <p><strong>Type:</strong> {occ.occurrence_type}</p>
        <p><strong>Severity:</strong> {occ.severity}</p>
        <p><strong>Location:</strong> {occ.location || "—"}</p>
        <p><strong>Occurred:</strong> {occ.occurred_at || "—"}</p>
        <p><strong>Reported:</strong> {occ.reported_at}</p>
        <p><strong>MOR Required:</strong> {occ.mor_required ? "Yes" : "No"}</p>
      </div>
      <div className="bg-white p-4 rounded shadow">
        <h2 className="font-semibold mb-2">Description</h2>
        <p>{occ.description}</p>
      </div>
    </div>
  );
}
