import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass(frozen=True)
class PostgresConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str = field(repr=False)  # never printed in logs
    connect_timeout: int = 5
    statement_timeout_ms: int = 10_000

    @classmethod
    def from_env(cls) -> "PostgresConfig":
        """Builds a config for the READ-ONLY scanning user from environment variables."""
        load_dotenv()
        return cls(
            host=os.environ["SOURCE_HOST"],
            port=int(os.environ["SOURCE_PORT"]),
            dbname=os.environ["SOURCE_DB"],
            user=os.environ["SOURCE_READER_USER"],
            password=os.environ["SOURCE_READER_PASSWORD"],
        )