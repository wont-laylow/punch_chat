import asyncio
import pytest

from app.websocket.manager import ConnectionManager


class DummyWebSocket:
    def __init__(self, fail_send=False):
        self.accepted = False
        self.sent = []
        self.fail_send = fail_send

    async def accept(self):
        self.accepted = True

    async def send_json(self, message):
        if self.fail_send:
            raise RuntimeError("send failed")
        # simulate async send delay
        await asyncio.sleep(0)
        self.sent.append(message)


@pytest.mark.asyncio
async def test_connect_and_broadcast_and_disconnect():
    mgr = ConnectionManager()
    ws1 = DummyWebSocket()
    ws2 = DummyWebSocket()

    # connect two websockets to room 1
    await mgr.connect(1, ws1)
    await mgr.connect(1, ws2)

    assert 1 in mgr.active_connections
    assert ws1 in mgr.active_connections[1]
    assert ws2 in mgr.active_connections[1]

    # broadcast message
    msg = {"hello": "world"}
    await mgr.broadcast(1, msg)

    assert ws1.sent[0] == msg
    assert ws2.sent[0] == msg

    # disconnect ws1
    mgr.disconnect(1, ws1)
    assert ws1 not in mgr.active_connections.get(1, set())

    # disconnect ws2
    mgr.disconnect(1, ws2)
    assert 1 not in mgr.active_connections


@pytest.mark.asyncio
async def test_broadcast_handles_send_errors():
    mgr = ConnectionManager()
    good = DummyWebSocket()
    bad = DummyWebSocket(fail_send=True)

    await mgr.connect(2, good)
    await mgr.connect(2, bad)

    # broadcast should not raise despite one failing
    await mgr.broadcast(2, {"x": 1})

    # good should have received message
    assert good.sent and good.sent[0]["x"] == 1
    # bad may have raised and been removed
    assert bad not in mgr.active_connections.get(2, set())
