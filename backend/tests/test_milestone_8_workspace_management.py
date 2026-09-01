import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.main import app

client = TestClient(app)


def test_milestone_8_workspace_management():
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
                "company_name": f"M8 Corp Alpha {suffix_a}",
                "company_slug": f"m8-alpha-{suffix_a}",
                "full_name": "Owner Alpha M8",
                "email": f"owner_m8_a_{suffix_a}@example.com",
                "password": password,
            },
        )
        assert reg_owner_a.status_code == 201
        owner_a_data = reg_owner_a.json()
        owner_a_token = owner_a_data["token"]["access_token"]
        owner_a_refresh_token = owner_a_data["token"]["refresh_token"]
        owner_a_id = owner_a_data["user"]["id"]
        workspace_a_id = owner_a_data["workspace"]["id"]

        # 2. Owner A creates Admin A via POST /workspaces/users
        add_admin_a = client.post(
            "/workspaces/users",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Admin Alpha M8",
                "email": f"admin_m8_a_{suffix_a}@example.com",
                "password": password,
                "role": "admin",
            },
        )
        assert add_admin_a.status_code == 201, f"Failed: {add_admin_a.text}"
        admin_a_id = add_admin_a.json()["id"]

        login_admin_a = client.post(
            "/auth/login",
            data={
                "username": f"admin_m8_a_{suffix_a}@example.com",
                "password": password,
            },
        )
        assert login_admin_a.status_code == 200
        admin_a_token = login_admin_a.json()["access_token"]

        # 3. Owner A creates Agent A via POST /workspaces/users
        add_agent_a = client.post(
            "/workspaces/users",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Agent Alpha M8",
                "email": f"agent_m8_a_{suffix_a}@example.com",
                "password": password,
                "role": "agent",
            },
        )
        assert add_agent_a.status_code == 201
        agent_a_id = add_agent_a.json()["id"]

        login_agent_a = client.post(
            "/auth/login",
            data={
                "username": f"agent_m8_a_{suffix_a}@example.com",
                "password": password,
            },
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
                "company_name": f"M8 Corp Beta {suffix_b}",
                "company_slug": f"m8-beta-{suffix_b}",
                "full_name": "Owner Beta M8",
                "email": f"owner_m8_b_{suffix_b}@example.com",
                "password": password,
            },
        )
        assert reg_owner_b.status_code == 201
        owner_b_data = reg_owner_b.json()
        owner_b_token = owner_b_data["token"]["access_token"]
        owner_b_id = owner_b_data["user"]["id"]
        workspace_b_id = owner_b_data["workspace"]["id"]

        # =============================================================
        # 1, 2, 3. Owner, Admin, Agent can view workspace (/workspaces/me)
        # =============================================================
        print("\n--- Tests 1, 2, 3: Owner, Admin, Agent view workspace ---")
        res_owner_ws = client.get(
            "/workspaces/me",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert res_owner_ws.status_code == 200
        assert res_owner_ws.json()["id"] == workspace_a_id

        res_admin_ws = client.get(
            "/workspaces/me",
            headers={"Authorization": f"Bearer {admin_a_token}"},
        )
        assert res_admin_ws.status_code == 200
        assert res_admin_ws.json()["id"] == workspace_a_id

        res_agent_ws = client.get(
            "/workspaces/me",
            headers={"Authorization": f"Bearer {agent_a_token}"},
        )
        assert res_agent_ws.status_code == 200
        assert res_agent_ws.json()["id"] == workspace_a_id

        # =============================================================
        # 4, 5. Owner and Admin can update workspace (/workspaces/me)
        # =============================================================
        print("\n--- Tests 4 & 5: Owner and Admin update workspace ---")
        owner_patch = client.patch(
            "/workspaces/me",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "name": f"Renamed By Owner {suffix_a}",
                "slug": f"renamed-owner-{suffix_a}",
            },
        )
        assert owner_patch.status_code == 200
        assert owner_patch.json()["name"] == f"Renamed By Owner {suffix_a}"
        assert owner_patch.json()["slug"] == f"renamed-owner-{suffix_a}"

        admin_patch = client.patch(
            "/workspaces/me",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={
                "name": f"Renamed By Admin {suffix_a}",
                "website": "https://admin-updated.example.com",
            },
        )
        assert admin_patch.status_code == 200
        assert admin_patch.json()["name"] == f"Renamed By Admin {suffix_a}"

        # =============================================================
        # 6. Agent receives 403 when updating workspace
        # =============================================================
        print("\n--- Test 6: Agent cannot update workspace (403) ---")
        agent_patch = client.patch(
            "/workspaces/me",
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={"name": "Hacked By Agent"},
        )
        assert agent_patch.status_code == 403

        # =============================================================
        # 7, 8, 9. Owner, Admin, Agent can list workspace users
        # =============================================================
        print("\n--- Tests 7, 8, 9: Owner, Admin, Agent list workspace users ---")
        owner_list_users = client.get(
            "/workspaces/users",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert owner_list_users.status_code == 200
        users_a = owner_list_users.json()
        assert len(users_a) >= 3
        u_ids = [u["id"] for u in users_a]
        assert owner_a_id in u_ids
        assert admin_a_id in u_ids
        assert agent_a_id in u_ids
        assert owner_b_id not in u_ids

        admin_list_users = client.get(
            "/workspaces/users",
            headers={"Authorization": f"Bearer {admin_a_token}"},
        )
        assert admin_list_users.status_code == 200
        assert len(admin_list_users.json()) == len(users_a)

        agent_list_users = client.get(
            "/workspaces/users",
            headers={"Authorization": f"Bearer {agent_a_token}"},
        )
        assert agent_list_users.status_code == 200
        assert len(agent_list_users.json()) == len(users_a)

        # =============================================================
        # 10. Owner can create agent
        # =============================================================
        print("\n--- Test 10: Owner creates agent ---")
        owner_creates_agent = client.post(
            "/workspaces/users",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Agent Two M8",
                "email": f"agent2_m8_{suffix_a}@example.com",
                "password": password,
                "role": "agent",
            },
        )
        assert owner_creates_agent.status_code == 201
        agent2_id = owner_creates_agent.json()["id"]

        # =============================================================
        # 11. Admin can create agent
        # =============================================================
        print("\n--- Test 11: Admin creates agent ---")
        admin_creates_agent = client.post(
            "/workspaces/users",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={
                "full_name": "Agent Three M8",
                "email": f"agent3_m8_{suffix_a}@example.com",
                "password": password,
                "role": "agent",
            },
        )
        assert admin_creates_agent.status_code == 201
        agent3_id = admin_creates_agent.json()["id"]

        # Admin cannot create Owner
        admin_creates_owner = client.post(
            "/workspaces/users",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={
                "full_name": "New Owner By Admin",
                "email": f"owner_fail_m8_{suffix_a}@example.com",
                "password": password,
                "role": "owner",
            },
        )
        assert admin_creates_owner.status_code == 403

        # =============================================================
        # 12. Agent cannot create users (403)
        # =============================================================
        print("\n--- Test 12: Agent cannot create users (403) ---")
        agent_creates_user = client.post(
            "/workspaces/users",
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={
                "full_name": "User By Agent",
                "email": f"fail_user_m8_{suffix_a}@example.com",
                "password": password,
                "role": "agent",
            },
        )
        assert agent_creates_user.status_code == 403

        # =============================================================
        # 13. Owner can change user role
        # =============================================================
        print("\n--- Test 13: Owner changes user role ---")
        owner_changes_role = client.patch(
            f"/workspaces/users/{agent2_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"role": "admin"},
        )
        assert owner_changes_role.status_code == 200
        assert owner_changes_role.json()["role"] == "admin"

        # =============================================================
        # 14 & 15. Admin and Agent cannot change user role (403)
        # =============================================================
        print("\n--- Tests 14 & 15: Admin and Agent cannot change user role (403) ---")
        admin_changes_role = client.patch(
            f"/workspaces/users/{agent3_id}",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={"role": "admin"},
        )
        assert admin_changes_role.status_code == 403

        agent_changes_role = client.patch(
            f"/workspaces/users/{agent3_id}",
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={"role": "admin"},
        )
        assert agent_changes_role.status_code == 403

        # =============================================================
        # 25. Final owner cannot be demoted or deleted (400)
        # =============================================================
        print("\n--- Test 25: Final owner cannot be demoted or deleted (400) ---")
        owner_demotes_self = client.patch(
            f"/workspaces/users/{owner_a_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"role": "agent"},
        )
        assert owner_demotes_self.status_code == 400
        assert "final workspace owner" in owner_demotes_self.text.lower()

        owner_deletes_self = client.delete(
            f"/workspaces/users/{owner_a_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert owner_deletes_self.status_code == 400
        assert "final workspace owner" in owner_deletes_self.text.lower()

        # =============================================================
        # 17 & 18. Admin and Agent cannot delete workspace user (403)
        # =============================================================
        print("\n--- Tests 17 & 18: Admin and Agent cannot delete users (403) ---")
        admin_deletes_user = client.delete(
            f"/workspaces/users/{agent3_id}",
            headers={"Authorization": f"Bearer {admin_a_token}"},
        )
        assert admin_deletes_user.status_code == 403

        agent_deletes_user = client.delete(
            f"/workspaces/users/{agent3_id}",
            headers={"Authorization": f"Bearer {agent_a_token}"},
        )
        assert agent_deletes_user.status_code == 403

        # =============================================================
        # 16. Owner can delete workspace user
        # =============================================================
        print("\n--- Test 16: Owner deletes workspace user ---")
        owner_deletes_agent = client.delete(
            f"/workspaces/users/{agent3_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert owner_deletes_agent.status_code == 200
        assert owner_deletes_agent.json() == {"message": "User deleted successfully"}

        # =============================================================
        # 19, 20, 21. Cross-workspace access, modification, deletion rejected
        # =============================================================
        print("\n--- Tests 19, 20, 21: Cross-workspace rejection (404) ---")
        cross_patch = client.patch(
            f"/workspaces/users/{owner_b_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"role": "agent"},
        )
        assert cross_patch.status_code == 404

        cross_delete = client.delete(
            f"/workspaces/users/{owner_b_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert cross_delete.status_code == 404

        # =============================================================
        # 22. Unauthenticated requests return 401
        # =============================================================
        print("\n--- Test 22: Unauthenticated requests return 401 ---")
        unauth_get = client.get("/workspaces/me")
        assert unauth_get.status_code == 401

        unauth_users = client.get("/workspaces/users")
        assert unauth_users.status_code == 401

        # =============================================================
        # 23. Invalid access token returns 401
        # =============================================================
        print("\n--- Test 23: Invalid access token returns 401 ---")
        invalid_token_res = client.get(
            "/workspaces/me",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert invalid_token_res.status_code == 401

        # =============================================================
        # 24. Refresh token cannot be used as access token (401)
        # =============================================================
        print("\n--- Test 24: Refresh token as access token returns 401 ---")
        refresh_as_access = client.get(
            "/workspaces/me",
            headers={"Authorization": f"Bearer {owner_a_refresh_token}"},
        )
        assert refresh_as_access.status_code == 401

        print("\n ALL MILESTONE 8 WORKSPACE MANAGEMENT TESTS PASSED SUCCESSFULLY!")

    finally:
        db.close()


if __name__ == "__main__":
    test_milestone_8_workspace_management()
