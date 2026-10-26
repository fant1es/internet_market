import re
from typing import Annotated

from pydantic import AfterValidator

_SEPARATORS = re.compile(r"[\s\-().]")
_E164 = re.compile(r"^\+[1-9]\d{7,14}$")


def normalize_phone(value: str) -> str:
    """Любой международный номер приводим '+<цифры>' с проверкой, например:
    '+375 29 123-45-67', '+7 999 123-45-67', '+1 (415) 555-0100',
    """
    raw = _SEPARATORS.sub("", value)

    if re.fullmatch(r"80\d{9}", raw):
        raw = "+375" + raw[2:]
    elif raw.startswith("00"): # 00 вместо +
        raw = "+" + raw[2:]

    if not _E164.fullmatch(raw):
        raise ValueError("Неверно указан номер. Пример номера: +375 29 123-45-67")
    return raw


Phone = Annotated[str, AfterValidator(normalize_phone)]