# CortexCX — Complete REST API Reference

All APIs (except public auth, webchat widget, and telegram webhook) require an `Authorization: Bearer <token>` header with role-based access control (RBAC).

---

## 1. Authentication & Users
- `POST /auth/register`: Register new workspace and owner account.
- `POST /auth/login`: Authenticate with email/password; returns JWT access & refresh tokens.
- `POST /auth/refresh`: Rotate refresh token and issue new access token.
- `POST /auth/logout`: Revoke active refresh token session.
- `GET  /users/me`: Current user profile.

---

## 2. Omnichannel Customer Integrations (`/channels`)
- `POST /channels/webchat/message`: Public customer message receiver from storefront widget.
  - Body: `{"workspace_id": "...", "session_id": "...", "content": "...", "customer_name": "...", "customer_email": "..."}`
  - Returns: `ChannelResponse` (`conversation_id`, `content`, `ai_state`, `decision`, `confidence_score`, `sources`, `escalated`).
- `GET  /channels/webchat/history/{session_id}?workspace_id=...`: Retrieve message history for active visitor session.
- `POST /channels/telegram/webhook?workspace_id=...`: Webhook receiver for Telegram Bot API updates.

---

## 3. Human Handoff & Agent Assist (`/escalations`)
- `GET  /escalations`: List open escalations (`pending`, `in_progress`).
- `GET  /escalations/{id}`: Detailed Agent Assist view (customer memories, thread, summary, suggested reply).
- `POST /escalations/{id}/claim`: Assign escalation to current support agent.
- `POST /escalations/{id}/respond`: Agent sends direct message to customer and optionally resolves ticket.
- `POST /escalations/{id}/return-to-ai`: Returns conversation control to the AI engine.
- `POST /escalations/feedback`: Captures agent response corrections for learning dataset.

---

## 4. D2C Commerce & Operations (`/commerce`)
- `GET  /commerce/products`: Search and filter catalog with stock levels.
- `POST /commerce/products`: Create catalog item with initial inventory (Owner/Admin).
- `GET  /commerce/orders`: List workspace orders.
- `POST /commerce/orders`: Create order with tracking details (Owner/Admin).
- `GET  /commerce/orders/{order_number}`: Track order status, carrier, and ETA.
- `GET  /commerce/policies`: List store policies (refund, return, shipping).
- `POST /commerce/policies`: Upsert policy content (Owner/Admin).
- `GET  /commerce/coupons`: List active promotional coupon codes.
- `POST /commerce/coupons`: Create discount coupon (Owner/Admin).

---

## 5. Executive Analytics (`/analytics`)
- `GET /analytics/overview`: Real-time aggregated KPIs (AI resolution rate, total conversations, escalations, average confidence, latency, top intents, channel breakdown).

---

## 6. Knowledge Base & RAG (`/knowledge` & `/ai`)
- `POST /knowledge/sources`: Create knowledge source container (`txt`, `pdf`, `docx`, `website`).
- `POST /knowledge/sources/{id}/documents`: Upload and parse documents.
- `POST /knowledge/documents/{id}/embed`: Generate embeddings for document chunks.
- `POST /knowledge/search`: Vector semantic search across workspace chunks.
- `POST /ai/conversations/{id}/process`: Trigger conversational AI turn.
- `POST /ai/conversations/{id}/rag`: Execute grounded hybrid RAG generation.
- `PATCH /ai/conversations/{id}/toggle`: Enable or disable AI processing.
