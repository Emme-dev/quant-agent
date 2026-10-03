"""Read-only helpers a future LLM-driven interface could call to answer
questions about the system -- status, recent runs, current positions.
Deliberately contains NOTHING that places an order, changes a risk limit,
or resets the kill switch. Those stay human-triggered (scripts/
reset_killswitch.py, a direct config edit) specifically so an LLM layer, if
one is ever wired in here, can describe and explain what happened, but
never gets authority to move money or change risk parameters itself."""
from sqlalchemy import select, desc

from ..core.db import session_scope
from ..core.models import Run, Position, Account
from ..risk import killswitch


def get_status(account_name: str) -> dict:
    with session_scope() as s:
        acct = s.scalar(select(Account).where(Account.name == account_name))
        if acct is None:
            return {"error": f"no account named '{account_name}'"}
        positions = s.query(Position).filter_by(account_id=acct.id).all()
        last_run = s.scalar(
            select(Run).where(Run.account_id == acct.id)
            .order_by(desc(Run.started_at)).limit(1)
        )
        return {
            "account": account_name,
            "mode": acct.mode,
            "kill_switch_tripped": killswitch.is_tripped(),
            "kill_switch_reason": killswitch.reason(),
            "positions": {p.symbol: p.qty for p in positions if p.qty},
            "last_run_status": last_run.status if last_run else None,
            "last_run_summary": last_run.summary if last_run else None,
        }


def get_recent_runs(account_name: str, limit: int = 7) -> list[dict]:
    with session_scope() as s:
        acct = s.scalar(select(Account).where(Account.name == account_name))
        if acct is None:
            return []
        runs = s.scalars(
            select(Run).where(Run.account_id == acct.id)
            .order_by(desc(Run.started_at)).limit(limit)
        ).all()
        return [
            {"run_id": r.id, "status": r.status, "started_at": str(r.started_at),
             "summary": r.summary}
            for r in runs
        ]
