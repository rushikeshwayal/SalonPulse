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

def test_customer_lookup_and_multi_service_visit():
    with TestClient(app) as client:
        client.post("/api/demo/reset")
        branches = client.get("/api/branches").json()
        barbers = client.get("/api/barbers").json()
        branch = branches[0]
        barber = next(item for item in barbers if item["branch_id"] == branch["id"])

        created = client.post("/api/visits", json={
            "customer_name": "Aarohi Test",
            "customer_phone": "+91 98765 12345",
            "customer_location": "Kharadi, Pune",
            "branch_id": branch["id"],
            "barber_id": barber["id"],
            "completed_at": "2026-08-15T18:05:00+05:30",
            "services": [
                {"service_name": "Haircut", "quantity": 1, "unit_price": 300},
                {"service_name": "Beard Trim", "quantity": 2, "unit_price": 150},
            ],
            "messaging_consent": False,
        })
        assert created.status_code == 201
        visit = created.json()["visit"]
        assert visit["amount"] == 600
        assert len(visit["service_items"]) == 2
        assert visit["customer_phone"] == "+91 98765 12345"
        assert visit["customer_location"] == "Kharadi, Pune"
        assert visit["completed_at"] == "2026-08-15T12:35:00Z"

        found_by_phone = client.get(
            "/api/customers/search", params={"q": "9876512345"}
        )
        assert found_by_phone.status_code == 200
        assert any(c["id"] == visit["customer_id"] for c in found_by_phone.json())

        found_by_name = client.get(
            "/api/customers/search", params={"q": "Aarohi"}
        )
        assert any(c["id"] == visit["customer_id"] for c in found_by_name.json())

        # A new-customer request with an already registered number is rejected to avoid duplicates.
        duplicate = client.post("/api/visits", json={
            "customer_name": "Aarohi Duplicate",
            "customer_phone": "9876512345",
            "branch_id": branch["id"],
            "barber_id": barber["id"],
            "services": [{"service_name": "Hair Wash", "quantity": 1, "unit_price": 100}],
        })
        assert duplicate.status_code == 409

        # A returning customer can be confirmed by ID and revisited without creating a duplicate.
        returning = client.post("/api/visits", json={
            "customer_id": visit["customer_id"],
            "branch_id": branch["id"],
            "barber_id": barber["id"],
            "services": [{"service_name": "Hair Wash", "quantity": 1, "unit_price": 100}],
        })
        assert returning.status_code == 201
        assert returning.json()["visit"]["customer_id"] == visit["customer_id"]
        client.post("/api/demo/reset")

