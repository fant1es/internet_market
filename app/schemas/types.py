import re
from typing import Annotated

from pydantic import AfterValidator, StringConstraints

_SEPARATORS = re.compile(r"[\s\-().]")
_E164 = re.compile(r"^\+[1-9]\d{7,14}$")
_NAME_RE = re.compile(r"^[a-zA-Zа-яА-ЯёЁ\- ]+$")

def _validate_name(v: str) -> str:
    # Проверка any, чтобы не проходили имена типа "---", "- -"
    if not _NAME_RE.fullmatch(v) or not any(c.isalpha() for c in v):
        raise ValueError("Имя должно содержать только буквы и пробелы")
    return v

def normalize_phone(value: str) -> str:
    """Любой международный номер пишем без пробелов с + и кодом с проверкой, например:
    '+375 29 123-45-67' -> '+375291234567'
    """
    raw = _SEPARATORS.sub("", value)

    if re.fullmatch(r"80\d{9}", raw):
        raw = "+375" + raw[2:]
    elif raw.startswith("00"): # 00 вместо +
        raw = "+" + raw[2:]

    if not _E164.fullmatch(raw):
        raise ValueError("Неверно указан номер. Пример номера: +375 29 123-45-67")
    return raw

Name = Annotated[str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=100),
    AfterValidator(_validate_name)
]
Phone = Annotated[str, AfterValidator(normalize_phone)]