from sqlalchemy import select, text

from backend.app.core.database import SessionLocal
from backend.app.modules.branches.infrastructure import Branch
from backend.app.modules.claims.automation import continue_existing_reports


DEFAULT_BRANCHES: dict[str, str] = {
    "PHX": "Phoenix",
    "DBN": "Durban",
    "JHB": "Johannesburg",
    "CPT": "Cape Town",
}


def seed_branches(db) -> None:
    """Ensure required default branches exist without touching user-added branches."""
    existing_codes = set(
        db.scalars(select(Branch.code).where(Branch.code.in_(DEFAULT_BRANCHES))).all()
    )

    for code, name in DEFAULT_BRANCHES.items():
        if code not in existing_codes:
            db.add(Branch(code=code, name=name))


def seed() -> None:
    """Seed required application data only.

    User identities and roles are owned by RT-Auth and are therefore not seeded
    locally. Branch seeding is idempotent: required defaults are created only
    when missing, while branches added through the application are preserved.
    """
    with SessionLocal() as db:
        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(2026100213)"))

        seed_branches(db)
        db.flush()

        continue_existing_reports(db)
        db.commit()


if __name__ == "__main__":
    from backend.app.core.config import get_settings
    from backend.app.core.migrations import run_database_migrations

    get_settings().validate_for_startup()
    run_database_migrations()
    seed()
