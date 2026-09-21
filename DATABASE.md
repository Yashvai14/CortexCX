# CortexCX — Database Schema & Data Models

PostgreSQL 14+ schema managed via Alembic migrations. All entities inherit `id: UUID`, `created_at: DateTime`, `updated_at: DateTime`, and enforce tenant isolation via `workspace_id: UUID`.

---

## 1. Core Tenant & Identity Models
- `workspaces`: Tenant organization boundary (`name`, `slug`).
- `users`: Operator accounts (`workspace_id`, `email`, `hashed_password`, `role`: `owner` | `admin` | `agent`).
- `refresh_tokens`: Refresh tokens for JWT session rotation.

## 2. Customer & Omnichannel Identity
- `customers`: Customer 360 profile (`workspace_id`, `full_name`, `email`, `phone`, `company_name`, `status`).
- `channel_identities`: Maps external messaging IDs (Telegram `chat_id`, WebChat `session_id`) to internal customer records.

## 3. Conversations & Messages
- `conversations`: Customer interaction threads (`workspace_id`, `customer_id`, `subject`, `status`: `open` | `pending` | `resolved` | `closed`, `ai_enabled`, `ai_state`: `idle` | `processing` | `responded` | `escalated` | `failed`).
- `messages`: Thread messages (`conversation_id`, `sender_type`: `customer` | `agent` | `ai` | `system`, `sender_user_id`, `content`).

## 4. D2C Commerce & Catalog
- `products`: Product items (`workspace_id`, `sku`, `name`, `description`, `price`, `currency`, `category`, `is_active`).
- `inventory`: Real-time stock levels (`workspace_id`, `product_id`, `quantity_available`, `quantity_reserved`, `low_stock_threshold`).
- `orders`: Customer orders (`workspace_id`, `customer_id`, `order_number`, `status`: `pending` | `processing` | `shipped` | `delivered` | `cancelled` | `refunded`, `total_amount`, `carrier`, `tracking_number`, `estimated_delivery`).
- `order_items`: Order line items (`order_id`, `product_id`, `quantity`, `unit_price`, `total_price`).
- `coupons`: Discount promotions (`workspace_id`, `code`, `discount_type`, `discount_value`, `min_order_amount`, `max_uses`, `is_active`).
- `policies`: Store policies (`workspace_id`, `policy_type`, `title`, `content`, `is_active`).

## 5. Knowledge Base & Hybrid RAG
- `knowledge_sources`: Source containers (`workspace_id`, `name`, `source_type`: `txt` | `pdf` | `docx` | `website`, `source_url`, `status`).
- `documents`: Parsed documents (`knowledge_source_id`, `title`, `filename`, `content`, `metadata_json`, `status`).
- `document_chunks`: Semantic chunks (`document_id`, `chunk_index`, `content`, `embedding`: `ARRAY(Float)`, `metadata_json`).

## 6. AI Cognition, Memory & Governance
- `customer_memories`: Episodic facts extracted from conversations (`workspace_id`, `customer_id`, `memory_type`, `content`, `confidence`, `source_conversation_id`, `is_active`).
- `human_escalations`: Low-confidence ticket handoffs (`workspace_id`, `conversation_id`, `customer_id`, `status`: `pending` | `in_progress` | `resolved` | `returned_to_ai`, `reason`, `confidence_score`, `summary`, `suggested_reply`, `assigned_agent_id`).
- `agent_feedbacks`: Agent corrections to AI responses (`workspace_id`, `conversation_id`, `message_id`, `agent_id`, `original_response`, `corrected_response`, `reason`, `is_verified`).
- `ai_run_traces`: Tracing & explainability (`workspace_id`, `conversation_id`, `message_id`, `intent`, `intent_confidence`, `decision`, `confidence_score`, `tools_executed`, `retrieved_sources`, `model_name`, `duration_ms`).
