from datetime import datetime
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    data_type: str
    nullable: bool
    is_primary_key: bool = False


@dataclass(frozen=True)
class ForeignKey:
    constraint: str
    table: str
    column: str
    ref_table: str
    ref_column: str


@dataclass(frozen=True)
class TableInfo:
    name: str
    columns: list[ColumnInfo]
    estimated_rows: int = 0


@dataclass(frozen=True)
class SchemaInfo:
    schema: str
    tables: list[TableInfo]
    foreign_keys: list[ForeignKey]


@dataclass(frozen=True)
class ConnectionTestResult:
    ok: bool
    message: str
    server_version: str | None = None
    read_only_verified: bool = False


@dataclass(frozen=True)
class SampleResult:
    """Sample rows for one table. Lives in memory only and must NEVER be stored."""
    table: str
    columns: list[str]
    rows: list[tuple] = field(repr=False)  # repr=False so values never leak into logs

    def column_values(self, column: str) -> list:
        idx = self.columns.index(column)
        return [row[idx] for row in self.rows]
@dataclass(frozen=True)
class RowMatches:
    """Where one identifier matched in one column. Counts and row keys only, never the values."""
    table: str
    column: str
    match_count: int
    key_columns: list[str]
    keys: list[tuple] = field(repr=False)  # primary-key values of up to `limit` matching rows


@dataclass(frozen=True)
class ObjectInfo:
    key: str
    size: int
    last_modified: datetime | None = None