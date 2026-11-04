from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from app.config import settings

SHOP_NAME = "Магазин"

_env = Environment(
    loader=FileSystemLoader(Path(__file__).resolve().parent.parent / "templates" / "emails"),
    autoescape=select_autoescape(enabled_extensions=("html",), default=False),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


@dataclass(frozen=True)
class EmailContent:
    subject: str
    text: str
    html: str


def _render(template: str, /, **ctx) -> tuple[str, str]:
    """Рендерит пару template.txt + template.html с общими переменными."""
    ctx = {"shop_name": SHOP_NAME, "ttl_minutes": settings.email_token_ttl_minutes, **ctx}
    return (_env.get_template(f"{template}.txt").render(**ctx),
            _env.get_template(f"{template}.html").render(**ctx))


def mask_email(email: str) -> str:
    """new@example.com -> n***@example.com"""
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


def build_confirm_new_email(name: str, link: str) -> EmailContent:
    """Письмо со ссылкой подтверждения, уходит на новый адрес."""
    text, html = _render("confirm_email", name=name, link=link)
    return EmailContent(f"Подтвердите новую почту в магазине «{SHOP_NAME}»", text, html)


def build_old_email_notice(name: str, new_email: str) -> EmailContent:
    """Уведомление о запросе смены, уходит на старый адрес."""
    text, html = _render("email_change_notice", name=name, new_email=mask_email(new_email))
    return EmailContent(f"Запрошена смена почты в магазине «{SHOP_NAME}»", text, html)