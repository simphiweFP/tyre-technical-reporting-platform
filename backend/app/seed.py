from sqlalchemy import select, text

from backend.app.core.config import get_settings
from backend.app.core.database import SessionLocal
from backend.app.core.security import hash_password
from backend.app.modules.branches.infrastructure import Branch
from backend.app.modules.claims.automation import continue_existing_reports
from backend.app.modules.identity.domain import Role
from backend.app.modules.identity.infrastructure import User


def seed() -> None:
    settings = get_settings()
    admin_email = settings.seed_admin_email.strip().lower()
    claims_email = settings.seed_claims_admin_email.strip().lower()
    if not claims_email or claims_email == admin_email:
        raise RuntimeError("SEED_CLAIMS_ADMIN_EMAIL must be a separate email address")
    with SessionLocal() as db:
        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(2026100213)"))
        branches = {"PHX": "Phoenix", "DBN": "Durban", "JHB": "Johannesburg"}
        for code, name in branches.items():
            if not db.scalar(select(Branch).where(Branch.code == code)):
                db.add(Branch(code=code, name=name))
        db.flush()
        branch = db.scalar(select(Branch).where(Branch.code == "PHX"))
        admin = db.scalar(select(User).where(User.email == admin_email))
        if not admin:
            db.add(
                User(
                    email=admin_email,
                    full_name="System Administrator",
                    job_title="Administrator",
                    password_hash=hash_password(settings.seed_admin_password),
                    role=Role.ADMINISTRATOR,
                    branch_id=branch.id,
                )
            )
        claims_admin = db.scalar(select(User).where(User.email == claims_email))
        if claims_admin and claims_admin.role != Role.CLAIMS_ADMINISTRATOR:
            raise RuntimeError(
                "SEED_CLAIMS_ADMIN_EMAIL belongs to another role; "
                "choose a different email or update the role in Administration"
            )
        if not claims_admin:
            db.add(
                User(
                    email=claims_email,
                    full_name="Claims Administrator",
                    job_title="Claims Administrator",
                    password_hash=hash_password(
                        settings.seed_claims_admin_password
                        or settings.seed_admin_password
                    ),
                    role=Role.CLAIMS_ADMINISTRATOR,
                    branch_id=branch.id,
                )
            )
        db.flush()
        continue_existing_reports(db)
        db.commit()


if __name__ == "__main__":
    from backend.app.core.migrations import run_database_migrations

    get_settings().validate_for_startup()
    run_database_migrations()
    seed()
