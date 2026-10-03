"""Day 7: minimal, READ-ONLY status API. Deliberately exposes nothing that
places an order, changes a risk limit, or resets the kill switch -- see
agent/tools.py's docstring for why that boundary is intentional. Resetting
the kill switch in particular stays CLI-only (scripts/reset_killswitch.py),
requiring someone to actually read the reason and type 'reset' -- an
unauthenticated HTTP endpoint is the wrong place for that action on a
project with no auth layer.

Run with:
    uvicorn quantagent.api.main:app --port 8000
Then visit http://127.0.0.1:8000/docs for interactive API docs."""
from fastapi import FastAPI

from .routes import status

app = FastAPI(
    title="quant-agent status API",
    version="0.1.0",
    description=(
        "Read-only status endpoints. No endpoint here can place an order, "
        "change a risk limit, or reset the kill switch."
    ),
)
app.include_router(status.router)


@app.get("/")
def root():
    return {"name": "quant-agent", "docs": "/docs"}
