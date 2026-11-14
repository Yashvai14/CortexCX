import io
import uuid
import pypdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.knowledge.chunking import chunk_text
from app.knowledge.parsers.docx_parser import DOCXParser
from app.knowledge.parsers.factory import get_parser_for_type
from app.knowledge.parsers.pdf_parser import PDFParser
from app.knowledge.parsers.txt_parser import TXTParser
from app.main import app

client = TestClient(app)


def test_chunking_service_logic():
    # 1. Deterministic slicing
    text = "A" * 1200
    chunks = chunk_text(text, chunk_size=500, chunk_overlap=50)
    assert len(chunks) == 3
    assert len(chunks[0]) == 500
    assert len(chunks[1]) == 500
    assert len(chunks[2]) == 300

    # 2. Empty text rejection
    with pytest.raises(ValueError, match="Document content cannot be empty"):
        chunk_text("   \n\t  ")

    # 3. Invalid parameters rejection
    with pytest.raises(ValueError, match="Chunk size must be greater than 0"):
        chunk_text("Hello", chunk_size=0)

    with pytest.raises(ValueError, match="Chunk overlap must be non-negative"):
        chunk_text("Hello", chunk_size=100, chunk_overlap=150)


def test_document_parsers():
    # TXT parser
    txt_parser = get_parser_for_type("txt")
    assert isinstance(txt_parser, TXTParser)
    parsed_txt = txt_parser.parse(b"Hello CortexCX Knowledge Base!")
    assert parsed_txt == "Hello CortexCX Knowledge Base!"

    with pytest.raises(ValueError, match="Document file is empty"):
        txt_parser.parse(b"   ")

    # PDF parser corrupted binary
    pdf_parser = get_parser_for_type("pdf")
    assert isinstance(pdf_parser, PDFParser)
    with pytest.raises(ValueError, match="Failed to parse malformed PDF document"):
        pdf_parser.parse(b"NOT_A_REAL_PDF_BYTES")

    # DOCX parser corrupted binary
    docx_parser = get_parser_for_type("docx")
    assert isinstance(docx_parser, DOCXParser)
    with pytest.raises(ValueError, match="Failed to parse malformed DOCX document"):
        docx_parser.parse(b"NOT_A_REAL_DOCX_BYTES")


def test_milestone_11_knowledge_base_endpoints():
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
                "company_name": f"KB Alpha {suffix_a}",
                "company_slug": f"kb-alpha-{suffix_a}",
                "full_name": "Owner Alpha KB",
                "email": f"owner_kb_a_{suffix_a}@example.com",
                "password": password,
            },
        )
        assert reg_owner_a.status_code == 201
        owner_a_data = reg_owner_a.json()
        owner_a_token = owner_a_data["token"]["access_token"]
        owner_a_refresh_token = owner_a_data["token"]["refresh_token"]
        owner_a_id = owner_a_data["user"]["id"]
        workspace_a_id = owner_a_data["workspace"]["id"]

        # Admin A
        add_admin_a = client.post(
            "/workspaces/users",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Admin Alpha KB",
                "email": f"admin_kb_a_{suffix_a}@example.com",
                "password": password,
                "role": "admin",
            },
        )
        assert add_admin_a.status_code == 201
        admin_a_id = add_admin_a.json()["id"]

        login_admin_a = client.post(
            "/auth/login",
            data={"username": f"admin_kb_a_{suffix_a}@example.com", "password": password},
        )
        assert login_admin_a.status_code == 200
        admin_a_token = login_admin_a.json()["access_token"]

        # Agent A
        add_agent_a = client.post(
            "/workspaces/users",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "full_name": "Agent Alpha KB",
                "email": f"agent_kb_a_{suffix_a}@example.com",
                "password": password,
                "role": "agent",
            },
        )
        assert add_agent_a.status_code == 201
        agent_a_id = add_agent_a.json()["id"]

        login_agent_a = client.post(
            "/auth/login",
            data={"username": f"agent_kb_a_{suffix_a}@example.com", "password": password},
        )
        assert login_agent_a.status_code == 200
        agent_a_token = login_agent_a.json()["access_token"]

        # -------------------------------------------------------------
        # SETUP WORKSPACE B: Owner B
        # -------------------------------------------------------------
        reg_owner_b = client.post(
            "/auth/register",
            json={
                "company_name": f"KB Beta {suffix_b}",
                "company_slug": f"kb-beta-{suffix_b}",
                "full_name": "Owner Beta KB",
                "email": f"owner_kb_b_{suffix_b}@example.com",
                "password": password,
            },
        )
        assert reg_owner_b.status_code == 201
        owner_b_data = reg_owner_b.json()
        owner_b_token = owner_b_data["token"]["access_token"]
        workspace_b_id = owner_b_data["workspace"]["id"]

        # =============================================================
        # 1. OWNER can create knowledge source
        # =============================================================
        res_src_owner = client.post(
            "/knowledge/sources",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "name": "Product Documentation",
                "source_type": "txt",
                "source_url": "https://docs.example.com",
            },
        )
        assert res_src_owner.status_code == 201
        src_owner_data = res_src_owner.json()
        src_a_id = src_owner_data["id"]
        assert src_owner_data["workspace_id"] == workspace_a_id
        assert src_owner_data["name"] == "Product Documentation"

        # =============================================================
        # 2. ADMIN can create knowledge source
        # =============================================================
        res_src_admin = client.post(
            "/knowledge/sources",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={
                "name": "API References",
                "source_type": "pdf",
            },
        )
        assert res_src_admin.status_code == 201
        src_admin_id = res_src_admin.json()["id"]

        # =============================================================
        # 3. AGENT cannot create knowledge source (403)
        # =============================================================
        res_src_agent = client.post(
            "/knowledge/sources",
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={
                "name": "Secret Notes",
                "source_type": "txt",
            },
        )
        assert res_src_agent.status_code == 403

        # =============================================================
        # 4 & 5. Authenticated user can list and get workspace sources
        # =============================================================
        list_srcs = client.get(
            "/knowledge/sources",
            headers={"Authorization": f"Bearer {agent_a_token}"},
        )
        assert list_srcs.status_code == 200
        src_ids = [s["id"] for s in list_srcs.json()]
        assert src_a_id in src_ids
        assert src_admin_id in src_ids

        get_src = client.get(
            f"/knowledge/sources/{src_a_id}",
            headers={"Authorization": f"Bearer {agent_a_token}"},
        )
        assert get_src.status_code == 200
        assert get_src.json()["id"] == src_a_id

        # =============================================================
        # 6. Cross-workspace source access returns 404
        # =============================================================
        cross_get_src = client.get(
            f"/knowledge/sources/{src_a_id}",
            headers={"Authorization": f"Bearer {owner_b_token}"},
        )
        assert cross_get_src.status_code == 404

        # =============================================================
        # 7. OWNER can create document (with chunking)
        # =============================================================
        long_content = "CortexCX provides automated customer support. " * 120  # ~5500 chars: larger than one chunk (2800 max)
        res_doc_owner = client.post(
            "/knowledge/documents",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "knowledge_source_id": src_a_id,
                "title": "Getting Started Guide",
                "filename": "guide.txt",
                "content": long_content,
                "metadata_json": {"author": "Support Lead", "version": "1.0"},
            },
        )
        assert res_doc_owner.status_code == 201, f"Failed: {res_doc_owner.text}"
        doc_data = res_doc_owner.json()
        doc_a_id = doc_data["id"]
        assert doc_data["workspace_id"] == workspace_a_id
        assert doc_data["knowledge_source_id"] == src_a_id
        assert doc_data["title"] == "Getting Started Guide"
        assert doc_data["chunk_count"] > 1

        # =============================================================
        # 8. ADMIN can create document
        # =============================================================
        res_doc_admin = client.post(
            "/knowledge/documents",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={
                "knowledge_source_id": src_admin_id,
                "title": "API Authentication",
                "content": "Bearer tokens must be passed in the Authorization header.",
            },
        )
        assert res_doc_admin.status_code == 201

        # =============================================================
        # 9. AGENT cannot create document (403)
        # =============================================================
        res_doc_agent = client.post(
            "/knowledge/documents",
            headers={"Authorization": f"Bearer {agent_a_token}"},
            json={
                "knowledge_source_id": src_a_id,
                "title": "Unauthorized Doc",
                "content": "Not allowed.",
            },
        )
        assert res_doc_agent.status_code == 403

        # =============================================================
        # 10, 11, 12. Document chunks ordered & deterministic
        # =============================================================
        chunks_res = client.get(
            f"/knowledge/documents/{doc_a_id}/chunks",
            headers={"Authorization": f"Bearer {agent_a_token}"},
        )
        assert chunks_res.status_code == 200
        chunks = chunks_res.json()
        assert len(chunks) == doc_data["chunk_count"]
        for idx, chunk in enumerate(chunks):
            assert chunk["chunk_index"] == idx
            assert chunk["document_id"] == doc_a_id
            assert chunk["workspace_id"] == workspace_a_id
            assert len(chunk["content"]) > 0

        # =============================================================
        # 13. Empty document is rejected (400)
        # =============================================================
        empty_doc_res = client.post(
            "/knowledge/documents",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={
                "knowledge_source_id": src_a_id,
                "title": "Empty Document",
                "content": "     \n\t   ",
            },
        )
        assert empty_doc_res.status_code == 400
        assert "empty" in empty_doc_res.text.lower()

        # =============================================================
        # 16. Cross-workspace document access returns 404
        # =============================================================
        cross_get_doc = client.get(
            f"/knowledge/documents/{doc_a_id}",
            headers={"Authorization": f"Bearer {owner_b_token}"},
        )
        assert cross_get_doc.status_code == 404

        cross_get_chunks = client.get(
            f"/knowledge/documents/{doc_a_id}/chunks",
            headers={"Authorization": f"Bearer {owner_b_token}"},
        )
        assert cross_get_chunks.status_code == 404

        # Owner B cannot add document to Workspace A's knowledge source
        cross_add_doc = client.post(
            "/knowledge/documents",
            headers={"Authorization": f"Bearer {owner_b_token}"},
            json={
                "knowledge_source_id": src_a_id,
                "title": "Cross Workspace Attack",
                "content": "Malicious content.",
            },
        )
        assert cross_add_doc.status_code == 404

        # =============================================================
        # 17. Unauthenticated requests return 401
        # =============================================================
        assert client.get("/knowledge/sources").status_code == 401
        assert client.get(f"/knowledge/documents/{doc_a_id}").status_code == 401

        # =============================================================
        # 18. Refresh token as access token returns 401
        # =============================================================
        ref_res = client.get(
            "/knowledge/sources",
            headers={"Authorization": f"Bearer {owner_a_refresh_token}"},
        )
        assert ref_res.status_code == 401

        # =============================================================
        # 19. Inactive user rejected
        # =============================================================
        # Deactivate Admin A
        client.patch(
            f"/workspaces/users/{admin_a_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"is_active": False},
        )

        inactive_create = client.post(
            "/knowledge/sources",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={"name": "Inactive Source", "source_type": "txt"},
        )
        assert inactive_create.status_code in [400, 401, 403]

        # Re-activate Admin A
        client.patch(
            f"/workspaces/users/{admin_a_id}",
            headers={"Authorization": f"Bearer {owner_a_token}"},
            json={"is_active": True},
        )

    finally:
        db.close()
