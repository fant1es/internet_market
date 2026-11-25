from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, pass_context, select_autoescape

from app.config import settings
from app.i18n import DEFAULT, translate
from app.models import Order

_env = Environment(
    loader=FileSystemLoader(Path(__file__).resolve().parent.parent / "templates" / "emails"),
    autoescape=select_autoescape(enabled_extensions=("html",), default=False),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


@pass_context
def _t(ctx, key: str, **params) -> str:
    # язык берём из контекста рендера: его передаёт _render
    return translate(key, ctx["lang"], **params)


_env.globals["t"] = _t


@dataclass(frozen=True)
class EmailContent:
    subject: str
    text: str
    html: str


def _shop(lang: str) -> str:
    return translate("common.shop", lang)


def _render(template: str, /, *, lang: str, **ctx) -> tuple[str, str]:
    """Рендерит пару template.txt + template.html с общими переменными."""
    ctx = {"lang": lang, "shop_name": _shop(lang),
           "ttl_minutes": settings.email_token_ttl_minutes, **ctx}
    return (_env.get_template(f"{template}.txt").render(**ctx),
            _env.get_template(f"{template}.html").render(**ctx))


def mask_email(email: str) -> str:
    """new@example.com -> n***@example.com"""
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


def build_confirm_new_email(name: str, link: str, lang: str = DEFAULT) -> EmailContent:
    """Письмо со ссылкой подтверждения, уходит на новый адрес."""
    text, html = _render("confirm_email", lang=lang, name=name, link=link)
    return EmailContent(translate("email.confirm.subject", lang, shop=_shop(lang)), text, html)


def build_old_email_notice(name: str, new_email: str, lang: str = DEFAULT) -> EmailContent:
    """Уведомление о запросе смены, уходит на старый адрес."""
    text, html = _render("email_change_notice", lang=lang, name=name, new_email=mask_email(new_email))
    return EmailContent(translate("email.notice.subject", lang, shop=_shop(lang)), text, html)


def build_receipt_email(order: Order, name: str, lang: str = DEFAULT) -> EmailContent:
    """Рендер письма с чеком."""
    text, html = _render("receipt/receipt", lang=lang, name=name, order=order)
    return EmailContent(translate("email.receipt.subject", lang, id=order.id, shop=_shop(lang)), text, html)


def render_receipt_html(order: Order, lang: str = DEFAULT) -> str:
    """HTML чека для PDF и страницы в браузере."""
    return _env.get_template("receipt/receipt_pdf.html").render(
        lang=lang, shop_name=_shop(lang), order=order)