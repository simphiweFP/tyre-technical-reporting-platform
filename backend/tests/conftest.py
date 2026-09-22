import os

os.environ["DATABASE_URL"] = "sqlite:///./test_tyres.db"
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-tests"
os.environ["ENVIRONMENT"] = "test"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import get_settings
from backend.app.core.database import Base, get_db
from backend.app.core.security import hash_password
from backend.app.main import app
from backend.app.modules.branches.infrastructure import Branch
from backend.app.modules.identity.domain import Role
from backend.app.modules.identity.infrastructure import User


@pytest.fixture()
def client(tmp_path):
    get_settings().media_root = str(tmp_path / "images")
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with TestingSession() as db:
        branch = Branch(code="PHX", name="Phoenix")
        db.add(branch)
        db.flush()
        db.add_all(
            [
                User(
                    email="admin@example.com",
                    full_name="Admin",
                    password_hash=hash_password("Password123!"),
                    role=Role.ADMINISTRATOR,
                    branch_id=branch.id,
                ),
                User(
                    email="viewer@example.com",
                    full_name="Viewer",
                    password_hash=hash_password("Password123!"),
                    role=Role.VIEWER,
                    branch_id=branch.id,
                ),
            ]
        )
        db.commit()

    def override_db():
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
