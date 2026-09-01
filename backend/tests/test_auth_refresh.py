import uuid
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token, create_refresh_token
from app.auth.model import RefreshToken, User
from app.auth.repositories.refresh_token_repository import RefreshTokenRepository
from app.auth.repositories.user_repository import UserRepository
from app.database.database import SessionLocal
from app.main import app

client = TestClient(app)


def test_full_refresh_token_flow():
    db: Session = SessionLocal()
    try:
        unique_suffix = uuid.uuid4().hex[:8]
        company_name = f"TestCorp {unique_suffix}"
        company_slug = f"testcorp-{unique_suffix}"
        email = f"user_{unique_suffix}@example.com"
        password = "SecurePassword123!"

        # -------------------------------------------------------------
        # 1. Register a NEW user
        # -------------------------------------------------------------
        print("\n--- 1. Registering new user ---")
        register_payload = {
            "company_name": company_name,
            "company_slug": company_slug,
            "full_name": "Test User",
            "email": email,
            "password": password,
        }
        reg_response = client.post("/auth/register", json=register_payload)
        assert reg_response.status_code == 201, f"Registration failed: {reg_response.text}"
        reg_data = reg_response.json()

        user_id = reg_data["user"]["id"]
        reg_refresh_token = reg_data["token"]["refresh_token"]
        reg_access_token = reg_data["token"]["access_token"]
        print(f"Registered user ID: {user_id}")

        # Verify DB state after registration
        repo = RefreshTokenRepository()
        db_token = repo.get_by_token(db=db, token=reg_refresh_token)
        assert db_token is not None, "Refresh token record not found in PostgreSQL"
        assert db_token.is_revoked is False, "New refresh token must not be revoked"
        print("Registration DB state verified successfully.")

        # -------------------------------------------------------------
        # 2. Login
        # -------------------------------------------------------------
        print("\n--- 2. Logging in ---")
        login_response = client.post(
            "/auth/login",
            data={"username": email, "password": password},
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        login_data = login_response.json()
        login_refresh_token = login_data["refresh_token"]
        login_access_token = login_data["access_token"]
        print("Login successful, received refresh token.")

        # -------------------------------------------------------------
        # 3. Call POST /auth/refresh with the login refresh token
        # -------------------------------------------------------------
        print("\n--- 3. Calling POST /auth/refresh ---")
        refresh_response = client.post(
            "/auth/refresh",
            json={"refresh_token": login_refresh_token},
        )
        assert refresh_response.status_code == 200, f"Refresh failed: {refresh_response.text}"
        refresh_data = refresh_response.json()
        assert "access_token" in refresh_data
        assert "refresh_token" in refresh_data
        assert refresh_data["token_type"] == "bearer"

        new_access_token = refresh_data["access_token"]
        new_refresh_token = refresh_data["refresh_token"]
        assert new_refresh_token != login_refresh_token, "Rotated refresh token must be distinct from old token"
        print("Refresh succeeded, new token pair returned.")

        # -------------------------------------------------------------
        # 4. Verify PostgreSQL state after refresh (Rotation check)
        # -------------------------------------------------------------
        print("\n--- 4. Verifying database state for token rotation ---")
        db.expire_all()
        old_token_record = repo.get_by_token(db=db, token=login_refresh_token)
        assert old_token_record is not None
        assert old_token_record.is_revoked is True, "Old refresh token must be marked is_revoked = True"

        new_token_record = repo.get_by_token(db=db, token=new_refresh_token)
        assert new_token_record is not None, "New refresh token must exist in PostgreSQL"
        assert new_token_record.is_revoked is False, "New refresh token must have is_revoked = False"
        print("PostgreSQL token rotation state verified: Old token revoked, new token active.")

        # -------------------------------------------------------------
        # 5. Try using the OLD (revoked) refresh token again -> 401
        # -------------------------------------------------------------
        print("\n--- 5. Attempting to reuse revoked refresh token ---")
        replay_response = client.post(
            "/auth/refresh",
            json={"refresh_token": login_refresh_token},
        )
        assert replay_response.status_code == 401, f"Expected 401 for revoked token, got {replay_response.status_code}"
        print("Revoked token properly rejected with 401 Unauthorized.")

        # -------------------------------------------------------------
        # 6. Try using an ACCESS token on /auth/refresh -> 401
        # -------------------------------------------------------------
        print("\n--- 6. Attempting to use access token on /auth/refresh ---")
        access_as_refresh_response = client.post(
            "/auth/refresh",
            json={"refresh_token": new_access_token},
        )
        assert access_as_refresh_response.status_code == 401, f"Expected 401 for access token, got {access_as_refresh_response.status_code}"
        print("Access token properly rejected with 401 Unauthorized.")

        # -------------------------------------------------------------
        # 7. Try an invalid / random token -> 401
        # -------------------------------------------------------------
        print("\n--- 7. Attempting to use invalid token ---")
        invalid_response = client.post(
            "/auth/refresh",
            json={"refresh_token": "not.a.valid.jwt.token"},
        )
        assert invalid_response.status_code == 401, f"Expected 401 for invalid token, got {invalid_response.status_code}"
        print("Invalid token properly rejected with 401 Unauthorized.")

        # -------------------------------------------------------------
        # 8. Try an expired refresh token -> 401
        # -------------------------------------------------------------
        print("\n--- 8. Attempting to use expired refresh token ---")
        expired_token = create_refresh_token(subject=user_id, expires_delta=timedelta(seconds=-10))
        # Insert expired token in DB
        expired_db_record = RefreshToken(
            user_id=uuid.UUID(user_id),
            token=expired_token,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            is_revoked=False,
        )
        repo.add(db=db, obj=expired_db_record)
        db.commit()

        expired_response = client.post(
            "/auth/refresh",
            json={"refresh_token": expired_token},
        )
        assert expired_response.status_code == 401, f"Expected 401 for expired token, got {expired_response.status_code}"
        print("Expired token properly rejected with 401 Unauthorized.")

        # -------------------------------------------------------------
        # 9. Verify new access token works on protected endpoint /auth/me
        # -------------------------------------------------------------
        print("\n--- 9. Verifying new access token with /auth/me ---")
        me_response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {new_access_token}"},
        )
        assert me_response.status_code == 200, f"/auth/me failed with new access token: {me_response.text}"
        assert me_response.json()["email"] == email
        print("/auth/me authenticated successfully with newly refreshed access token.")

        # -------------------------------------------------------------
        # 10. Subsequent refresh with the new active refresh token
        # -------------------------------------------------------------
        print("\n--- 10. Refreshing again with the active rotated token ---")
        second_refresh_response = client.post(
            "/auth/refresh",
            json={"refresh_token": new_refresh_token},
        )
        assert second_refresh_response.status_code == 200, f"Second refresh failed: {second_refresh_response.text}"
        second_refresh_data = second_refresh_response.json()
        print("Second refresh succeeded successfully.")

        # Verify old token now revoked
        db.expire_all()
        # -------------------------------------------------------------
        # 11. Test inactive user rejection -> 401
        # -------------------------------------------------------------
        print("\n--- 11. Testing inactive user rejection ---")
        user_repo = UserRepository()
        user_obj = user_repo.get_by_id(db=db, obj_id=uuid.UUID(user_id))
        assert user_obj is not None
        user_obj.is_active = False
        db.commit()

        inactive_user_response = client.post(
            "/auth/refresh",
            json={"refresh_token": second_refresh_data["refresh_token"]},
        )
        assert inactive_user_response.status_code == 401, f"Expected 401 for inactive user, got {inactive_user_response.status_code}"
        print("Inactive user properly rejected with 401 Unauthorized.")

        # Restore user status
        user_obj.is_active = True
        db.commit()

        # -------------------------------------------------------------
        # 12. Test valid JWT that does not exist in DB -> 401
        # -------------------------------------------------------------
        print("\n--- 12. Testing valid JWT not present in database ---")
        unregistered_token = create_refresh_token(subject=user_id)
        not_in_db_response = client.post(
            "/auth/refresh",
            json={"refresh_token": unregistered_token},
        )
        assert not_in_db_response.status_code == 401, f"Expected 401 for DB-missing token, got {not_in_db_response.status_code}"
        print("Non-persisted token properly rejected with 401 Unauthorized.")

        print("\n ALL AUTH REFRESH AND ROTATION TESTS PASSED SUCCESSFULLY!")

    finally:
        db.close()


if __name__ == "__main__":
    test_full_refresh_token_flow()
