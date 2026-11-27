import re
from pathlib import Path

from app.i18n import _STRINGS

# Коды, по которым ищется перевод err.<код>
PATTERNS = [
    r'AppError\(\s*[\w.]+\s*,\s*"([a-z_]+)"',
    r'field_error\(\s*"[a-z_]+"\s*,\s*"([a-z_]+)"',
    r'\bcode="([a-z_]+)"',
    r'\b[A-Z_]*CODE\s*=\s*"([a-z_]+)"',
    r'get_or_404\([^)]*?,\s*"([a-z_]+)"\s*\)',
    r'commit_or_409\(\s*db\s*,\s*"([a-z_]+)"',
    r'InvalidImageError\(\s*"([a-z_]+)"',
]
# Коды валидаторов схем: перевод err.validation.<код>
VALIDATION_PATTERN = r'ValidationCode\(\s*"([a-z_]+)"'

# Стандартные типы ошибок Pydantic, которые переводятся
STANDARD_TYPES = [
    "missing", "invalid", "string_too_short", "string_too_long", "greater_than", "greater_than_equal",
    "less_than", "less_than_equal", "decimal_max_digits", "decimal_max_places", "decimal_whole_digits",
    "decimal_parsing", "decimal_type", "int_parsing", "int_type", "int_from_float",
    "string_pattern_mismatch", "extra_forbidden", "json_invalid", "invalid_email",
]


def _scan(patterns):
    found = set()
    for path in Path("app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            found |= set(re.findall(pattern, text))
    return found


def test_error_codes_have_translations():
    used = _scan(PATTERNS)
    for lang in _STRINGS:
        missing = sorted(c for c in used if f"err.{c}" not in _STRINGS[lang])
        assert not missing, f"Нет перевода ({lang}) для кодов: {missing}"


def test_validation_codes_have_translations():
    used = _scan([VALIDATION_PATTERN]) | set(STANDARD_TYPES)
    for lang in _STRINGS:
        missing = sorted(c for c in used if f"err.validation.{c}" not in _STRINGS[lang])
        assert not missing, f"Нет перевода ({lang}) для кодов валидации: {missing}"
