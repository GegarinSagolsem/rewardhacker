"""Alembic environment. The database URL comes from DATABASE_URL (.env), never alembic.ini."""

import os
from logging.config import fileConfig

from alembic import context

from rewardhacker.api import tables  # noqa: F401  (registers the models on Base.metadata)
from rewardhacker.api.db import Base, make_engine, normalize_url
from rewardhacker.api.settings import ConfigError
from rewardhacker.config import load_dotenv

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    load_dotenv()
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise ConfigError("DATABASE_URL is not set (see .env.example)")
    return url


def run_migrations_offline() -> None:
    context.configure(url=normalize_url(_url()), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = make_engine(_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
