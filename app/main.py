from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.logger import configure_logging, get_logger

# Configure logging 
configure_logging()
logger = get_logger(__name__)

from app.core.db import Base, engine, get_db
from app.models.user import User
from app.models.chat import ChatRoom
from app.websocket.manager import ConnectionManager
from app.security.security import decode_jwt_token
from app.services.chat_service import ChatService
from app.schemas.chat import MessageCreate
from app.api.auth_router import router as auth_router
from app.api.chat_router import ChatRouter
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from app.api.user_router import UserRouter
from app.web.router import web_router
from app.admin.router import admin_router
from app.api.ai_router import ai_router
from app.api.password_router import router as password_router



templates = Jinja2Templates(directory="app/templates")

chat_router = ChatRouter()

app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
)

manager = ConnectionManager()
chat_service = ChatService()
user_router = UserRouter()

app.include_router(user_router.router, prefix="/api/v1")
app.include_router(chat_router.router, prefix="/api/v1")
app.include_router(web_router)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(password_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(admin_router)



@app.on_event("startup")
async def on_startup():
    logger.info("Creating database tables (startup)")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured (startup)")


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/web/login", status_code=302)


@app.websocket("/ws/chat")
async def websocket_chat(
    websocket: WebSocket,
    room_id: int = Query(...),
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket endpoint for both direct (1-1) and group chat.
    - Auth via access token (query param `token`)
    - room_id specifies which room to join.
    """

    payload = decode_jwt_token(token)
    if not payload or payload.get("type") != "access":
        logger.warning("WebSocket auth failed: invalid token or wrong type")
        await websocket.close(code=4401)
        return

    user_id = int(payload["sub"]) 

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user or not user.is_active:
        logger.warning("WebSocket auth failed: user not found or inactive: %s", user_id)
        await websocket.close(code=4403)
        return

    room = await chat_service.get_room_for_user(db, room_id, user_id)
    if not room:
        logger.warning("WebSocket join denied: user %s not member of room %s", user_id, room_id)
        await websocket.close(code=4404)
        return

    await manager.connect(room_id, websocket)
    logger.info("WebSocket connected: user=%s room=%s", user_id, room_id)

    try:
        while True:
            data = await websocket.receive_json()
            content = data.get("content")
            if not content:
                continue

            message_in = MessageCreate(room_id=room_id, content=content)
            msg_obj, block_reason = await chat_service.save_message(
                db,
                message_in=message_in,
                sender_id=user_id,
            )
            
            # If message was blocked, send error notification to user
            if block_reason:
                logger.warning("Message blocked for user %s: %s", user_id, block_reason)
                error_response = {
                    "type": "error",
                    "message": f"Your message was blocked: {block_reason}"
                }
                logger.debug("Sending error response: %s", error_response)
                await websocket.send_json(error_response)
                continue

            logger.debug("Saved message %s in room %s from user %s", getattr(msg_obj, 'id', None), room_id, user_id)

            await manager.broadcast(
                room_id,
                {
                    "id": msg_obj.id,
                    "room_id": msg_obj.room_id,
                    "sender_id": msg_obj.sender_id,
                    "content": msg_obj.content,
                    "created_at": msg_obj.created_at.isoformat(),
                },
            )

    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)
        logger.info("WebSocket disconnected: user=%s room=%s", user_id, room_id)
    except Exception:
        manager.disconnect(room_id, websocket)
        logger.exception("WebSocket error for user=%s room=%s", user_id, room_id)
        await websocket.close()
