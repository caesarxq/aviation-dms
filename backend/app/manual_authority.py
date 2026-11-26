"""Manual ownership authority for the controlled-manual change workflow.

Ownership lives as data (`manual_ownership` seeded per `doc_class`, plus
`documents.manual_owner_role`). This module turns that data into a decision the
change-request workflow can enforce:

- the manual owner reviews change requests for that manual
- the approver role (Head of Quality) approves, rejects, and publishes

Documents outside the ownership scheme fall through unchanged, so the existing
permission checks continue to govern them.
"""
from typing import Optional

SYSTEM_ADMIN_ROLE = "system_admin"
DEFAULT_APPROVER_ROLE = "head_quality"


async def authority_for_document(db, document_id: str) -> dict:
    """Return the owner/approver roles governing a document.

    Empty dict means the document does not exist; missing roles mean it is not
    part of the manual ownership scheme.
    """
    row = await (await db.execute(
        "SELECT d.document_id, d.doc_class, d.document_category, d.manual_owner_role, "
        "       mo.owner_role AS mapped_owner, mo.approver_role AS mapped_approver "
        "FROM documents d "
        "LEFT JOIN manual_ownership mo ON mo.doc_class = d.doc_class "
        "WHERE d.document_id = ?",
        (document_id,),
    )).fetchone()
    if row is None:
        return {}

    owner_role = row["manual_owner_role"] or row["mapped_owner"] or ""
    approver_role = row["mapped_approver"] or (DEFAULT_APPROVER_ROLE if owner_role else "")
    return {
        "document_id": row["document_id"],
        "doc_class": row["doc_class"] or "",
        "owner_role": owner_role,
        "approver_role": approver_role,
    }


def _denied(role: str, expected: str, action: str) -> str:
    return (
        f"{action} for this manual requires the {expected} role "
        f"(actor role: {role or 'unknown'})."
    )


def can_review(role: str, authority: dict) -> bool:
    """The owner of the manual reviews its change requests."""
    owner_role: Optional[str] = authority.get("owner_role") if authority else ""
    if not owner_role:
        return True
    return role == owner_role or role == SYSTEM_ADMIN_ROLE


def can_approve(role: str, authority: dict) -> bool:
    """Only the approver role (Head of Quality) approves, rejects, and publishes."""
    approver_role: Optional[str] = authority.get("approver_role") if authority else ""
    if not approver_role:
        return True
    return role == approver_role or role == SYSTEM_ADMIN_ROLE


def review_denial(role: str, authority: dict) -> str:
    return _denied(role, authority.get("owner_role", ""), "Reviewing a change request")


def approve_denial(role: str, authority: dict) -> str:
    return _denied(role, authority.get("approver_role", ""), "Approving or publishing a change request")
