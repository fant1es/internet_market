import re
from typing import Annotated

import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat, PhoneNumberType
from pydantic import AfterValidator, StringConstraints

DEFAULT_REGION = "BY"  # Для номеров без кода страны:
_ALLOWED_CHARS = re.compile(r"^[\d\s\-().+]+$")
_MOBILE_TYPES = {PhoneNumberType.MOBILE, PhoneNumberType.FIXED_LINE_OR_MOBILE}
_PHONE_HINT = "Неверно указан номер. Пример номера: +375 29 123-45-67"
_NAME_RE = re.compile(r"^(?=.*[^\W\s\d_])[A-Za-z0-9\s]+$")


def normalize_phone(value: str) -> str:
    """Любой валидный мобильный номер приводится к стандарту E.164, например '8 (029) 123-45-67' -> '+375291234567'."""
    raw = value.strip()
    if not _ALLOWED_CHARS.fullmatch(raw):
        raise ValueError("Номер может содержать только цифры, +, пробелы, скобки и дефисы")
    try:
        number = phonenumbers.parse(raw, DEFAULT_REGION)
    except NumberParseException:
        raise ValueError(_PHONE_HINT)
    if not phonenumbers.is_valid_number(number):
        raise ValueError(_PHONE_HINT)
    if phonenumbers.number_type(number) not in _MOBILE_TYPES:
        raise ValueError("Укажите номер мобильного телефона")
    return phonenumbers.format_number(number, PhoneNumberFormat.E164)


def _validate_name(v: str) -> str:
    # Проверка any, чтобы не проходили имена типа "---", "- -"
    if not _NAME_RE.fullmatch(v) or not any(c.isalpha() for c in v):
        raise ValueError("Имя должно содержать только буквы и пробелы")
    return v

Name = Annotated[str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=100),
    AfterValidator(_validate_name)
]
Phone = Annotated[str, AfterValidator(normalize_phone)]