import re
from pathlib import Path

from app.i18n import _STRINGS

# Все места, где в коде встречается код ошибки
PATTERNS = [
    r'AppError\(\s*[\w.]+\s*,\s*"([a-z_]+)"',
    r'field_error\(\s*"[a-z_]+"\s*,\s*"([a-z_]+)"',
    r'\bcode="([a-z_]+)"',
    r'\b[A-Z_]*CODE\s*=\s*"([a-z_]+)"',
    r'get_or_404\([^)]*?,\s*"([a-z_]+)"\s*\)',
    r'commit_or_409\(\s*db\s*,\s*"([a-z_]+)"',
    r'InvalidImageError\(\s*"([a-z_]+)"',
]


def test_error_codes_have_translations():
    used = set()
    for path in Path("app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in PATTERNS:
            used |= set(re.findall(pattern, text))
    for lang in _STRINGS:
        missing = sorted(c for c in used if f"err.{c}" not in _STRINGS[lang])
        assert not missing, f"Нет перевода ({lang}) для кодов: {missing}"
