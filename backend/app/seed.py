from sqlalchemy import select

from backend.app.core.config import get_settings
from backend.app.core.database import SessionLocal
from backend.app.core.security import hash_password
from backend.app.modules.branches.infrastructure import Branch
from backend.app.modules.identity.domain import Role
from backend.app.modules.identity.infrastructure import User


def seed() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        branches = {"PHX": "Phoenix", "DBN": "Durban", "JHB": "Johannesburg"}
        for code, name in branches.items():
            if not db.scalar(select(Branch).where(Branch.code == code)):
                db.add(Branch(code=code, name=name))
        db.flush()
        branch = db.scalar(select(Branch).where(Branch.code == "PHX"))
        admin = db.scalar(
            select(User).where(User.email == settings.seed_admin_email.lower())
        )
        if not admin:
            db.add(
                User(
                    email=settings.seed_admin_email.lower(),
                    full_name="System Administrator",
                    job_title="Administrator",
                    password_hash=hash_password(settings.seed_admin_password),
                    role=Role.ADMINISTRATOR,
                    branch_id=branch.id,
                )
            )
        db.commit()


if __name__ == "__main__":
    seed()
