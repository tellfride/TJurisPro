import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings as app_settings
from .database import Base, engine
from .routers import audit, auth, clients, companies, dashboard, imports, loans, reports, settings, users, whatsapp_templates
from .services.scheduler import start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="JurisPRO", version="1.0.0")

# Frontend e API são servidos pela mesma origem (StaticFiles montado abaixo),
# então CORS não é necessário para o uso normal do sistema. allow_origins vazio
# por padrão (fecha requisições cross-origin); defina CORS_ORIGINS no .env
# (lista separada por vírgula) só se precisar integrar outro front-end/domínio.
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(companies.router)
app.include_router(users.router)
app.include_router(clients.router)
app.include_router(loans.router)
app.include_router(dashboard.router)
app.include_router(audit.router)
app.include_router(settings.router)
app.include_router(reports.router)
app.include_router(imports.router)
app.include_router(whatsapp_templates.router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    logging.getLogger("jurispro").info("JurisPRO iniciado")


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
