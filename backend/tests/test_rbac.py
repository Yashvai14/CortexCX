import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token, create_refresh_token
from app.auth.model import User, UserRole
from app.auth.repositories.user_repository import UserRepository
from app.database.database import SessionLocal
from app.main import app

client = TestClient(app)


def test_rbac_authorization_matrix():
    db: Session = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:8]
        password = "SecurePassword123!"

        # Register User 1 (Default role: OWNER)
        reg_owner = client.post(
            "/auth/register",
            json={
                "company_name": f"Owner Corp {suffix}",
                "company_slug": f"owner-corp-{suffix}",
                "full_name": "Owner User",
                "email": f"owner_{suffix}@example.com",
                "password": password,
            },
        )
        assert reg_owner.status_code == 201
        owner_id = reg_owner.json()["user"]["id"]
        owner_access_token = reg_owner.json()["token"]["access_token"]
        owner_refresh_token = reg_owner.json()["token"]["refresh_token"]

        # Register User 2 -> Update role to ADMIN in database
        reg_admin = client.post(
            "/auth/register",
            json={
                "company_name": f"Admin Corp {suffix}",
                "company_slug": f"admin-corp-{suffix}",
                "full_name": "Admin User",
                "email": f"admin_{suffix}@example.com",
                "password": password,
            },
        )
        assert reg_admin.status_code == 201
        admin_id = reg_admin.json()["user"]["id"]
        admin_access_token = reg_admin.json()["token"]["access_token"]

        # Register User 3 -> Update role to AGENT in database
        reg_agent = client.post(
            "/auth/register",
            json={
                "company_name": f"Agent Corp {suffix}",
                "company_slug": f"agent-corp-{suffix}",
                "full_name": "Agent User",
                "email": f"agent_{suffix}@example.com",
                "password": password,
            },
        )
        assert reg_agent.status_code == 201
        agent_id = reg_agent.json()["user"]["id"]
        agent_access_token = reg_agent.json()["token"]["access_token"]

        # Update roles directly in PostgreSQL
        user_repo = UserRepository()
        admin_user = user_repo.get_by_id(db=db, obj_id=uuid.UUID(admin_id))
        assert admin_user is not None
        admin_user.role = UserRole.ADMIN

        agent_user = user_repo.get_by_id(db=db, obj_id=uuid.UUID(agent_id))
        assert agent_user is not None
        agent_user.role = UserRole.AGENT

        db.commit()

        # Verify DB role assignment
        db.expire_all()
        assert user_repo.get_by_id(db=db, obj_id=uuid.UUID(owner_id)).role == UserRole.OWNER
        assert user_repo.get_by_id(db=db, obj_id=uuid.UUID(admin_id)).role == UserRole.ADMIN
        assert user_repo.get_by_id(db=db, obj_id=uuid.UUID(agent_id)).role == UserRole.AGENT

        print("\n--- TEST 1: OWNER accessing OWNER endpoint ---")
        res1 = client.get(
            "/auth/owner-test",
            headers={"Authorization": f"Bearer {owner_access_token}"},
        )
        assert res1.status_code == 200, f"Expected 200, got {res1.status_code}: {res1.text}"
        assert res1.json() == {"message": "Owner access granted"}
        print("OWNER -> OWNER endpoint: 200 OK")

        print("\n--- TEST 2: ADMIN accessing OWNER endpoint ---")
        res2 = client.get(
            "/auth/owner-test",
            headers={"Authorization": f"Bearer {admin_access_token}"},
        )
        assert res2.status_code == 403, f"Expected 403, got {res2.status_code}: {res2.text}"
        print("ADMIN -> OWNER endpoint: 403 Forbidden")

        print("\n--- TEST 3: AGENT accessing OWNER endpoint ---")
        res3 = client.get(
            "/auth/owner-test",
            headers={"Authorization": f"Bearer {agent_access_token}"},
        )
        assert res3.status_code == 403, f"Expected 403, got {res3.status_code}: {res3.text}"
        print("AGENT -> OWNER endpoint: 403 Forbidden")

        print("\n--- TEST 4: OWNER accessing ADMIN endpoint ---")
        res4 = client.get(
            "/auth/admin-test",
            headers={"Authorization": f"Bearer {owner_access_token}"},
        )
        assert res4.status_code == 200, f"Expected 200, got {res4.status_code}: {res4.text}"
        assert res4.json() == {"message": "Admin access granted"}
        print("OWNER -> ADMIN endpoint: 200 OK")

        print("\n--- TEST 5: ADMIN accessing ADMIN endpoint ---")
        res5 = client.get(
            "/auth/admin-test",
            headers={"Authorization": f"Bearer {admin_access_token}"},
        )
        assert res5.status_code == 200, f"Expected 200, got {res5.status_code}: {res5.text}"
        assert res5.json() == {"message": "Admin access granted"}
        print("ADMIN -> ADMIN endpoint: 200 OK")

        print("\n--- TEST 6: AGENT accessing ADMIN endpoint ---")
        res6 = client.get(
            "/auth/admin-test",
            headers={"Authorization": f"Bearer {agent_access_token}"},
        )
        assert res6.status_code == 403, f"Expected 403, got {res6.status_code}: {res6.text}"
        print("AGENT -> ADMIN endpoint: 403 Forbidden")

        print("\n--- TEST 7: No authentication on protected endpoint ---")
        res7 = client.get("/auth/admin-test")
        assert res7.status_code == 401, f"Expected 401, got {res7.status_code}"
        print("Unauthenticated -> 401 Unauthorized")

        print("\n--- TEST 8: Invalid access token ---")
        res8 = client.get(
            "/auth/admin-test",
            headers={"Authorization": "Bearer invalid.access.token"},
        )
        assert res8.status_code == 401, f"Expected 401, got {res8.status_code}"
        print("Invalid Token -> 401 Unauthorized")

        print("\n--- TEST 9: Refresh token used as access token ---")
        res9 = client.get(
            "/auth/admin-test",
            headers={"Authorization": f"Bearer {owner_refresh_token}"},
        )
        assert res9.status_code == 401, f"Expected 401, got {res9.status_code}"
        print("Refresh Token as Bearer -> 401 Unauthorized")

        print("\n ALL RBAC TESTS PASSED SUCCESSFULLY!")

    finally:
        db.close()


if __name__ == "__main__":
    test_rbac_authorization_matrix()
