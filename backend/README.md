# 🧠 CortexCX Backend

> **Next-Generation AI Customer Experience & Support Intelligence Platform**  
> Built with FastAPI, PostgreSQL, SQLAlchemy, Alembic, and pluggable AI/RAG orchestration.

---

## 📌 Overview

CortexCX is an enterprise-grade customer experience management backend that empowers support teams with multi-tenant workspaces, conversation handling, customer intelligence, knowledge base vector search, and Retrieval-Augmented Generation (RAG) AI copilot capabilities.

---

## 🚀 Key Features Implemented

### 1. 🏢 Multi-Tenant Workspace & Team Management
- **Strict Isolation**: All entities (users, customers, conversations, documents) are bound to a tenant `workspace_id`.
- **RBAC (Role-Based Access Control)**:
  - `owner`: Full workspace and billing authority, member invites, role updates.
  - `admin`: User/team management, knowledge base embedding, AI configuration.
  - `agent`: Customer service operations, messaging, customer updates, AI suggestions.
- **Team Management**: Workspace member invitations, role updates, and member removal.

### 2. 🔐 Authentication & Session Security
- **JWT Authentication**: Secure Bearer tokens with configurable expiration.
- **Refresh Token Rotation**: Persistent refresh tokens with revocation support and device session tracking.
- **Password Security**: Bcrypt-hashed password storage.

### 3. 👥 Customer 360 & CRM
- Full customer lifecycle tracking (contact info, tags, metadata, timestamps).
- Search, filter, and pagination across customer records.
- Associated conversation history tracking.

### 4. 💬 Conversation & Omnichannel Messaging
- **Conversation State Engine**: Statuses (`open`, `pending`, `resolved`, `closed`), priorities (`low`, `medium`, `high`, `urgent`).
- **Assignment System**: Assign conversations to individual agents or teams.
- **Message Threads**: Customer messages, agent replies, and AI-generated messages.
- **AI Conversation Metadata**: Sentiment analysis, intent tagging, and suggested next actions.

### 5. 📚 Knowledge Base & Ingest Pipeline
- **Knowledge Sources**: Organize documentation by source/category (`manual`, `faq`, `documentation`, `api`).
- **Multi-Format Document Parsing**:
  - Plain text & Markdown (`.txt`, `.md`)
  - PDF documents (`.pdf` via `pypdf`)
  - Word documents (`.docx` via `python-docx`)
- **Configurable Chunking**: Automated content chunking with overlapping windows for high-recall retrieval.

### 6. 🔍 Vector Embeddings & Semantic Search
- **Embedding Provider Abstraction**: Pluggable architecture supporting `MockEmbeddingProvider` (deterministic vector generation for fast local dev/testing) and `OpenAIEmbeddingProvider` (`text-embedding-3-small` / custom models).
- **In-Database Vector Similarity**: Cosine similarity calculations over chunk vector arrays with `top_k` ranking and source filtering.
- **Dedicated Search Endpoints**: Semantic query endpoint returning ranked chunks with similarity scores.

### 7. 🤖 RAG (Retrieval-Augmented Generation) & AI Copilot
- **Context Assembly**: Automatic extraction of conversation history, customer context, and semantic knowledge retrieval.
- **Prompt Engineering**: System instructions that keep responses grounded, concise, and professional.
- **Provider Independence**: Modular LLM provider architecture (`mock`, `openai` GPT-4o-mini).
- **RAG Execution Endpoint**: `/ai/conversations/{id}/rag` generating context-grounded agent drafts or automated customer replies.

---

## 🏗️ Architecture & Project Structure

```text
backend/
├── alembic/                      # Database migrations
│   ├── env.py
│   └── versions/                 # Migration version history
├── app/
│   ├── ai/                       # LLM orchestration & AI endpoints
│   │   ├── providers/            # Base, Mock, and OpenAI LLM providers
│   │   ├── commands/             # AI generation & analysis commands
│   │   ├── router.py             # /ai routes
│   │   └── schema.py
│   ├── auth/                     # Authentication & User Management
│   │   ├── commands/             # Register, Login, Refresh, Logout, User CRUD
│   │   ├── dependencies.py       # Auth guards (get_current_user)
│   │   ├── permissions.py        # RBAC role guards (require_roles)
│   │   ├── model.py              # User & RefreshToken models
│   │   ├── router.py             # /auth routes
│   │   ├── user_router.py        # /users routes
│   │   └── security.py           # Password hash & JWT tokens
│   ├── conversation/             # Conversations & Messages
│   │   ├── commands/             # Create, Assign, Update Status, Add Message
│   │   ├── model.py              # Conversation & Message models
│   │   ├── router.py             # /conversations routes
│   │   └── schema.py
│   ├── core/                     # Application configuration & settings
│   │   ├── config.py             # Pydantic BaseSettings
│   │   └── security.py
│   ├── customer/                 # Customer directory & CRM
│   │   ├── commands/             # Create, Update, List, Get Customer
│   │   ├── model.py              # Customer model
│   │   ├── router.py             # /customers routes
│   │   └── schema.py
│   ├── database/                 # SQLAlchemy Engine & Session
│   │   ├── base.py               # BaseModel & Common Mixins
│   │   ├── database.py           # SessionLocal & Engine
│   │   ├── models.py             # Central model registry
│   │   └── session.py            # FastAPI db dependency
│   ├── embeddings/               # Vector Embedding Engine
│   │   ├── base.py               # BaseEmbeddingProvider interface
│   │   ├── factory.py            # Provider factory (Mock / OpenAI)
│   │   └── mock_provider.py      # Deterministic Mock Provider
│   ├── knowledge/                # Knowledge Base & Vector Search
│   │   ├── commands/             # Ingest, Chunk, Embed, Search commands
│   │   ├── model.py              # KnowledgeSource, Document, DocumentChunk
│   │   ├── parser.py             # File parsers (PDF, DOCX, TXT)
│   │   ├── router.py             # /knowledge routes
│   │   └── schema.py
│   ├── rag/                      # Retrieval-Augmented Generation Engine
│   │   ├── context.py            # Context Builder (History + Search)
│   │   ├── retrieval.py          # Semantic Knowledge Retriever
│   │   ├── schema.py             # RAG Request/Response schemas
│   │   └── service.py            # RAG Execution Service
│   ├── workspace/                # Multi-tenant Workspaces & Team
│   │   ├── commands/             # Workspace & Member management
│   │   ├── model.py              # Workspace model
│   │   ├── router.py             # /workspaces routes
│   │   └── schema.py
│   └── main.py                   # FastAPI Application entrypoint & CORS
├── tests/                        # Comprehensive Pytest Suite (21 test files)
├── .env.example                  # Environment template
├── alembic.ini                   # Alembic configuration
├── requirements.txt              # Production & development dependencies
└── README.md
```

---

## ⚙️ Installation & Setup Guide

### 1. Prerequisites
- **Python**: Version `3.11` or higher installed
- **PostgreSQL**: Version `14` or higher running locally or in Docker
- **Git**: Installed on your system

---

### 2. Clone and Setup Environment

```bash
# Navigate to the backend directory
cd backend

# Create a Python virtual environment
python -m venv .venv

# Activate the virtual environment
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Windows (CMD):
.venv\Scripts\activate.bat
# On Linux / macOS:
source .venv/bin/activate
```

---

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

### 4. Configure Environment Variables

Copy the `.env.example` template into a new `.env` file:

```bash
# Windows PowerShell
cp .env.example .env
```

Edit `.env` to match your local database and secrets:

```dotenv
APP_NAME=CortexCX
APP_VERSION=1.0.0
DEBUG=True
HOST=127.0.0.1
PORT=8000

# PostgreSQL Connection String
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/cortexcx_db

# Security
SECRET_KEY=your-custom-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080
REFRESH_TOKEN_EXPIRE_MINUTES=10080
REFRESH_TOKEN_EXPIRE_DAYS=30

# AI Provider Configuration (mock | openai)
AI_PROVIDER=mock
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini

# Embeddings & Vector Search (mock | openai)
EMBEDDING_PROVIDER=mock
EMBEDDING_DIMENSION=128
```

---

### 5. Database Setup & Migrations

Ensure PostgreSQL has a database named `cortexcx_db` (or the name you specified in `DATABASE_URL`):

```sql
CREATE DATABASE cortexcx_db;
```

Run all database migrations using Alembic:

```bash
alembic upgrade head
```

---

## 🏃 Running the Application

Start the FastAPI application with Uvicorn:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The server will be live at:
- **API Root**: `http://127.0.0.1:8000`
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`
- **ReDoc Documentation**: `http://127.0.0.1:8000/redoc`

---

## 🧪 Running Automated Tests

Run the complete test suite using `pytest`:

```bash
# Run all tests from backend directory
pytest tests

# Run tests with verbose output
pytest -v tests
```

---

## 🔑 Default Accounts & Credentials

For local testing and administration:

| Role | Email | Default Password | Description |
|---|---|---|---|
| **Owner / Admin** | `admin@cortexcx.com` | `Password123!` | Primary administrator account with full workspace access |

---

## 📡 API Endpoint Overview

| Module | Method | Endpoint | Description | Auth Required |
|---|---|---|---|---|
| **Auth** | `POST` | `/auth/register` | Register new workspace & owner | Public |
| **Auth** | `POST` | `/auth/login` | Login with email and password | Public |
| **Auth** | `POST` | `/auth/refresh` | Refresh access token using refresh token | Public |
| **Auth** | `POST` | `/auth/logout` | Revoke refresh token | Bearer Token |
| **Users** | `GET` | `/users/me` | Get authenticated user profile | Bearer Token |
| **Workspaces**| `GET` | `/workspaces/me` | Get current workspace details | Bearer Token |
| **Workspaces**| `GET` | `/workspaces/users` | List workspace members | Owner / Admin |
| **Workspaces**| `POST`| `/workspaces/users` | Invite/add member to workspace | Owner / Admin |
| **Customers** | `GET` | `/customers` | List & filter workspace customers | Bearer Token |
| **Customers** | `POST`| `/customers` | Create new customer profile | Bearer Token |
| **Conversations**| `GET` | `/conversations` | List conversation threads | Bearer Token |
| **Conversations**| `POST`| `/conversations` | Create conversation thread | Bearer Token |
| **Conversations**| `POST`| `/conversations/{id}/messages` | Send message in thread | Bearer Token |
| **Knowledge** | `POST`| `/knowledge/sources` | Create knowledge source container | Owner / Admin |
| **Knowledge** | `POST`| `/knowledge/sources/{id}/documents` | Upload & ingest document | Owner / Admin |
| **Knowledge** | `POST`| `/knowledge/documents/{id}/embed` | Generate embeddings for document chunks | Owner / Admin |
| **Knowledge** | `POST`| `/knowledge/search` | Semantic cosine similarity vector search | Bearer Token |
| **AI / RAG** | `POST`| `/ai/conversations/{id}/rag` | Generate grounded RAG AI response | Agent / Admin / Owner |
| **AI** | `POST`| `/ai/conversations/{id}/suggest-reply` | Generate AI suggestion draft | Agent / Admin / Owner |
| **AI** | `POST`| `/ai/conversations/{id}/analyze` | Analyze sentiment & extract intent | Agent / Admin / Owner |

---

## 🛡️ Best Practices & Production Guidelines

1. **Security**: Ensure `SECRET_KEY` in production is a cryptographically strong 64-character string.
2. **Environment Isolation**: Never commit `.env` or production secrets to Git.
3. **Database**: In high-load production environments, ensure connection pooling and adequate index configurations on `workspace_id` columns.
4. **AI Providers**: Switch `AI_PROVIDER=openai` and `EMBEDDING_PROVIDER=openai` and provide `OPENAI_API_KEY` when deploying live LLM capabilities.