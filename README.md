# Chat Plus

Minimal FastAPI chat app with JWT auth, group & direct chats, AI summarization, and a local content moderator.

Quick Start (Windows cmd)

- Create & activate venv:

  python -m venv .venv
  \.venv\Scripts\activate

- Install dependencies:

  pip install -r requirements.txt

- Run server:

  \.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000

- Run tests:

  pytest -q

Key Features

- Auth: JWT-based register/login for API and web UI (access token stored in a cookie).
- Chats: Group & direct rooms, membership management, realtime via WebSocket plus HTTP fallback.
- Find friends: Search users and start direct chats from the web UI.
- Summarizer: AI endpoint that summarizes recent messages; a `Summarize chat` button is available in room UI.
- Content moderator: On-device MiniLMv2-based toxicity filter that blocks toxic messages before saving. Configurable threshold in `app/ai/moderator.py`.

Quick pointers

- Templates: `app/templates/` (UI files)
- Web UI routes: `app/web/router.py`
- WebSocket + app entry: `app/main.py`
- Business logic: `app/services/chat_service.py`
- Moderator: `app/ai/moderator.py`

Notes

- When a message is blocked the web UI shows a red error box with the block reason; moderator logs contain details.
- Use `--reload` during development for automatic server restarts after code changes.

Want it even shorter or need an `.env` example? I can add that next.
