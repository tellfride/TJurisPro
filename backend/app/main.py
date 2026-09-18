import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings as app_settings
from .database import Base, engine
from .routers import audit, auth, clients, companies, dashboard, imports, loans, reports, settings, users, whatsapp_templates
from .services.scheduler import start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    logging.getLogger("jurispro").info("JurisPRO iniciado")
    yield


# Documentação interativa só com ENABLE_DOCS=true (desenvolvimento).
_docs = {} if app_settings.enable_docs else {"docs_url": None, "redoc_url": None, "openapi_url": None}
app = FastAPI(title="JurisPRO", version="1.0.0", lifespan=lifespan, **_docs)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    """O erro 422 padrão devolve, para cada campo, o valor que foi enviado
    ("input") e o padrão da validação ("ctx"). Numa tentativa de login isso
    ecoaria a senha digitada e, em qualquer rota, expõe regras internas. Devolve
    só onde está o erro e qual é."""
    errors = [
        {"loc": list(err.get("loc", ())), "msg": err.get("msg", "Valor inválido"), "type": err.get("type", "value_error")}
        for err in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


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


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
