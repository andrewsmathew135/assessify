"""End-to-end API tests covering the full happy path and error handling."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine, init_db
from app.main import app
from tests.conftest import build_macro_docx, build_xlsx


@pytest.fixture(scope="module")
def client():
    # Start from a clean schema for the module.
    Base.metadata.drop_all(bind=engine)
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def token(client):
    resp = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "test-pass-123"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_login_rejects_bad_password(client):
    resp = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "wrong"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == "unauthorized"
    assert "message" in body


def test_admin_routes_require_auth(client):
    resp = client.get("/api/admin/templates")
    assert resp.status_code == 401


def test_macro_upload_rejected_cleanly(client, token):
    files = {"file": ("evil.docx", build_macro_docx(), "application/octet-stream")}
    resp = client.post(
        "/api/admin/templates",
        headers=_auth(token),
        data={"name": "Evil", "instructions": ""},
        files=files,
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "macro_detected"
    # No stack trace leaks — just a clean human-readable message.
    assert "macro" in body["message"].lower()


def test_full_happy_path(client, token):
    # 1) Upload an Excel template.
    xlsx = build_xlsx({"A1": "Name", "B1": "", "A2": "Score", "B2": 0})
    files = {
        "file": (
            "assess.xlsx",
            xlsx,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    resp = client.post(
        "/api/admin/templates",
        headers=_auth(token),
        data={"name": "Data Task", "instructions": "Fill B1 and B2."},
        files=files,
    )
    assert resp.status_code == 201, resp.text
    template_id = resp.json()["id"]

    # 2) Define the field spec.
    spec = {
        "fields": [
            {"id": "name", "label": "Name", "sheet": "Sheet1", "cell": "B1", "required": True},
            {
                "id": "score",
                "label": "Score",
                "sheet": "Sheet1",
                "cell": "B2",
                "type": "number",
                "required": True,
                "min": 0,
                "max": 100,
            },
        ]
    }
    resp = client.patch(
        f"/api/admin/templates/{template_id}",
        headers=_auth(token),
        json={"field_spec": spec},
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["field_spec"]["fields"]) == 2

    # 3) Create a candidate session (link).
    resp = client.post(
        "/api/admin/sessions",
        headers=_auth(token),
        json={"template_id": template_id, "candidate_name": "Ada"},
    )
    assert resp.status_code == 201, resp.text
    link = resp.json()
    candidate_token = link["token"]
    assert link["candidate_url"].endswith(candidate_token)

    # 4) Candidate opens the assignment.
    resp = client.get(f"/api/candidate/{candidate_token}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "opened"
    assert resp.json()["file_type"] == "xlsx"

    # 5) Candidate fetches the spreadsheet grid.
    resp = client.get(f"/api/candidate/{candidate_token}/workbook")
    assert resp.status_code == 200
    editable = {
        c["address"]
        for sheet in resp.json()["sheets"]
        for row in sheet["rows"]
        for c in row
        if c["editable"]
    }
    assert editable == {"B1", "B2"}

    # 6) Candidate submits edits in-browser.
    resp = client.post(
        f"/api/candidate/{candidate_token}/submit-edits",
        json={"field_values": {"name": "Ada Lovelace", "score": 92}},
    )
    assert resp.status_code == 200, resp.text
    confirmation = resp.json()
    assert confirmation["review_status"] == "passed"
    assert confirmation["fields_submitted"]["name"] == "Ada Lovelace"

    # 7) Admin sees the submission on the dashboard.
    resp = client.get("/api/admin/submissions", headers=_auth(token))
    assert resp.status_code == 200
    rows = resp.json()
    assert any(r["template_id"] == template_id for r in rows)
    submission_id = next(r["submission_id"] for r in rows if r["template_id"] == template_id)

    # 8) Admin opens the submission detail and sees a passing report.
    resp = client.get(f"/api/admin/submissions/{submission_id}", headers=_auth(token))
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["review_status"] == "passed"
    assert detail["review_report"]["failed_count"] == 0

    # 9) Admin can download the submitted file.
    resp = client.get(
        f"/api/admin/submissions/{submission_id}/file?which=submitted",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.content[:2] == b"PK"  # a valid Office/zip package


def test_invalid_candidate_link_returns_clean_404(client):
    resp = client.get("/api/candidate/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["code"] == "not_found"
