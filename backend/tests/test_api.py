from fastapi.testclient import TestClient

from app.main import SessionLocal, StaffUser, app, hash_password

TEST_PASSWORD = "CI-Only-Password-2026!"


def login_as(client, username="owner"):
    with SessionLocal() as db:
        user = db.query(StaffUser).filter_by(username=username).first()
        assert user, f"Expected seeded test user {username}"
        user.password_hash = hash_password(TEST_PASSWORD)
        user.must_change_password = False
        user.is_active = True
        db.commit()
    response = client.post("/api/auth/login", json={
        "identifier": username, "password": TEST_PASSWORD
    })
    assert response.status_code == 200, response.text
    client.headers.update({"Authorization": "Bearer " + response.json()["access_token"]})
    return response.json()["user"]


def test_demo_api_happy_path():
    """Exercise the demo workflow against a reset SQLite demo database."""
    with TestClient(app) as client:
        assert client.get("/api/dashboard").status_code == 401
        login_as(client)
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
                     "/api/recovery-tasks", "/api/insights", "/api/messages", "/api/bootstrap", "/"):
            assert client.get(path).status_code == 200, path

        bootstrap = client.get("/api/bootstrap").json()
        assert set(bootstrap) == {
            "dashboard", "branches", "barbers", "customers", "visits",
            "user", "dashboard", "branches", "barbers", "customers", "visits",
            "feedback", "tasks", "insights", "messages", "serviceCatalog", "auditLogs",
        }
        assert bootstrap["dashboard"]["total_visits"] >= 1
        assert bootstrap["branches"] and bootstrap["serviceCatalog"]

        assert client.post("/api/demo/reset").status_code == 200

def test_customer_lookup_and_multi_service_visit():
    with TestClient(app) as client:
        login_as(client)
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



def test_roles_audit_versions_and_barber_rating():
    with TestClient(app) as client:
        owner = login_as(client, "owner")
        branches = client.get("/api/branches").json()
        barbers = client.get("/api/barbers").json()
        branch = branches[0]
        barber = next(b for b in barbers if b["branch_id"] == branch["id"])
        created = client.post("/api/visits", json={
            "customer_name": "Version Test Client",
            "customer_phone": "9876500011",
            "customer_location": "Pune",
            "branch_id": branch["id"],
            "barber_id": barber["id"],
            "services": [{"service_name": "Haircut", "quantity": 1, "unit_price": 300}],
        })
        assert created.status_code == 201, created.text
        visit = created.json()["visit"]

        assert client.get("/api/audit-logs").status_code == 200

        edited = client.patch(f"/api/visits/{visit['id']}", json={
            "services": [
                {"service_name": "Haircut", "quantity": 1, "unit_price": 350},
                {"service_name": "Hair Wash", "quantity": 1, "unit_price": 100},
            ],
            "change_note": "Corrected checkout total",
        })
        assert edited.status_code == 200, edited.text
        assert edited.json()["visit"]["amount"] == 450

        history = client.get(f"/api/visits/{visit['id']}/history")
        assert history.status_code == 200
        assert {item["action"] for item in history.json()} >= {"visit.create", "visit.update"}
        assert history.json()[0]["before_data"] is not None
        assert client.get("/api/staff-users").status_code == 200

        # The barber only sees their own assigned visit and cannot view owner-only staff data.
        login_as(client, "aarav")
        barber_visits = client.get("/api/visits").json()
        assert all(item["barber_id"] == 1 for item in barber_visits)
        assert client.get("/api/staff-users").status_code == 403
        assert client.get("/api/audit-logs").status_code == 403

        own_branch = next(b for b in client.get("/api/branches").json())
        created_by_barber = client.post("/api/visits", json={
            "customer_name": "Barber Rated Client",
            "customer_phone": "9876500012",
            "customer_location": "Pune",
            "branch_id": own_branch["id"],
            "barber_id": 999,  # backend derives barber identity from the signed-in account
            "services": [{"service_name": "Haircut", "quantity": 1, "unit_price": 300}],
        })
        assert created_by_barber.status_code == 201, created_by_barber.text
        barber_visit = created_by_barber.json()["visit"]
        rating = client.post("/api/customer-ratings", json={
            "visit_id": barber_visit["id"], "rating": 5, "note": "Arrived on time and communicated clearly."
        })
        assert rating.status_code == 201, rating.text
        assert client.get("/api/customer-ratings").json()[0]["rating"] == 5


def test_customer_visit_numbering_and_latest_only_editing():
    with TestClient(app) as client:
        login_as(client, "owner")
        reset = client.post("/api/demo/reset")
        assert reset.status_code == 200, reset.text

        branch = client.get("/api/branches").json()[0]
        barber = next(b for b in client.get("/api/barbers").json() if b["branch_id"] == branch["id"])
        first = client.post("/api/visits", json={
            "customer_name": "Timeline Test Customer",
            "customer_phone": "9876500021",
            "customer_location": "Pune",
            "branch_id": branch["id"],
            "barber_id": barber["id"],
            "completed_at": "2026-09-01T10:00:00Z",
            "services": [{"service_name": "Haircut", "quantity": 1, "unit_price": 300}],
        })
        assert first.status_code == 201, first.text
        customer_id = first.json()["visit"]["customer_id"]
        first_visit_id = first.json()["visit"]["id"]

        second = client.post("/api/visits", json={
            "customer_id": customer_id,
            "branch_id": branch["id"],
            "barber_id": barber["id"],
            "completed_at": "2026-10-01T10:00:00Z",
            "services": [{"service_name": "Beard Trim", "quantity": 1, "unit_price": 150}],
        })
        assert second.status_code == 201, second.text
        second_visit_id = second.json()["visit"]["id"]

        visits = client.get("/api/visits?limit=100").json()
        first_record = next(v for v in visits if v["id"] == first_visit_id)
        second_record = next(v for v in visits if v["id"] == second_visit_id)
        assert first_record["visit_number"] == 1
        assert second_record["visit_number"] == 2
        assert first_record["visit_count"] == second_record["visit_count"] == 2
        assert first_record["is_latest_visit"] is False
        assert first_record["can_edit"] is False
        assert second_record["is_latest_visit"] is True
        assert second_record["can_edit"] is True
        assert visits.index(second_record) < visits.index(first_record)

        older_edit = client.patch(f"/api/visits/{first_visit_id}", json={
            "services": [{"service_name": "Haircut", "quantity": 1, "unit_price": 400}],
            "change_note": "Trying to edit an older visit",
        })
        assert older_edit.status_code == 409
        assert "latest visit" in older_edit.json()["detail"].lower()

        latest_edit = client.patch(f"/api/visits/{second_visit_id}", json={
            "services": [{"service_name": "Beard Trim", "quantity": 1, "unit_price": 200}],
            "change_note": "Corrected latest visit price",
        })
        assert latest_edit.status_code == 200, latest_edit.text
        assert latest_edit.json()["visit"]["amount"] == 200

        reassignment = client.patch(f"/api/visits/{second_visit_id}", json={
            "customer_id": first_record["customer_id"] + 1,
            "change_note": "Do not allow customer reassignment",
        })
        assert reassignment.status_code in {400, 404}


def test_barber_customer_list_and_reviews_are_limited_to_visits_they_served():
    with TestClient(app) as client:
        login_as(client, "owner")
        reset = client.post("/api/demo/reset")
        assert reset.status_code == 200, reset.text
        branches = client.get("/api/branches").json()
        barbers = client.get("/api/barbers").json()
        first_barber = next(b for b in barbers if b["id"] == 1)
        other_barber = next(b for b in barbers if b["id"] != first_barber["id"])

        own_visit = client.post("/api/visits", json={
            "customer_name": "Shared Timeline Customer",
            "customer_phone": "9876500041",
            "customer_location": "Pune",
            "branch_id": first_barber["branch_id"],
            "barber_id": first_barber["id"],
            "services": [{"service_name": "Haircut", "quantity": 1, "unit_price": 300}],
        })
        assert own_visit.status_code == 201, own_visit.text
        customer_id = own_visit.json()["visit"]["customer_id"]
        own_visit_id = own_visit.json()["visit"]["id"]

        other_visit = client.post("/api/visits", json={
            "customer_id": customer_id,
            "branch_id": other_barber["branch_id"],
            "barber_id": other_barber["id"],
            "services": [{"service_name": "Beard Trim", "quantity": 1, "unit_price": 150}],
        })
        assert other_visit.status_code == 201, other_visit.text
        other_visit_id = other_visit.json()["visit"]["id"]

        own_feedback = client.post("/api/feedback", json={
            "visit_id": own_visit_id,
            "rating": 5,
            "comment": "Very satisfied with the haircut.",
        })
        assert own_feedback.status_code == 201, own_feedback.text
        other_feedback = client.post("/api/feedback", json={
            "visit_id": other_visit_id,
            "rating": 2,
            "comment": "This feedback belongs to another barber's visit.",
        })
        assert other_feedback.status_code == 201, other_feedback.text

        hidden_customer_visit = client.post("/api/visits", json={
            "customer_name": "Only Other Barber Customer",
            "customer_phone": "9876500042",
            "customer_location": "Pune",
            "branch_id": other_barber["branch_id"],
            "barber_id": other_barber["id"],
            "services": [{"service_name": "Hair Wash", "quantity": 1, "unit_price": 100}],
        })
        assert hidden_customer_visit.status_code == 201, hidden_customer_visit.text
        hidden_customer_id = hidden_customer_visit.json()["visit"]["customer_id"]

        login_as(client, "aarav")
        customer_ids = {customer["id"] for customer in client.get("/api/customers").json()}
        assert customer_id in customer_ids
        assert hidden_customer_id not in customer_ids

        # Customer reviews appear as visit-linked notifications, not audit-log entries.
        notifications = client.get("/api/notifications")
        assert notifications.status_code == 200, notifications.text
        notification_payload = notifications.json()
        notification_rows = notification_payload["notifications"]
        assert notification_payload["count"] == len(notification_rows)
        own_notification = next((row for row in notification_rows if row["visit_id"] == own_visit_id), None)
        assert own_notification is not None
        assert own_notification["message"] == "Very satisfied with the haircut."
        assert own_notification["rating"] == 5
        assert all(row["visit_id"] != other_visit_id for row in notification_rows)
        assert client.get("/api/audit-logs").status_code == 403
        assert client.get("/api/feedback").status_code == 403
        assert client.post("/api/feedback", json={
            "visit_id": own_visit_id, "rating": 4, "comment": "Barbers cannot manually enter customer feedback."
        }).status_code == 403

        reviews = client.get(f"/api/customers/{customer_id}/reviews")
        assert reviews.status_code == 200, reviews.text
        review_data = reviews.json()
        assert review_data["visit_count"] == 1
        assert review_data["review_count"] == 1
        assert [review["visit_id"] for review in review_data["reviews"]] == [own_visit_id]
        assert review_data["reviews"][0]["comment"] == "Very satisfied with the haircut."

        hidden_history = client.get(f"/api/customers/{hidden_customer_id}/reviews")
        assert hidden_history.status_code == 404
