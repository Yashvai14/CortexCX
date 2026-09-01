import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.model import User, UserRole
from app.auth.repositories.user_repository import UserRepository
from app.database.database import SessionLocal
from app.main import app

client = TestClient(app)


def test_milestone_5_workspace_and_user_management():
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
                "company_name": f"Workspace Alpha {suffix_a}",
                "company_slug": f"ws-alpha-{suffix_a}",
                "full_name": "Owner Alpha",
                "email": f"owner_a_{suffix_a}@example.com",
                "password": password,
            },
        )
        assert reg_owner_a.status_code == 201
        owner_a_data = reg_owner_a.json()
        owner_a_token = owner_a_data["token"]["access_token"]
        owner_a_id = owner_a_data["user"]["id"]
        workspace_a_id = owner_a_data["workspace"]["id"]

        # 2. Owner A creates Admin A via POST /users
        create_admin_a = client.post(
            "/users",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Admin Alpha",
                "email": f"admin_a_{suffix_a}@example.com",
                "password": password,
                "role": "admin",
            },
        )
        assert create_admin_a.status_code == 201, f"Failed to create Admin A: {create_admin_a.text}"
        admin_a_id = create_admin_a.json()["id"]

        # Login Admin A to get token
        login_admin_a = client.post(
            "/auth/login",
            data={"username": f"admin_a_{suffix_a}@example.com", "password": password},
        )
        assert login_admin_a.status_code == 200
        admin_a_token = login_admin_a.json()["access_token"]

        # 3. Owner A creates Agent A via POST /users
        create_agent_a = client.post(
            "/users",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Agent Alpha",
                "email": f"agent_a_{suffix_a}@example.com",
                "password": password,
                "role": "agent",
            },
        )
        assert create_agent_a.status_code == 201
        agent_a_id = create_agent_a.json()["id"]

        # Login Agent A to get token
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
                "company_name": f"Workspace Beta {suffix_b}",
                "company_slug": f"ws-beta-{suffix_b}",
                "full_name": "Owner Beta",
                "email": f"owner_b_{suffix_b}@example.com",
                "password": password,
            },
        )
        assert reg_owner_b.status_code == 201
        owner_b_data = reg_owner_b.json()
        owner_b_token = owner_b_data["token"]["access_token"]
        owner_b_id = owner_b_data["user"]["id"]
        workspace_b_id = owner_b_data["workspace"]["id"]

        # =============================================================
        # PART A: WORKSPACE MANAGEMENT TESTS
        # =============================================================

        # 1. Authenticated user can retrieve own workspace
        print("\n--- Test 1: Authenticated user retrieves own workspace ---")
        res_ws_me = client.get(
            "/workspaces/me",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert res_ws_me.status_code == 200
        ws_info = res_ws_me.json()
        assert ws_info["id"] == workspace_a_id
        assert ws_info["name"] == f"Workspace Alpha {suffix_a}"

        # 2. User cannot access another workspace (implicitly guaranteed by tenant scoping)
        print("\n--- Test 2: User in Workspace B gets Workspace B info only ---")
        res_ws_b = client.get(
            "/workspaces/me",
            headers={"Authorization": f"Bearer {owner_b_token}"},
        )
        assert res_ws_b.status_code == 200
        assert res_ws_b.json()["id"] == workspace_b_id
        assert res_ws_b.json()["id"] != workspace_a_id

        # 3. OWNER can update workspace
        print("\n--- Test 3: OWNER updates workspace ---")
        patch_ws = client.patch(
            "/workspaces/me",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "name": f"Renamed Alpha {suffix_a}",
                "website": "https://alpha.example.com",
                "industry": "Software SaaS",
            },
        )
        assert patch_ws.status_code == 200, f"Owner update failed: {patch_ws.text}"
        assert patch_ws.json()["name"] == f"Renamed Alpha {suffix_a}"
        assert patch_ws.json()["website"] == "https://alpha.example.com"
        assert patch_ws.json()["industry"] == "Software SaaS"

        # 4. ADMIN can update workspace (/workspaces/me)
        print("\n--- Test 4: ADMIN can update workspace (/workspaces/me) ---")
        admin_patch_ws = client.patch(
            "/workspaces/me",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={"name": "Updated by Admin"},
        )
        assert admin_patch_ws.status_code == 200

        # 5. AGENT cannot update workspace
        print("\n--- Test 5: AGENT cannot update workspace (403) ---")
        agent_patch_ws = client.patch(
            "/workspaces/me",
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={"name": "Hacked by Agent"},
        )
        assert agent_patch_ws.status_code == 403

        # 6. Unauthenticated request is rejected
        print("\n--- Test 6: Unauthenticated workspace request rejected (401) ---")
        unauth_ws = client.get("/workspaces/me")
        assert unauth_ws.status_code == 401

        # =============================================================
        # PART B: USER MANAGEMENT TESTS
        # =============================================================

        # 7. OWNER can list workspace users
        print("\n--- Test 7: OWNER lists workspace users ---")
        list_owner = client.get(
            "/users",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert list_owner.status_code == 200
        users_list = list_owner.json()
        assert len(users_list) >= 3
        user_ids = [u["id"] for u in users_list]
        assert owner_a_id in user_ids
        assert admin_a_id in user_ids
        assert agent_a_id in user_ids
        # Ensure no users from Workspace B are included
        assert owner_b_id not in user_ids

        # 8. ADMIN can list workspace users
        print("\n--- Test 8: ADMIN lists workspace users ---")
        list_admin = client.get(
            "/users",
            headers={"Authorization": f"Bearer {admin_a_token}"},
        )
        assert list_admin.status_code == 200
        assert len(list_admin.json()) == len(users_list)

        # 9. AGENT can view workspace users
        print("\n--- Test 9: AGENT lists workspace users ---")
        list_agent = client.get(
            "/users",
            headers={"Authorization": f"Bearer {agent_a_token}"},
        )
        assert list_agent.status_code == 200
        assert len(list_agent.json()) == len(users_list)

        # 10. OWNER can create user
        print("\n--- Test 10: OWNER creates new agent ---")
        created_by_owner = client.post(
            "/users",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Agent 2 Alpha",
                "email": f"agent2_a_{suffix_a}@example.com",
                "password": password,
                "role": "agent",
            },
        )
        assert created_by_owner.status_code == 201
        agent2_id = created_by_owner.json()["id"]

        # 11. ADMIN can create user
        print("\n--- Test 11: ADMIN creates new agent ---")
        created_by_admin = client.post(
            "/users",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={
                "full_name": "Agent 3 Alpha",
                "email": f"agent3_a_{suffix_a}@example.com",
                "password": password,
                "role": "agent",
            },
        )
        assert created_by_admin.status_code == 201
        agent3_id = created_by_admin.json()["id"]

        # 12. AGENT cannot create user
        print("\n--- Test 12: AGENT cannot create user (403) ---")
        agent_create_fail = client.post(
            "/users",
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={
                "full_name": "Hacker User",
                "email": f"hacker_{suffix_a}@example.com",
                "password": password,
                "role": "agent",
            },
        )
        assert agent_create_fail.status_code == 403

        # 13. User creation hashes password & 14. Password hash is never returned
        print("\n--- Tests 13 & 14: Password hashing verified & not returned in response ---")
        user_repo = UserRepository()
        db.expire_all()
        created_user_db = user_repo.get_by_id(db=db, obj_id=uuid.UUID(agent3_id))
        assert created_user_db is not None
        assert created_user_db.hashed_password != password
        assert created_user_db.hashed_password.startswith("$2b$") or created_user_db.hashed_password.startswith("$2a$")
        assert "hashed_password" not in created_by_admin.json()
        assert "password" not in created_by_admin.json()

        # 15. OWNER can update users
        print("\n--- Test 15: OWNER updates agent ---")
        owner_updates_agent = client.patch(
            "/users/" + agent2_id,
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Agent 2 Promoted",
                "role": "admin",
            },
        )
        assert owner_updates_agent.status_code == 200
        assert owner_updates_agent.json()["full_name"] == "Agent 2 Promoted"
        assert owner_updates_agent.json()["role"] == "admin"

        # 16. ADMIN cannot modify OWNER privileges and cannot promote users to OWNER
        print("\n--- Test 16: ADMIN cannot modify OWNER (403) & cannot promote to OWNER (403) ---")
        admin_modifies_owner = client.patch(
            "/users/" + owner_a_id,
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={"full_name": "Owner Demoted", "role": "agent"},
        )
        assert admin_modifies_owner.status_code == 403

        admin_promotes_to_owner = client.patch(
            "/users/" + agent3_id,
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={"role": "owner"},
        )
        assert admin_promotes_to_owner.status_code == 403

        admin_creates_owner = client.post(
            "/users",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={
                "full_name": "New Owner By Admin",
                "email": f"new_owner_fail_{suffix_a}@example.com",
                "password": password,
                "role": "owner",
            },
        )
        assert admin_creates_owner.status_code == 403

        # 17. AGENT cannot modify users
        print("\n--- Test 17: AGENT cannot modify users (403) ---")
        agent_updates_user = client.patch(
            "/users/" + agent3_id,
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={"full_name": "Agent Renamed"},
        )
        assert agent_updates_user.status_code == 403

        # 18. OWNER can delete appropriate users
        print("\n--- Test 18: OWNER deletes user ---")
        owner_deletes_agent = client.delete(
            "/users/" + agent2_id,
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert owner_deletes_agent.status_code == 200
        assert owner_deletes_agent.json() == {"message": "User deleted successfully"}

        # Verify deletion in DB
        db.expire_all()
        assert user_repo.get_by_id(db=db, obj_id=uuid.UUID(agent2_id)) is None

        # 19. ADMIN cannot delete OWNER
        print("\n--- Test 19: ADMIN cannot delete OWNER (403) ---")
        admin_deletes_owner = client.delete(
            "/users/" + owner_a_id,
            headers={"Authorization": f"Bearer {admin_a_token}"},
        )
        assert admin_deletes_owner.status_code == 403

        # 20. AGENT cannot delete users
        print("\n--- Test 20: AGENT cannot delete users (403) ---")
        agent_deletes_user = client.delete(
            "/users/" + agent3_id,
            headers={"Authorization": f"Bearer {agent_a_token}"},
        )
        assert agent_deletes_user.status_code == 403

        # 21. Cross-workspace user access is rejected (404)
        print("\n--- Test 21: Cross-workspace user access returns 404 ---")
        cross_get = client.get(
            "/users/" + owner_b_id,
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert cross_get.status_code == 404, f"Expected 404, got {cross_get.status_code}"

        # 22. Cross-workspace user modification is rejected (404)
        print("\n--- Test 22: Cross-workspace user modification returns 404 ---")
        cross_patch = client.patch(
            "/users/" + owner_b_id,
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"full_name": "Hacked Across Workspaces"},
        )
        assert cross_patch.status_code == 404, f"Expected 404, got {cross_patch.status_code}"

        # 23. Cross-workspace user deletion is rejected (404)
        print("\n--- Test 23: Cross-workspace user deletion returns 404 ---")
        cross_delete = client.delete(
            "/users/" + owner_b_id,
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert cross_delete.status_code == 404, f"Expected 404, got {cross_delete.status_code}"

        # 24. Invalid user UUID is handled correctly (422)
        print("\n--- Test 24: Invalid user UUID format returns 422 ---")
        invalid_uuid_get = client.get(
            "/users/invalid-uuid-string",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert invalid_uuid_get.status_code == 422

        # 25. Non-existent user UUID is handled correctly (404)
        print("\n--- Test 25: Non-existent UUID returns 404 ---")
        random_uuid = str(uuid.uuid4())
        non_existent_get = client.get(
            "/users/" + random_uuid,
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert non_existent_get.status_code == 404

        print("\n ALL 25 WORKSPACE AND USER MANAGEMENT TESTS PASSED SUCCESSFULLY!")

    finally:
        db.close()


if __name__ == "__main__":
    test_milestone_5_workspace_and_user_management()
