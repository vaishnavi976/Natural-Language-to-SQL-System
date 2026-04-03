import re
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    is_valid: bool
    error: str = field(default="")
_BLOCKED_STATEMENTS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|"
    r"MERGE|UPSERT|RENAME|EXEC|EXECUTE|CALL|DO)\b",
    re.IGNORECASE,
)

_BLOCKED_KEYWORDS = re.compile(
    r"\b(xp_|sp_|GRANT|REVOKE|SHUTDOWN|ATTACH|DETACH|"
    r"PRAGMA|LOAD_EXTENSION)\b",
    re.IGNORECASE,
)

_SYSTEM_TABLES = re.compile(
    r"\b(sqlite_master|sqlite_temp_master|sqlite_sequence|"
    r"information_schema|sys\.)\b",
    re.IGNORECASE,
)

_STRIP_COMMENTS = re.compile(r"(--[^\n]*|/\*.*?\*/)", re.DOTALL)
_MULTI_STMT     = re.compile(r";\s*\S")


def validate_sql(sql: str) -> ValidationResult:
    """
    Returns ValidationResult(is_valid=True) when sql is safe to execute,
    ValidationResult(is_valid=False, error=<reason>) otherwise.
    """
    if not sql or not sql.strip():
        return ValidationResult(False, "Empty SQL query.")

    clean = _STRIP_COMMENTS.sub(" ", sql).strip()

    if _MULTI_STMT.search(clean):
        return ValidationResult(False, "Multiple SQL statements are not allowed.")

    tokens    = clean.split()
    first_tok = tokens[0].upper() if tokens else ""
    if first_tok not in ("SELECT", "WITH", "EXPLAIN"):
        return ValidationResult(
            False,
            f"Only SELECT queries are permitted. Received statement type: '{first_tok}'.",
        )

    m = _BLOCKED_STATEMENTS.search(clean)
    if m:
        return ValidationResult(False, f"Forbidden SQL statement: '{m.group()}'.")

    m = _BLOCKED_KEYWORDS.search(clean)
    if m:
        return ValidationResult(False, f"Forbidden keyword detected: '{m.group()}'.")

    m = _SYSTEM_TABLES.search(clean)
    if m:
        return ValidationResult(False, f"Access to system tables is not allowed: '{m.group()}'.")

    return ValidationResult(True)
