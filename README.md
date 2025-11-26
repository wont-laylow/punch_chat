# Chat Plus

Minimal FastAPI chat app with JWT auth, group & direct chats, and AI summarization.

Quick Start (Windows cmd)

- Create & activate venv:

  python -m venv .venv
  \.venv\Scripts\activate

- Install dependencies:

  pip install -r requirements.txt

- Run server:

  uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

- Run tests:

  pytest -q

Key Features

- Auth: JWT-based register/login for API and web UI (access token stored in a cookie).
- Chats: Group & direct rooms, membership management, realtime via WebSocket plus HTTP fallback.
- Find friends: Search users and start direct chats from the web UI.
- Summarizer: AI endpoint that summarizes recent messages; a `Summarize chat` button is available in room UI.

Quick pointers

- Templates: `app/templates/` (UI files)
- Web UI routes: `app/web/router.py`
- WebSocket + app entry: `app/main.py`
- Business logic: `app/services/chat_service.py`

Notes

- Use `--reload` during development for automatic server restarts after code changes.
- Content moderator has been disabled due to compute costs on free hosting.
