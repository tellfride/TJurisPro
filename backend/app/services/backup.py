import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from ..config import settings

logger = logging.getLogger("jurispro.backup")


def _backup_dir() -> Path:
    base = Path(__file__).resolve().parent.parent.parent  # backend/
    path = (base / settings.backup_dir).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_backup() -> Path | None:
    """Executa mysqldump e salva o arquivo em backups/. Retorna o caminho
    gerado, ou None se falhar (ex: mysqldump não instalado/no PATH)."""
    out_dir = _backup_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_file = out_dir / f"{settings.db_name}_{timestamp}.sql"

    cmd = [
        settings.mysqldump_path,
        f"-h{settings.db_host}",
        f"-P{settings.db_port}",
        f"-u{settings.db_user}",
        f"-p{settings.db_password}",
        "--single-transaction",
        "--routines",
        "--events",
        settings.db_name,
    ]
    try:
        with open(out_file, "wb") as fh:
            result = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, timeout=600)
        if result.returncode != 0:
            logger.error("mysqldump falhou: %s", result.stderr.decode(errors="ignore"))
            out_file.unlink(missing_ok=True)
            return None
        logger.info("Backup diário gerado em %s", out_file)
        _apply_retention(out_dir)
        return out_file
    except (OSError, subprocess.SubprocessError) as exc:
        logger.error("Não foi possível executar mysqldump (%s). Verifique MYSQLDUMP_PATH no .env", exc)
        out_file.unlink(missing_ok=True)
        return None


def _apply_retention(out_dir: Path) -> None:
    cutoff = datetime.now() - timedelta(days=settings.backup_retention_days)
    for f in out_dir.glob(f"{settings.db_name}_*.sql"):
        try:
            if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink()
        except OSError:
            continue
