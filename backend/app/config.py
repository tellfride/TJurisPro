import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


class Settings:
    db_host: str = _env("DB_HOST", "localhost")
    db_port: int = int(_env("DB_PORT", "3306"))
    db_name: str = _env("DB_NAME", "jurispro")
    db_user: str = _env("DB_USER", "jurispro")
    db_password: str = _env("DB_PASSWORD", "")

    jwt_secret: str = _env("JWT_SECRET", "change-me")
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = int(_env("JWT_EXPIRE_HOURS", "8"))

    cors_origins: list[str] = [o.strip() for o in _env("CORS_ORIGINS", "").split(",") if o.strip()]

    # /docs, /redoc e /openapi.json listam todas as rotas e campos da API — úteis em
    # desenvolvimento, mas em produção só ajudam quem está mapeando o sistema.
    enable_docs: bool = _env("ENABLE_DOCS", "").lower() in ("1", "true", "yes")

    mysqldump_path: str = _env("MYSQLDUMP_PATH", "mysqldump")
    backup_dir: str = _env("BACKUP_DIR", "../backups")
    backup_retention_days: int = int(_env("BACKUP_RETENTION_DAYS", "30"))

    # Importação de planilha: cada linha vira cliente + empréstimo + até 120 parcelas.
    import_max_rows: int = int(_env("IMPORT_MAX_ROWS", "1000"))

    admin_name: str = _env("ADMIN_NAME", "Administrador")
    admin_email: str = _env("ADMIN_EMAIL", "admin@jurispro.local")
    admin_password: str = _env("ADMIN_PASSWORD", "")

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


settings = Settings()

if settings.jwt_secret in ("", "change-me") or len(settings.jwt_secret) < 32:
    raise RuntimeError(
        "JWT_SECRET não definido, no valor padrão 'change-me' ou com menos de 32 caracteres "
        "em backend/.env. Gere um valor forte, ex.: openssl rand -hex 32"
    )
