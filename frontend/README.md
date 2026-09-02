# 🌐 CortexCX Frontend

> **Modern Next.js Customer Experience & Support Intelligence Dashboard**  
> Built with Next.js (App Router), React, TypeScript, Tailwind CSS, Lucide Icons, and Axios.

---

## 📌 Overview

The CortexCX Frontend provides a fast, responsive, and intuitive interface for support agents, team leads, and administrators. It connects directly with the CortexCX FastAPI backend to manage omnichannel conversations, customer profiles, knowledge base vector search, and AI-assisted responses in real-time.

---

## 🚀 Key Features

- 🔐 **Authentication & Session Management**: Login, registration, token refresh, and protected routes with `AuthContext`.
- 📊 **Executive Dashboard**: Key customer support metrics, real-time KPI cards, and workload overview.
- 💬 **Conversation Hub**: Active ticket queue, status/priority filtering, agent assignment, and message threads.
- 🤖 **AI Copilot & RAG**: Live AI suggested replies, sentiment & intent detection, and knowledge-grounded suggestions.
- 👥 **Customer 360**: Searchable customer directory with full customer detail view and conversation history.
- 📚 **Knowledge Base Management**: Document ingestion, status tracking, chunk exploration, and semantic vector search tester.
- ⚙️ **Workspace Settings**: Team user directory, role configurations, and workspace settings.

---

## 🏗️ Project Structure

```text
frontend/
├── public/                 # Static assets & icons
├── src/
│   ├── api/                # API client layer (Axios instances & endpoints)
│   │   ├── ai.ts           # AI & RAG endpoints
│   │   ├── auth.ts         # Login, register, refresh tokens
│   │   ├── client.ts       # Axios interceptors & base config
│   │   ├── conversations.ts # Conversation & message CRUD
│   │   ├── customers.ts    # Customer profiles & history
│   │   ├── knowledge.ts    # Knowledge base & semantic search
│   │   └── workspace.ts    # Workspace & team management
│   ├── app/                # Next.js App Router
│   │   ├── (auth)/login/   # Authentication page
│   │   ├── conversations/  # Conversation list & detail ([id])
│   │   ├── customers/      # Customer directory & detail ([id])
│   │   ├── dashboard/      # Overview & metrics
│   │   ├── knowledge/      # Knowledge base & semantic search
│   │   ├── settings/       # Workspace settings & team
│   │   ├── globals.css     # Tailwind & global theme styling
│   │   ├── layout.tsx      # Root layout
│   │   └── page.tsx        # Redirect / entry
│   ├── components/
│   │   ├── layout/         # AppLayout, Sidebar, TopNav, ProtectedRoute
│   │   └── ui/             # Reusable UI component library (Badges, Cards, Modals)
│   ├── context/            # Global React Contexts (AuthContext)
│   └── types/              # TypeScript definitions & API interfaces
├── package.json
├── tsconfig.json
└── tailwind.config.ts
```

---

## ⚙️ Installation & Setup

### 1. Prerequisites
- **Node.js**: `v18.17` or higher
- **npm** or **yarn** / **pnpm**
- **CortexCX Backend** running on `http://127.0.0.1:8000`

---

### 2. Install Dependencies

```bash
cd frontend
npm install
```

---

### 3. Configure Environment Variables (Optional)

Create `.env.local` in `frontend/` if overriding the default API URL:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

---

### 4. Run Development Server

```bash
npm run dev
```

The application will be accessible at: **`http://localhost:3000`**

---

## 🧪 Build for Production

```bash
npm run build
npm run start
```
