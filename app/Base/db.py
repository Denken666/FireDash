from typing import Generator

from sqlmodel import SQLModel, Session, create_engine

sqlite_file_name = "fire_dash.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(
    sqlite_url,
    echo=False,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
