from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from .config import database_url

_engine = None
_Session = None


def engine():
    global _engine, _Session
    if _engine is None:
        url = database_url()
        kw = {}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kw = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
        _engine = create_engine(url, future=True, **kw)
        _Session = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


@contextmanager
def session_scope():
    engine()
    s = _Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def init_db():
    from .models import Base
    Base.metadata.create_all(engine())
