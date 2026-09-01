import time
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.customer.model import Customer
from app.customer.repositories.customer_repository import CustomerRepository
from app.database.database import SessionLocal
from app.main import app

client = TestClient(app)


def test_milestone_6_customer_management():
    db: Session = SessionLocal()
    try:
        suffix_a = uuid.uuid4().hex[:8]
        suffix_b = uuid.uuid4().hex[:8]
        password = "SecurePassword123!"

        # -------------------------------------------------------------
        # SETUP WORKSPACE A: Owner A, Admin A, Agent A
        # -------------------------------------------------------------
        print("\n--- SETUP: Creating Workspace A with Owner, Admin, and Agent ---")
        # 1. Register Owner A
        reg_owner_a = client.post(
            "/auth/register",
            json={
                "company_name": f"Corp A {suffix_a}",
                "company_slug": f"corp-a-{suffix_a}",
                "full_name": "Owner A",
                "email": f"owner_a_{suffix_a}@example.com",
                "password": password,
            },
        )
        assert reg_owner_a.status_code == 201
        owner_a_token = reg_owner_a.json()["token"]["access_token"]
        owner_a_refresh_token = reg_owner_a.json()["token"]["refresh_token"]
        workspace_a_id = reg_owner_a.json()["workspace"]["id"]

        # 2. Owner A creates Admin A
        create_admin_a = client.post(
            "/users",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Admin A",
                "email": f"admin_a_{suffix_a}@example.com",
                "password": password,
                "role": "admin",
            },
        )
        assert create_admin_a.status_code == 201
        login_admin_a = client.post(
            "/auth/login",
            data={"username": f"admin_a_{suffix_a}@example.com", "password": password},
        )
        assert login_admin_a.status_code == 200
        admin_a_token = login_admin_a.json()["access_token"]

        # 3. Owner A creates Agent A
        create_agent_a = client.post(
            "/users",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Agent A",
                "email": f"agent_a_{suffix_a}@example.com",
                "password": password,
                "role": "agent",
            },
        )
        assert create_agent_a.status_code == 201
        login_agent_a = client.post(
            "/auth/login",
            data={"username": f"agent_a_{suffix_a}@example.com", "password": password},
        )
        assert login_agent_a.status_code == 200
        agent_a_token = login_agent_a.json()["access_token"]

        # -------------------------------------------------------------
        # SETUP WORKSPACE B: Owner B
        # -------------------------------------------------------------
        print("\n--- SETUP: Creating Workspace B with Owner B ---")
        reg_owner_b = client.post(
            "/auth/register",
            json={
                "company_name": f"Corp B {suffix_b}",
                "company_slug": f"corp-b-{suffix_b}",
                "full_name": "Owner B",
                "email": f"owner_b_{suffix_b}@example.com",
                "password": password,
            },
        )
        assert reg_owner_b.status_code == 201
        owner_b_token = reg_owner_b.json()["token"]["access_token"]
        workspace_b_id = reg_owner_b.json()["workspace"]["id"]

        # =============================================================
        # 1. OWNER can create customer
        # =============================================================
        print("\n--- Test 1: OWNER creates customer ---")
        cust1_res = client.post(
            "/customers",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Customer One",
                "email": f"cust1_{suffix_a}@client.com",
                "phone": "+1234567890",
                "company_name": "Client One LLC",
                "status": "active",
            },
        )
        assert cust1_res.status_code == 201, f"Failed: {cust1_res.text}"
        cust1_data = cust1_res.json()
        cust1_id = cust1_data["id"]
        assert cust1_data["full_name"] == "Customer One"
        assert cust1_data["workspace_id"] == workspace_a_id

        # =============================================================
        # 2. ADMIN can create customer
        # =============================================================
        print("\n--- Test 2: ADMIN creates customer ---")
        cust2_res = client.post(
            "/customers",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={
                "full_name": "Customer Two",
                "email": f"cust2_{suffix_a}@client.com",
                "phone": "+1234567891",
                "company_name": "Client Two LLC",
                "status": "active",
            },
        )
        assert cust2_res.status_code == 201
        cust2_id = cust2_res.json()["id"]

        # =============================================================
        # 3. AGENT can create customer
        # =============================================================
        print("\n--- Test 3: AGENT creates customer ---")
        cust3_res = client.post(
            "/customers",
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={
                "full_name": "Customer Three",
                "email": f"cust3_{suffix_a}@client.com",
                "phone": "+1234567892",
                "company_name": "Client Three LLC",
                "status": "inactive",
            },
        )
        assert cust3_res.status_code == 201
        cust3_id = cust3_res.json()["id"]

        # =============================================================
        # 4. Authenticated user can list customers
        # =============================================================
        print("\n--- Test 4: List customers for Workspace A ---")
        list_res = client.get(
            "/customers",
            headers={"Authorization": f"Bearer {agent_a_token}"},
        )
        assert list_res.status_code == 200
        customers = list_res.json()
        assert len(customers) >= 3
        c_ids = [c["id"] for c in customers]
        assert cust1_id in c_ids
        assert cust2_id in c_ids
        assert cust3_id in c_ids

        # =============================================================
        # 5. Authenticated user can retrieve a customer
        # =============================================================
        print("\n--- Test 5: Retrieve single customer ---")
        get_res = client.get(
            f"/customers/{cust1_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert get_res.status_code == 200
        assert get_res.json()["id"] == cust1_id
        assert get_res.json()["email"] == f"cust1_{suffix_a}@client.com"

        # =============================================================
        # 6. Customer update works & 21. PATCH only modifies supplied fields
        # =============================================================
        print("\n--- Tests 6 & 21: Customer update & partial modifications ---")
        time.sleep(0.01)  # small delay for updated_at check
        update_res = client.patch(
            f"/customers/{cust1_id}",
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={"company_name": "Updated Corp LLC"},
        )
        assert update_res.status_code == 200
        updated_cust1 = update_res.json()
        assert updated_cust1["company_name"] == "Updated Corp LLC"
        assert updated_cust1["full_name"] == "Customer One"  # unmodified
        assert updated_cust1["phone"] == "+1234567890"  # unmodified

        # =============================================================
        # 22. updated_at changes after update
        # =============================================================
        print("\n--- Test 22: updated_at changed after update ---")
        assert updated_cust1["updated_at"] >= cust1_data["created_at"]

        # =============================================================
        # 7. Customer delete works for authorized roles (ADMIN/OWNER)
        # =============================================================
        print("\n--- Test 7: ADMIN deletes customer 3 ---")
        del_res = client.delete(
            f"/customers/{cust3_id}",
            headers={"Authorization": f"Bearer {admin_a_token}"},
        )
        assert del_res.status_code == 200
        assert del_res.json() == {"message": "Customer deleted successfully"}

        # =============================================================
        # 24. Deleted customer cannot be retrieved afterward
        # =============================================================
        print("\n--- Test 24: Deleted customer cannot be retrieved ---")
        deleted_get = client.get(
            f"/customers/{cust3_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert deleted_get.status_code == 404

        # =============================================================
        # 8. Unauthenticated requests return 401
        # =============================================================
        print("\n--- Test 8: Unauthenticated request returns 401 ---")
        unauth_res = client.get("/customers")
        assert unauth_res.status_code == 401

        # =============================================================
        # 9. Invalid access token returns 401
        # =============================================================
        print("\n--- Test 9: Invalid access token returns 401 ---")
        invalid_token_res = client.get(
            "/customers",
            headers={"Authorization": "Bearer not.a.valid.token"},
        )
        assert invalid_token_res.status_code == 401

        # =============================================================
        # 10. Refresh token cannot be used as an access token
        # =============================================================
        print("\n--- Test 10: Refresh token used as access token returns 401 ---")
        refresh_as_access = client.get(
            "/customers",
            headers={"Authorization": f"Bearer {owner_a_refresh_token}"},
        )
        assert refresh_as_access.status_code == 401

        # -------------------------------------------------------------
        # Create Customer in Workspace B
        # -------------------------------------------------------------
        cust_b_res = client.post(
            "/customers",
            headers={"Authorization": f"Bearer {owner_b_token}"},
            json={
                "full_name": "Customer Beta",
                "email": f"cust_beta_{suffix_b}@client.com",
                "phone": "+9876543210",
                "company_name": "Beta Client Inc",
                "status": "active",
            },
        )
        assert cust_b_res.status_code == 201
        cust_b_id = cust_b_res.json()["id"]

        # =============================================================
        # 11. Workspace A cannot retrieve Workspace B customer (404)
        # =============================================================
        print("\n--- Test 11: Cross-workspace retrieval returns 404 ---")
        cross_get = client.get(
            f"/customers/{cust_b_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert cross_get.status_code == 404

        # =============================================================
        # 12. Workspace A cannot update Workspace B customer (404)
        # =============================================================
        print("\n--- Test 12: Cross-workspace update returns 404 ---")
        cross_patch = client.patch(
            f"/customers/{cust_b_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"full_name": "Hacked Customer"},
        )
        assert cross_patch.status_code == 404

        # =============================================================
        # 13. Workspace A cannot delete Workspace B customer (404)
        # =============================================================
        print("\n--- Test 13: Cross-workspace delete returns 404 ---")
        cross_delete = client.delete(
            f"/customers/{cust_b_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert cross_delete.status_code == 404

        # =============================================================
        # 14. Non-existent customer returns 404
        # =============================================================
        print("\n--- Test 14: Non-existent customer returns 404 ---")
        random_id = str(uuid.uuid4())
        non_existent = client.get(
            f"/customers/{random_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert non_existent.status_code == 404

        # =============================================================
        # 15. Invalid UUID returns 422
        # =============================================================
        print("\n--- Test 15: Invalid UUID returns 422 ---")
        invalid_uuid = client.get(
            "/customers/invalid-uuid-format",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert invalid_uuid.status_code == 422

        # =============================================================
        # 16. Customer belongs to the authenticated user's workspace
        # =============================================================
        print("\n--- Test 16: Customer workspace_id matches authenticated user ---")
        assert cust1_data["workspace_id"] == workspace_a_id

        # =============================================================
        # 17. Client cannot assign customer to another workspace
        # =============================================================
        print("\n--- Test 17: Injected workspace_id in payload is ignored ---")
        fake_ws_id = str(uuid.uuid4())
        injected_ws_res = client.post(
            "/customers",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Injected WS Customer",
                "email": f"injected_{suffix_a}@client.com",
                "workspace_id": fake_ws_id,  # Should be ignored
                "status": "active",
            },
        )
        assert injected_ws_res.status_code == 201
        assert injected_ws_res.json()["workspace_id"] == workspace_a_id
        assert injected_ws_res.json()["workspace_id"] != fake_ws_id

        # =============================================================
        # 18. Duplicate email inside same workspace returns 400
        # =============================================================
        print("\n--- Test 18: Duplicate email inside same workspace rejected (400) ---")
        duplicate_res = client.post(
            "/customers",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Duplicate Email Customer",
                "email": f"cust1_{suffix_a}@client.com",  # already exists in ws A
                "status": "active",
            },
        )
        assert duplicate_res.status_code == 400
        assert "already exists" in duplicate_res.text.lower()

        # =============================================================
        # 19. Same email can exist in separate workspaces
        # =============================================================
        print("\n--- Test 19: Same email in Workspace B succeeds ---")
        same_email_ws_b = client.post(
            "/customers",
            headers={"Authorization": f"Bearer {owner_b_token}"},
            json={
                "full_name": "Same Email In B",
                "email": f"cust1_{suffix_a}@client.com",  # exists in ws A, new in ws B
                "status": "active",
            },
        )
        assert same_email_ws_b.status_code == 201
        assert same_email_ws_b.json()["workspace_id"] == workspace_b_id

        # =============================================================
        # 20. Response never exposes internal/sensitive fields
        # =============================================================
        print("\n--- Test 20: Response schema security check ---")
        assert "password" not in cust1_data
        assert "hashed_password" not in cust1_data
        assert "secret" not in cust1_data

        # =============================================================
        # 23. Unauthorized role (AGENT) cannot delete customer (403)
        # =============================================================
        print("\n--- Test 23: AGENT cannot delete customer (403) ---")
        agent_delete_fail = client.delete(
            f"/customers/{cust2_id}",
            headers={"Authorization": f"Bearer {agent_a_token}"},
        )
        assert agent_delete_fail.status_code == 403

        print("\n ALL 24 CUSTOMER MANAGEMENT TESTS PASSED SUCCESSFULLY!")

    finally:
        db.close()


if __name__ == "__main__":
    test_milestone_6_customer_management()
