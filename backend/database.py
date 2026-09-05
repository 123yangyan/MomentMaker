from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import BASE_DIR

DATABASE_URL = f"sqlite:///{(BASE_DIR / 'momentmaker.db').as_posix()}"

# SQLite 默认限制单线程访问；FastAPI 会在线程池中执行同步数据库操作。
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """所有 SQLAlchemy 数据表的基类。"""


def migrate_database() -> None:
    """
    为已有的 MVP 数据库补充新字段。

    create_all 只能创建新表，不能修改已存在的表，因此这里执行一次
    可重复运行的轻量迁移。项目正式上线后应改用 Alembic。
    """
    inspector = inspect(engine)
    if "files" not in inspector.get_table_names():
        return

    file_columns = {column["name"] for column in inspector.get_columns("files")}
    file_additions = {
        "image_created_at": "DATETIME",
        "mime_type": "VARCHAR(100)",
        "width": "INTEGER",
        "height": "INTEGER",
        "session_id": "VARCHAR(36)",
    }
    with engine.begin() as connection:
        for name, sql_type in file_additions.items():
            if name not in file_columns:
                connection.execute(text(f"ALTER TABLE files ADD COLUMN {name} {sql_type}"))

    if "tasks" in inspector.get_table_names():
        task_columns = {column["name"] for column in inspector.get_columns("tasks")}
        task_additions = {
            "story_text": "VARCHAR(500)",
            "work_title": "VARCHAR(30)",
            "selected_file_ids": "TEXT DEFAULT '[]'",
            "session_id": "VARCHAR(36)",
            "vl_model": "VARCHAR(100)",
            "image_model_requested": "VARCHAR(100)",
            "image_model_used": "VARCHAR(100)",
            "prompt_version": "VARCHAR(30)",
            "error_code": "VARCHAR(50)",
            "internal_error": "TEXT",
            "updated_at": "DATETIME",
            "started_at": "DATETIME",
            "completed_at": "DATETIME",
        }
        with engine.begin() as connection:
            for name, sql_type in task_additions.items():
                if name not in task_columns:
                    connection.execute(
                        text(f"ALTER TABLE tasks ADD COLUMN {name} {sql_type}")
                    )

    if "works" in inspector.get_table_names():
        work_columns = {column["name"] for column in inspector.get_columns("works")}
        if "title" not in work_columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE works ADD COLUMN title VARCHAR(30) "
                        "DEFAULT '未命名作品'"
                    )
                )


def get_db():
    """为每次请求提供独立数据库会话，并在结束后关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
