import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token, create_refresh_token
from app.auth.model import RefreshToken, User
from app.auth.repositories.refresh_token_repository import RefreshTokenRepository
from app.database.database import SessionLocal
from app.main import app

client = TestClient(app)


def test_complete_auth_logout_milestone():
    db: Session = SessionLocal()
    try:
        suffix_a = uuid.uuid4().hex[:8]
        email_a = f"user_a_{suffix_a}@example.com"
        password_a = "SecurePass123!"

        # Register User A
        reg_a = client.post(
            "/auth/register",
            json={
                "company_name": f"Corp {suffix_a}",
                "company_slug": f"corp-{suffix_a}",
                "full_name": "User Alpha",
                "email": email_a,
                "password": password_a,
            },
        )
        assert reg_a.status_code == 201
        user_a_id = reg_a.json()["user"]["id"]

        # =============================================================
        # TEST 1 — LOGIN
        # =============================================================
        print("\n--- TEST 1 — LOGIN ---")
        login_res = client.post(
            "/auth/login",
            data={"username": email_a, "password": password_a},
        )
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        login_data = login_res.json()
        assert "access_token" in login_data
        assert "refresh_token" in login_data

        access_token_1 = login_data["access_token"]
        refresh_token_1 = login_data["refresh_token"]
        print("Login succeeded, received access_token and refresh_token.")

        # =============================================================
        # TEST 2 — LOGOUT
        # =============================================================
        print("\n--- TEST 2 — LOGOUT ---")
        logout_res = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {access_token_1}"},
            json={"refresh_token": refresh_token_1},
        )
        assert logout_res.status_code == 200, f"Logout failed: {logout_res.text}"
        assert logout_res.json() == {"message": "Logout successful"}
        print("Logout returned 200 OK with {'message': 'Logout successful'}.")

        # =============================================================
        # TEST 3 — DATABASE VERIFICATION
        # =============================================================
        print("\n--- TEST 3 — DATABASE VERIFICATION ---")
        db.expire_all()
        repo = RefreshTokenRepository()
        token_1_record = repo.get_by_token(db=db, token=refresh_token_1)
        assert token_1_record is not None, "Refresh token record must still exist in DB (not deleted)"
        assert token_1_record.is_revoked is True, "Refresh token must have is_revoked = True"
        print("PostgreSQL record verified: is_revoked is TRUE and record was NOT deleted.")

        # =============================================================
        # TEST 4 — REUSE OLD REFRESH TOKEN
        # =============================================================
        print("\n--- TEST 4 — REUSE OLD REFRESH TOKEN ---")
        refresh_attempt = client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token_1},
        )
        assert refresh_attempt.status_code == 401, f"Expected 401 on revoked token, got {refresh_attempt.status_code}"
        print("Revoked refresh token correctly rejected with 401 Unauthorized on /auth/refresh.")

        # =============================================================
        # TEST 5 — NORMAL REFRESH AFTER NEW LOGIN
        # =============================================================
        print("\n--- TEST 5 — NORMAL REFRESH AFTER NEW LOGIN ---")
        login_res_2 = client.post(
            "/auth/login",
            data={"username": email_a, "password": password_a},
        )
        assert login_res_2.status_code == 200
        access_token_2 = login_res_2.json()["access_token"]
        refresh_token_2 = login_res_2.json()["refresh_token"]

        refresh_res_2 = client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token_2},
        )
        assert refresh_res_2.status_code == 200, f"Refresh failed: {refresh_res_2.text}"
        refresh_data_2 = refresh_res_2.json()
        access_token_3 = refresh_data_2["access_token"]
        refresh_token_3 = refresh_data_2["refresh_token"]
        print("New login and normal token refresh worked successfully.")

        # =============================================================
        # TEST 6 — LOGOUT NEW TOKEN
        # =============================================================
        print("\n--- TEST 6 — LOGOUT NEW TOKEN ---")
        logout_res_2 = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {access_token_3}"},
            json={"refresh_token": refresh_token_3},
        )
        assert logout_res_2.status_code == 200
        assert logout_res_2.json() == {"message": "Logout successful"}

        db.expire_all()
        token_3_record = repo.get_by_token(db=db, token=refresh_token_3)
        assert token_3_record is not None
        assert token_3_record.is_revoked is True
        print("Rotated token logged out and marked is_revoked = True in PostgreSQL.")

        # =============================================================
        # TEST 7 — ACCESS TOKEN VALIDITY
        # =============================================================
        print("\n--- TEST 7 — ACCESS TOKEN VALIDITY ---")
        me_res = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {access_token_3}"},
        )
        assert me_res.status_code == 200, f"Access token should remain valid until expiry: {me_res.text}"
        assert me_res.json()["email"] == email_a
        print("Access token remains valid for /auth/me until natural JWT expiration.")

        # =============================================================
        # TEST 8 — CROSS-USER LOGOUT ATTEMPT PREVENTED
        # =============================================================
        print("\n--- TEST 8 — CROSS-USER LOGOUT ATTEMPT PREVENTED ---")
        suffix_b = uuid.uuid4().hex[:8]
        email_b = f"user_b_{suffix_b}@example.com"
        password_b = "SecurePass123!"

        reg_b = client.post(
            "/auth/register",
            json={
                "company_name": f"Corp {suffix_b}",
                "company_slug": f"corp-{suffix_b}",
                "full_name": "User Beta",
                "email": email_b,
                "password": password_b,
            },
        )
        assert reg_b.status_code == 201
        refresh_token_b = reg_b.json()["token"]["refresh_token"]

        # User A tries to revoke User B's refresh token
        cross_logout_res = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {access_token_3}"},
            json={"refresh_token": refresh_token_b},
        )
        assert cross_logout_res.status_code == 401, f"Expected 401 for cross-user revocation, got {cross_logout_res.status_code}"

        # Verify User B's token is STILL active (not revoked)
        db.expire_all()
        token_b_record = repo.get_by_token(db=db, token=refresh_token_b)
        assert token_b_record.is_revoked is False, "User B's token must not have been revoked by User A"
        print("Cross-user token revocation prevented. User B's token remains active.")

        # =============================================================
        # TEST 9 — LOGOUT WITH INVALID / REVOKED / MISMATCHED TOKENS
        # =============================================================
        print("\n--- TEST 9 — EDGE CASE SECURITY REJECTIONS ---")
        # 1. Unauthenticated request
        unauth_res = client.post("/auth/logout", json={"refresh_token": refresh_token_b})
        assert unauth_res.status_code == 401

        # 2. Access token passed in body as refresh_token
        access_as_refresh = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {access_token_3}"},
            json={"refresh_token": access_token_3},
        )
        assert access_as_refresh.status_code == 401

        # 3. Already revoked token
        already_revoked = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {access_token_3}"},
            json={"refresh_token": refresh_token_3},
        )
        assert already_revoked.status_code == 401

        # 4. Malformed token
        malformed = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {access_token_3}"},
            json={"refresh_token": "malformed.jwt.token"},
        )
        assert malformed.status_code == 401

        print("All security rejections verified with 401 Unauthorized.")
        print("\n ALL LOGOUT TESTS PASSED SUCCESSFULLY!")

    finally:
        db.close()


if __name__ == "__main__":
    test_complete_auth_logout_milestone()
