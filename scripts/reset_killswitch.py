"""Manual reset after reviewing why the kill switch tripped.
python scripts/reset_killswitch.py"""
from quantagent.risk import killswitch
from quantagent.core.logging import get_logger

log = get_logger("reset_killswitch")

if __name__ == "__main__":
    r = killswitch.reason()
    if r is None:
        log.info("Kill switch is not tripped. Nothing to do.")
    else:
        print(f"Kill switch was tripped with reason:\n  {r}\n")
        confirm = input("Type 'reset' to clear it: ")
        if confirm.strip().lower() == "reset":
            killswitch.reset()
            log.info("Kill switch reset.")
        else:
            log.info("Not confirmed. Kill switch left tripped.")
