from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def _mysql_compatible_snapshot_isolation(dbapi_connection, _connection_record):
    """MariaDB >= 11.6.2 liga innodb_snapshot_isolation por padrão: uma leitura
    bloqueante (SELECT ... FOR UPDATE) que encontra linha alterada por outra
    transação DEPOIS do "retrato" da sessão falha com o erro 1020, em vez de ler o
    dado confirmado mais recente como o MySQL faz. O sistema foi escrito para o
    comportamento do MySQL — next_loan_number() depende dele para numerar a OS sem
    colisão quando dois empréstimos são lançados ao mesmo tempo. Em servidores que
    não têm a variável (MySQL), o SET falha e é ignorado."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("SET SESSION innodb_snapshot_isolation=OFF")
    except Exception:
        pass
    finally:
        cursor.close()


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
