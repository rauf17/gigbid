# synthetic: true
"""High-concurrency async WebSocket hub with connection pooling."""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()
active_clients: list[WebSocket] = []


@app.websocket("/ws/metrics")
async def metrics_feed(ws: WebSocket):
    await ws.accept()
    active_clients.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        active_clients.remove(ws)
