import uuid
from app.core.config import settings
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.embeddings.base import BaseEmbeddingProvider
from app.embeddings.factory import get_embedding_provider
from app.embeddings.mock_provider import MockEmbeddingProvider
from app.knowledge.model import DocumentChunk
from app.main import app

client = TestClient(app)


def test_embedding_provider_logic():
    # 1. Factory returns MockEmbeddingProvider by default
    provider = get_embedding_provider()
    assert isinstance(provider, MockEmbeddingProvider)
    assert isinstance(provider, BaseEmbeddingProvider)

    # 2. Same text produces same vector (deterministic)
    v1 = provider.embed_text("How to configure CortexCX workspace?")
    v2 = provider.embed_text("How to configure CortexCX workspace?")
    assert v1 == v2
    assert len(v1) == settings.EMBEDDING_DIMENSION

    # 3. Different text produces different vector
    v3 = provider.embed_text("How to process a refund for a customer?")
    assert v1 != v3

    # Batch embedding
    batch = provider.embed_texts(["Text A", "Text B"])
    assert len(batch) == 2
    assert batch[0] == provider.embed_text("Text A")
    assert batch[1] == provider.embed_text("Text B")


def test_milestone_12_embedding_and_vector_retrieval():
    db: Session = SessionLocal()
    try:
        suffix_a = uuid.uuid4().hex[:8]
        suffix_b = uuid.uuid4().hex[:8]
        password = "SecurePassword123!"

        # -------------------------------------------------------------
        # SETUP WORKSPACE A: Owner A, Admin A, Agent A
        # -------------------------------------------------------------
        reg_owner_a = client.post(
            "/auth/register",
            json={
                "company_name": f"Vector Corp Alpha {suffix_a}",
                "company_slug": f"vec-alpha-{suffix_a}",
                "full_name": "Owner Alpha Vec",
                "email": f"owner_vec_a_{suffix_a}@example.com",
                "password": password,
            },
        )
        assert reg_owner_a.status_code == 201
        owner_a_data = reg_owner_a.json()
        owner_a_token = owner_a_data["token"]["access_token"]
        owner_a_refresh_token = owner_a_data["token"]["refresh_token"]
        workspace_a_id = owner_a_data["workspace"]["id"]

        # Admin A
        add_admin_a = client.post(
            "/workspaces/users",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Admin Alpha Vec",
                "email": f"admin_vec_a_{suffix_a}@example.com",
                "password": password,
                "role": "admin",
            },
        )
        assert add_admin_a.status_code == 201
        admin_a_id = add_admin_a.json()["id"]

        login_admin_a = client.post(
            "/auth/login",
            data={"username": f"admin_vec_a_{suffix_a}@example.com", "password": password},
        )
        assert login_admin_a.status_code == 200
        admin_a_token = login_admin_a.json()["access_token"]

        # Agent A
        add_agent_a = client.post(
            "/workspaces/users",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Agent Alpha Vec",
                "email": f"agent_vec_a_{suffix_a}@example.com",
                "password": password,
                "role": "agent",
            },
        )
        assert add_agent_a.status_code == 201
        agent_a_id = add_agent_a.json()["id"]

        login_agent_a = client.post(
            "/auth/login",
            data={"username": f"agent_vec_a_{suffix_a}@example.com", "password": password},
        )
        assert login_agent_a.status_code == 200
        agent_a_token = login_agent_a.json()["access_token"]

        # -------------------------------------------------------------
        # SETUP WORKSPACE B: Owner B
        # -------------------------------------------------------------
        reg_owner_b = client.post(
            "/auth/register",
            json={
                "company_name": f"Vector Corp Beta {suffix_b}",
                "company_slug": f"vec-beta-{suffix_b}",
                "full_name": "Owner Beta Vec",
                "email": f"owner_vec_b_{suffix_b}@example.com",
                "password": password,
            },
        )
        assert reg_owner_b.status_code == 201
        owner_b_data = reg_owner_b.json()
        owner_b_token = owner_b_data["token"]["access_token"]
        workspace_b_id = owner_b_data["workspace"]["id"]

        # Create Knowledge Sources in Workspace A
        res_src1 = client.post(
            "/knowledge/sources",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"name": "Billing Policies", "source_type": "txt"},
        )
        assert res_src1.status_code == 201
        src1_id = res_src1.json()["id"]

        res_src2 = client.post(
            "/knowledge/sources",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"name": "API Documentation", "source_type": "txt"},
        )
        assert res_src2.status_code == 201
        src2_id = res_src2.json()["id"]

        # Create Documents in Workspace A
        res_doc1 = client.post(
            "/knowledge/documents",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "knowledge_source_id": src1_id,
                "title": "Refund and Billing Guide",
                "content": (
                    "To process a refund for a customer, navigate to the Billing tab. "
                    "Select the invoice and click Issue Refund. Refunds take 3 to 5 business days."
                ),
            },
        )
        assert res_doc1.status_code == 201
        doc1_id = res_doc1.json()["id"]

        res_doc2 = client.post(
            "/knowledge/documents",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "knowledge_source_id": src2_id,
                "title": "API Authentication Guide",
                "content": (
                    "To authenticate API requests, include your JWT access token in the Authorization header. "
                    "Tokens expire after 7 days and can be refreshed using the refresh endpoint."
                ),
            },
        )
        assert res_doc2.status_code == 201
        doc2_id = res_doc2.json()["id"]

        # Create Document in Workspace B (Confidential)
        res_src_b = client.post(
            "/knowledge/sources",
            headers={"Authorization": f"Bearer {owner_b_token}"},
            json={"name": "Workspace B Secrets", "source_type": "txt"},
        )
        assert res_src_b.status_code == 201
        src_b_id = res_src_b.json()["id"]

        res_doc_b = client.post(
            "/knowledge/documents",
            headers={"Authorization": f"Bearer {owner_b_token}"},
            json={
                "knowledge_source_id": src_b_id,
                "title": "Top Secret Beta Operations",
                "content": "Confidential internal secrets for Workspace Beta only.",
            },
        )
        assert res_doc_b.status_code == 201
        doc_b_id = res_doc_b.json()["id"]

        # =============================================================
        # 5. Embed Document by Owner
        # 6. Embeddings persisted in PostgreSQL
        # =============================================================
        embed_doc1 = client.post(
            f"/knowledge/documents/{doc1_id}/embed",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert embed_doc1.status_code == 200
        assert embed_doc1.json()["id"] == doc1_id

        # Verify in DB that chunks have embeddings
        chunks_doc1 = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == doc1_id)
            .all()
        )
        assert len(chunks_doc1) > 0
        for chunk in chunks_doc1:
            assert chunk.embedding is not None
            assert len(chunk.embedding) == settings.EMBEDDING_DIMENSION

        # Embed Document 2 by Admin
        embed_doc2 = client.post(
            f"/knowledge/documents/{doc2_id}/embed",
            headers={"Authorization": f"Bearer {admin_a_token}"},
        )
        assert embed_doc2.status_code == 200

        # Embed Document B by Owner B
        embed_doc_b = client.post(
            f"/knowledge/documents/{doc_b_id}/embed",
            headers={"Authorization": f"Bearer {owner_b_token}"},
        )
        assert embed_doc_b.status_code == 200

        # =============================================================
        # 13. AGENT cannot embed documents (403)
        # =============================================================
        agent_embed = client.post(
            f"/knowledge/documents/{doc1_id}/embed",
            headers={"Authorization": f"Bearer {agent_a_token}"},
        )
        assert agent_embed.status_code == 403

        # =============================================================
        # 12. Cross-workspace document embedding returns 404
        # =============================================================
        cross_embed = client.post(
            f"/knowledge/documents/{doc_b_id}/embed",
            headers={"Authorization": f"Bearer {owner_a_token}"},
        )
        assert cross_embed.status_code == 404

        # =============================================================
        # 7, 8, 9, 14. Semantic Search (Accessible by Owner, Admin, Agent)
        # =============================================================
        search_res = client.post(
            "/knowledge/search",
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={
                "query": "process a refund for a customer",
                "top_k": 5,
            },
        )
        assert search_res.status_code == 200
        search_data = search_res.json()
        assert search_data["query"] == "process a refund for a customer"
        assert search_data["total"] > 0
        results = search_data["results"]
        # Top result should be the refund chunk
        assert "refund" in results[0]["content"].lower()
        # Verify scores are in descending order
        scores = [r["similarity_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

        # =============================================================
        # 10 & 11. Strict Tenant Isolation (Cross-workspace knowledge inaccessible)
        # =============================================================
        search_secret = client.post(
            "/knowledge/search",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "query": "Confidential internal secrets for Workspace Beta only",
                "top_k": 5,
            },
        )
        assert search_secret.status_code == 200
        secret_results = search_secret.json()["results"]
        for r in secret_results:
            assert "Workspace Beta" not in r["content"]
            assert r["document_id"] != doc_b_id

        # =============================================================
        # 18. Knowledge Source Filter in Search
        # =============================================================
        search_filtered = client.post(
            "/knowledge/search",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "query": "authenticate API requests",
                "top_k": 5,
                "knowledge_source_id": src2_id,
            },
        )
        assert search_filtered.status_code == 200
        for r in search_filtered.json()["results"]:
            assert r["knowledge_source_id"] == src2_id

        # =============================================================
        # 15. Unauthenticated requests return 401
        # =============================================================
        assert client.post("/knowledge/search", json={"query": "hello"}).status_code == 401
        assert client.post(f"/knowledge/documents/{doc1_id}/embed").status_code == 401

        # =============================================================
        # 16. Refresh token as access token returns 401
        # =============================================================
        ref_as_acc = client.post(
            "/knowledge/search",
            headers={"Authorization": f"Bearer {owner_a_refresh_token}"},
            json={"query": "test"},
        )
        assert ref_as_acc.status_code == 401

        # =============================================================
        # 17. Inactive user rejected
        # =============================================================
        client.patch(
            f"/workspaces/users/{admin_a_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"is_active": False},
        )
        inactive_search = client.post(
            "/knowledge/search",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={"query": "test"},
        )
        assert inactive_search.status_code in [400, 401, 403]

        client.patch(
            f"/workspaces/users/{admin_a_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"is_active": True},
        )

    finally:
        db.close()
