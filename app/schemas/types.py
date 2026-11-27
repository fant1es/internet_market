import re
from typing import Annotated

import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat, PhoneNumberType
from pydantic import AfterValidator, StringConstraints, EmailStr

from app.utils.errors import ValidationCode

DEFAULT_REGION = "BY"  # Для номеров без кода страны:
_ALLOWED_CHARS = re.compile(r"^[\d\s\-().+]+$")
_MOBILE_TYPES = {PhoneNumberType.MOBILE, PhoneNumberType.FIXED_LINE_OR_MOBILE}
_NAME_RE = re.compile(r"^(?=.*[^\W\s\d_])[A-Za-z\s]+$")

_PASSWORD_MIN_LEN = 8
_PASSWORD_MAX_LEN = 128

def _validate_password(v: str) -> str:
    if len(v) < _PASSWORD_MIN_LEN:
        raise ValidationCode("password_too_short", min=_PASSWORD_MIN_LEN)
    if len(v) > _PASSWORD_MAX_LEN:
        raise ValidationCode("password_too_long", max=_PASSWORD_MAX_LEN)
    if not v.isprintable():
        raise ValidationCode("password_invalid_chars")
    return v


def normalize_phone(value: str) -> str:
    """Любой валидный мобильный номер приводится к стандарту E.164, например '8 (029) 123-45-67' -> '+375291234567'."""
    raw = value.strip()
    if not _ALLOWED_CHARS.fullmatch(raw):
        raise ValidationCode("phone_chars")
    try:
        number = phonenumbers.parse(raw, DEFAULT_REGION)
    except NumberParseException:
        raise ValidationCode("phone_invalid")
    if not phonenumbers.is_valid_number(number):
        raise ValidationCode("phone_invalid")
    if phonenumbers.number_type(number) not in _MOBILE_TYPES:
        raise ValidationCode("phone_not_mobile")
    return phonenumbers.format_number(number, PhoneNumberFormat.E164)


def _validate_name(v: str) -> str:
    # Проверка any, чтобы не проходили имена типа "---", "- -"
    if not _NAME_RE.fullmatch(v) or not any(c.isalpha() for c in v):
        raise ValidationCode("name_invalid")
    return v

Name = Annotated[str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=100),
    AfterValidator(_validate_name)
]
Password = Annotated[str, AfterValidator(_validate_password)]
Phone = Annotated[str, AfterValidator(normalize_phone)]
Email = Annotated[EmailStr, AfterValidator(lambda v: v.lower()), ]