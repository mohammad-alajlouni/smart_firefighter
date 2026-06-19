"""
main.py — FastAPI web application for the Smart Firefighter Wearable System.

Run from the project root:
    uvicorn web.main:app --reload

Dashboard: http://127.0.0.1:8000
"""

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# ── Path setup ────────────────────────────────────────────────────────────────
WEB_DIR = Path(__file__).parent
PROJECT_ROOT = WEB_DIR.parent
# Add both web/ and python/ so imports work whether run via uvicorn or directly
sys.path.insert(0, str(WEB_DIR))
sys.path.insert(0, str(PROJECT_ROOT / "python"))

from config import Config
from simulation_manager import SimulationManager, VALID_SCENARIOS
from mqtt_service import MQTTService
from log_service import LogService
from report_service import ReportService

# ── Singletons ────────────────────────────────────────────────────────────────
sim_manager = SimulationManager()
mqtt_service = MQTTService()
log_service = LogService()
report_service = ReportService()

# Connected WebSocket clients
_ws_clients: set[WebSocket] = set()


async def broadcast(payload: dict) -> None:
    """Send a telemetry payload to every connected browser client."""
    if not _ws_clients:
        return
    msg = json.dumps(payload, ensure_ascii=False)
    dead: set[WebSocket] = set()
    for ws in list(_ws_clients):
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    _ws_clients.difference_update(dead)


# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()
    Config.ensure_dirs()
    sim_manager.set_loop_and_callback(loop, broadcast)
    mqtt_service.set_context(loop, broadcast)
    mqtt_service.start()
    yield
    sim_manager.stop()
    mqtt_service.stop()


app = FastAPI(title="Smart Firefighter Wearable System", lifespan=lifespan)

app.mount(
    "/static",
    StaticFiles(directory=str(WEB_DIR / "static")),
    name="static",
)
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))


# ── Page routes ───────────────────────────────────────────────────────────────

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "broker": Config.BROKER_HOST,
            "port": Config.BROKER_PORT,
            "topic": Config.TELEMETRY_TOPIC,
            "firefighter_id": Config.FIREFIGHTER_ID,
            "scenarios": VALID_SCENARIOS,
        },
    )


@app.get("/simulation")
async def simulation_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="simulation.html",
        context={
            "broker": Config.BROKER_HOST,
            "port": Config.BROKER_PORT,
            "topic": Config.TELEMETRY_TOPIC,
            "firefighter_id": Config.FIREFIGHTER_ID,
            "scenarios": VALID_SCENARIOS,
        },
    )


@app.get("/logs")
async def logs_page(request: Request):
    return templates.TemplateResponse(request=request, name="logs.html")


@app.get("/reports")
async def reports_page(request: Request):
    return templates.TemplateResponse(request=request, name="reports.html")


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/telemetry")
async def ws_telemetry(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.add(websocket)
    try:
        if sim_manager.last_payload:
            await websocket.send_text(
                json.dumps(sim_manager.last_payload, ensure_ascii=False)
            )
        while True:
            # Receive to detect disconnect; ignore client messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        _ws_clients.discard(websocket)


# ── Pydantic request models ───────────────────────────────────────────────────

class StartRequest(BaseModel):
    scenario: str = "normal"


class ScenarioRequest(BaseModel):
    scenario: str


class PublishOnceRequest(BaseModel):
    scenario: Optional[str] = None


# ── Simulation control API ────────────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    return sim_manager.get_status()


@app.post("/api/simulation/start")
async def start_simulation(body: StartRequest):
    scenario = body.scenario if body.scenario in VALID_SCENARIOS else "normal"
    sim_manager.start(scenario)
    return {"status": "started", "scenario": scenario}


@app.post("/api/simulation/stop")
async def stop_simulation():
    sim_manager.stop()
    return {"status": "stopped"}


@app.post("/api/simulation/set-scenario")
async def set_scenario(body: ScenarioRequest):
    if body.scenario not in VALID_SCENARIOS:
        return JSONResponse(
            {"error": f"Unknown scenario: {body.scenario}"}, status_code=400
        )
    sim_manager.scenario = body.scenario
    return {"status": "ok", "scenario": body.scenario}


@app.post("/api/simulation/publish-once")
async def publish_once(body: PublishOnceRequest = None):
    scenario = (body.scenario if body and body.scenario else None) or sim_manager.scenario
    payload = sim_manager.publish_once(scenario)
    return payload


# ── Logs API ──────────────────────────────────────────────────────────────────

@app.get("/api/logs")
async def get_logs(
    limit: int = Query(100, ge=1, le=5000),
    status: Optional[str] = Query(None),
    firefighter_id: Optional[str] = Query(None),
):
    records = log_service.get_logs(
        limit=limit,
        status_filter=status,
        ff_filter=firefighter_id,
    )
    return {"count": len(records), "records": records}


# ── Reports API ───────────────────────────────────────────────────────────────

@app.get("/api/report/summary")
async def get_summary():
    # Combine in-memory session records with any previously saved CSV records
    csv_records = log_service.get_logs(limit=5000)
    all_records = sim_manager.records + [
        r for r in csv_records
        if r not in sim_manager.records
    ]
    return report_service.get_summary(all_records)


@app.get("/api/report/export-csv")
async def export_csv():
    path = log_service.get_latest_csv()
    if not path:
        return JSONResponse({"error": "No CSV log file found"}, status_code=404)
    return FileResponse(
        str(path), filename=path.name, media_type="text/csv"
    )


@app.get("/api/report/export-summary")
async def export_summary():
    csv_records = log_service.get_logs(limit=5000)
    path = report_service.save_summary(sim_manager.records or csv_records)
    return {"path": str(path), "filename": path.name, "status": "saved"}


# ── Wokwi file downloads ──────────────────────────────────────────────────────

@app.get("/api/wokwi/diagram")
async def wokwi_diagram():
    """Download the Wokwi circuit diagram (diagram.json) for import into wokwi.com."""
    path = PROJECT_ROOT / "wokwi" / "diagram.json"
    return FileResponse(str(path), filename="diagram.json", media_type="application/json")


@app.get("/api/wokwi/sketch")
async def wokwi_sketch():
    """Download the ESP32 sketch (sketch.ino) for import into wokwi.com."""
    path = PROJECT_ROOT / "wokwi" / "sketch.ino"
    return FileResponse(str(path), filename="sketch.ino", media_type="text/plain")


@app.get("/api/wokwi/libraries")
async def wokwi_libraries():
    """Download the libraries manifest (libraries.txt) for import into wokwi.com."""
    path = PROJECT_ROOT / "wokwi" / "libraries.txt"
    return FileResponse(str(path), filename="libraries.txt", media_type="text/plain")
