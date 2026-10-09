from fastapi.testclient import TestClient

from app.main import app


def test_demo_api_happy_path():
    """Exercise the demo workflow against a reset SQLite demo database."""
    with TestClient(app) as client:
        assert client.post("/api/demo/reset").status_code == 200

        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        branches = client.get("/api/branches").json()
        barbers = client.get("/api/barbers").json()
        customers = client.get("/api/customers").json()
        assert branches and barbers and customers

        branch = branches[0]
        barber = next(item for item in barbers if item["branch_id"] == branch["id"])
        visit_response = client.post("/api/visits", json={
            "customer_id": customers[0]["id"],
            "branch_id": branch["id"],
            "barber_id": barber["id"],
            "service_name": "Test haircut",
            "amount": 350,
            "messaging_consent": True,
        })
        assert visit_response.status_code == 201
        visit = visit_response.json()["visit"]
        assert visit_response.json()["message_status"] == "mock_queued"

        feedback_response = client.post("/api/feedback", json={
            "visit_id": visit["id"],
            "rating": 1,
            "comment": "The result was not what I requested.",
        })
        assert feedback_response.status_code == 201
        assert feedback_response.json()["recovery_created"] is True
        task_id = feedback_response.json()["feedback"]["recovery_task_id"]

        resolved = client.patch(f"/api/recovery-tasks/{task_id}", json={
            "status": "resolved",
            "resolution_note": "Followed up in the test.",
        })
        assert resolved.status_code == 200
        assert resolved.json()["status"] == "resolved"

        for path in ("/api/dashboard", "/api/visits", "/api/feedback",
                     "/api/recovery-tasks", "/api/insights", "/api/messages", "/"):
            assert client.get(path).status_code == 200, path

        assert client.post("/api/demo/reset").status_code == 200
