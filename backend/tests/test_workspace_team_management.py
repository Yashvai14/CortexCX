import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.main import app

client = TestClient(app)


def test_milestone_5_workspace_team_management():
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
                "company_name": f"Team Alpha {suffix_a}",
                "company_slug": f"team-alpha-{suffix_a}",
                "full_name": "Owner Alpha",
                "email": f"owner_alpha_{suffix_a}@example.com",
                "password": password,
            },
        )
        assert reg_owner_a.status_code == 201
        owner_a_data = reg_owner_a.json()
        owner_a_token = owner_a_data["token"]["access_token"]
        owner_a_refresh_token = owner_a_data["token"]["refresh_token"]
        owner_a_id = owner_a_data["user"]["id"]
        workspace_a_id = owner_a_data["workspace"]["id"]

        # 2. Owner A adds Admin A via POST /workspaces/{id}/members
        add_admin_a = client.post(
            f"/workspaces/{workspace_a_id}/members",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Admin Alpha",
                "email": f"admin_alpha_{suffix_a}@example.com",
                "password": password,
                "role": "admin",
            },
        )
        assert add_admin_a.status_code == 201, f"Failed: {add_admin_a.text}"
        admin_a_id = add_admin_a.json()["id"]

        login_admin_a = client.post(
            "/auth/login",
            data={
                "username": f"admin_alpha_{suffix_a}@example.com",
                "password": password,
            },
        )
        assert login_admin_a.status_code == 200
        admin_a_token = login_admin_a.json()["access_token"]

        # 3. Owner A adds Agent A via POST /workspaces/{id}/members
        add_agent_a = client.post(
            f"/workspaces/{workspace_a_id}/members",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Agent Alpha",
                "email": f"agent_alpha_{suffix_a}@example.com",
                "password": password,
                "role": "agent",
            },
        )
        assert add_agent_a.status_code == 201
        agent_a_id = add_agent_a.json()["id"]

        login_agent_a = client.post(
            "/auth/login",
            data={
                "username": f"agent_alpha_{suffix_a}@example.com",
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
                "company_name": f"Team Beta {suffix_b}",
                "company_slug": f"team-beta-{suffix_b}",
                "full_name": "Owner Beta",
                "email": f"owner_beta_{suffix_b}@example.com",
                "password": password,
            },
        )
        assert reg_owner_b.status_code == 201
        owner_b_data = reg_owner_b.json()
        owner_b_token = owner_b_data["token"]["access_token"]
        owner_b_id = owner_b_data["user"]["id"]
        workspace_b_id = owner_b_data["workspace"]["id"]

        # =============================================================
        # 1. Authenticated owner can access own workspace
        # =============================================================
        print("\n--- Test 1: Authenticated owner accesses own workspace ---")
        res_ws = client.get(
            f"/workspaces/{workspace_a_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert res_ws.status_code == 200
        assert res_ws.json()["id"] == workspace_a_id
        assert res_ws.json()["name"] == f"Team Alpha {suffix_a}"

        # =============================================================
        # 2. User cannot access another workspace (404)
        # =============================================================
        print("\n--- Test 2: User cannot access another workspace (404) ---")
        cross_ws = client.get(
            f"/workspaces/{workspace_b_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert cross_ws.status_code == 404

        # =============================================================
        # 3. Owner can update workspace
        # =============================================================
        print("\n--- Test 3: Owner updates workspace ---")
        update_ws = client.patch(
            f"/workspaces/{workspace_a_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "name": f"Renamed Alpha {suffix_a}",
                "website": "https://alpha.example.com",
                "industry": "SaaS Tech",
            },
        )
        assert update_ws.status_code == 200
        assert update_ws.json()["name"] == f"Renamed Alpha {suffix_a}"
        assert update_ws.json()["website"] == "https://alpha.example.com"

        # =============================================================
        # 4. Unauthorized user cannot update workspace (403)
        # =============================================================
        print("\n--- Test 4: Admin and Agent cannot update workspace (403) ---")
        admin_update_ws = client.patch(
            f"/workspaces/{workspace_a_id}",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={"name": "Hacked By Admin"},
        )
        assert admin_update_ws.status_code == 403

        agent_update_ws = client.patch(
            f"/workspaces/{workspace_a_id}",
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={"name": "Hacked By Agent"},
        )
        assert agent_update_ws.status_code == 403

        # =============================================================
        # 5, 6, 7. Owner, Admin, Agent can list members
        # =============================================================
        print("\n--- Tests 5, 6, 7: List members for Owner, Admin, and Agent ---")
        owner_list = client.get(
            f"/workspaces/{workspace_a_id}/members",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert owner_list.status_code == 200
        members = owner_list.json()
        assert len(members) >= 3
        m_ids = [m["id"] for m in members]
        assert owner_a_id in m_ids
        assert admin_a_id in m_ids
        assert agent_a_id in m_ids
        assert owner_b_id not in m_ids

        admin_list = client.get(
            f"/workspaces/{workspace_a_id}/members",
            headers={"Authorization": f"Bearer {admin_a_token}"},
        )
        assert admin_list.status_code == 200
        assert len(admin_list.json()) == len(members)

        agent_list = client.get(
            f"/workspaces/{workspace_a_id}/members",
            headers={"Authorization": f"Bearer {agent_a_token}"},
        )
        assert agent_list.status_code == 200
        assert len(agent_list.json()) == len(members)

        # =============================================================
        # 8. Owner can add member
        # =============================================================
        print("\n--- Test 8: Owner adds new agent member ---")
        add_by_owner = client.post(
            f"/workspaces/{workspace_a_id}/members",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Agent Two Alpha",
                "email": f"agent2_alpha_{suffix_a}@example.com",
                "password": password,
                "role": "agent",
            },
        )
        assert add_by_owner.status_code == 201
        agent2_id = add_by_owner.json()["id"]

        # =============================================================
        # 9. Admin can add agent
        # =============================================================
        print("\n--- Test 9: Admin adds agent ---")
        add_by_admin = client.post(
            f"/workspaces/{workspace_a_id}/members",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={
                "full_name": "Agent Three Alpha",
                "email": f"agent3_alpha_{suffix_a}@example.com",
                "password": password,
                "role": "agent",
            },
        )
        assert add_by_admin.status_code == 201
        agent3_id = add_by_admin.json()["id"]

        # =============================================================
        # 10. Admin cannot create owner (403)
        # =============================================================
        print("\n--- Test 10: Admin cannot create owner (403) ---")
        admin_create_owner = client.post(
            f"/workspaces/{workspace_a_id}/members",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={
                "full_name": "New Owner By Admin",
                "email": f"owner_fail_{suffix_a}@example.com",
                "password": password,
                "role": "owner",
            },
        )
        assert admin_create_owner.status_code == 403

        # =============================================================
        # 11. Agent cannot add member (403)
        # =============================================================
        print("\n--- Test 11: Agent cannot add member (403) ---")
        agent_add_fail = client.post(
            f"/workspaces/{workspace_a_id}/members",
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={
                "full_name": "New Member By Agent",
                "email": f"agent_fail_{suffix_a}@example.com",
                "password": password,
                "role": "agent",
            },
        )
        assert agent_add_fail.status_code == 403

        # =============================================================
        # 12. Owner can update member role
        # =============================================================
        print("\n--- Test 12: Owner updates member role ---")
        owner_updates_agent = client.patch(
            f"/workspaces/{workspace_a_id}/members/{agent2_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"role": "admin"},
        )
        assert owner_updates_agent.status_code == 200
        assert owner_updates_agent.json()["role"] == "admin"

        # =============================================================
        # 13. Admin cannot promote user to owner (403)
        # =============================================================
        print("\n--- Test 13: Admin cannot promote user to owner (403) ---")
        admin_promotes_owner = client.patch(
            f"/workspaces/{workspace_a_id}/members/{agent3_id}",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={"role": "owner"},
        )
        assert admin_promotes_owner.status_code == 403

        # =============================================================
        # 14. Agent cannot update roles (403)
        # =============================================================
        print("\n--- Test 14: Agent cannot update roles (403) ---")
        agent_updates_role = client.patch(
            f"/workspaces/{workspace_a_id}/members/{agent3_id}",
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={"role": "admin"},
        )
        assert agent_updates_role.status_code == 403

        # =============================================================
        # 17. Final owner cannot be deleted or demoted (400)
        # =============================================================
        print("\n--- Test 17: Final owner cannot be deleted or demoted (400) ---")
        demote_final_owner = client.patch(
            f"/workspaces/{workspace_a_id}/members/{owner_a_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"role": "agent"},
        )
        assert demote_final_owner.status_code == 400
        assert "final workspace owner" in demote_final_owner.text.lower()

        delete_final_owner = client.delete(
            f"/workspaces/{workspace_a_id}/members/{owner_a_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert delete_final_owner.status_code == 400
        assert "final workspace owner" in delete_final_owner.text.lower()

        # =============================================================
        # 15. Authorized user can remove member
        # =============================================================
        print("\n--- Test 15: Admin removes Agent 3 ---")
        admin_removes_agent3 = client.delete(
            f"/workspaces/{workspace_a_id}/members/{agent3_id}",
            headers={"Authorization": f"Bearer {admin_a_token}"},
        )
        assert admin_removes_agent3.status_code == 200
        assert admin_removes_agent3.json() == {"message": "Member removed successfully"}

        # =============================================================
        # 16. Unauthorized user (Agent) cannot remove member (403)
        # =============================================================
        print("\n--- Test 16: Agent cannot remove member (403) ---")
        agent_removes_fail = client.delete(
            f"/workspaces/{workspace_a_id}/members/{agent2_id}",
            headers={"Authorization": f"Bearer {agent_a_token}"},
        )
        assert agent_removes_fail.status_code == 403

        # =============================================================
        # 18. Cross-workspace member modification is rejected (404)
        # =============================================================
        print("\n--- Test 18: Cross-workspace member modification returns 404 ---")
        cross_member_patch = client.patch(
            f"/workspaces/{workspace_b_id}/members/{owner_b_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"full_name": "Hacked Member"},
        )
        assert cross_member_patch.status_code == 404

        cross_member_delete = client.delete(
            f"/workspaces/{workspace_b_id}/members/{owner_b_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert cross_member_delete.status_code == 404

        # =============================================================
        # 19. Unauthenticated request returns 401
        # =============================================================
        print("\n--- Test 19: Unauthenticated request returns 401 ---")
        unauth_req = client.get(f"/workspaces/{workspace_a_id}")
        assert unauth_req.status_code == 401

        # =============================================================
        # 20. Invalid access token returns 401
        # =============================================================
        print("\n--- Test 20: Invalid access token returns 401 ---")
        invalid_token_req = client.get(
            f"/workspaces/{workspace_a_id}",
            headers={"Authorization": "Bearer not.valid.token"},
        )
        assert invalid_token_req.status_code == 401

        # =============================================================
        # 21. Refresh token cannot be used as access token (401)
        # =============================================================
        print("\n--- Test 21: Refresh token as access token returns 401 ---")
        refresh_as_access = client.get(
            f"/workspaces/{workspace_a_id}",
            headers={"Authorization": f"Bearer {owner_a_refresh_token}"},
        )
        assert refresh_as_access.status_code == 401

        print("\n ALL 21 WORKSPACE AND TEAM MANAGEMENT TESTS PASSED SUCCESSFULLY!")

    finally:
        db.close()


if __name__ == "__main__":
    test_milestone_5_workspace_team_management()
