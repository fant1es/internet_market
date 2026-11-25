import json
from pathlib import Path
from urllib.parse import urlparse

LOCALES_DIR = Path(__file__).parent / "locales"
SUPPORTED = ("ru", "en")
DEFAULT = "ru"
COOKIE = "lang"


def _flatten(d: dict, prefix: str = "") -> dict:
    """Складывает вложенные словари через точку:
    {en: {word: hello}} в {end.word: hello}"""
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(_flatten(v, f"{prefix}{k}."))
        else:
            out[f"{prefix}{k}"] = v
    return out

# Получаем для каждого языка сложенные словари
_STRINGS = {
    code: _flatten(json.loads((LOCALES_DIR / f"{code}.json").read_text(encoding="utf-8")))
    for code in SUPPORTED
}


def translate(key: str, lang: str = DEFAULT, **params) -> str:
    # Получаем нужный язык, а затем сам ключ
    text = _STRINGS.get(lang, {}).get(key) or _STRINGS[DEFAULT].get(key, key)
    return text.format(**params) if params else text


def js_strings(lang: str) -> dict:
    """Только ключи js.* и status.*: их забирает браузер."""
    keys = [k for k in _STRINGS[DEFAULT] if k.startswith(("js.", "status."))]
    return {k: translate(k, lang) for k in keys}


def detect_lang(request) -> str:
    # Внутри cookie в Accept-Language
    code = request.cookies.get(COOKIE)
    if code in SUPPORTED:
        return code
    for part in request.headers.get("accept-language", "").split(","):
        base = part.split(";")[0].strip().lower()[:2]
        if base in SUPPORTED:
            return base
    return DEFAULT


def safe_back_url(referer: str | None) -> str:
    """Из Referer берём только путь и query, чтобы не получить open redirect."""
    if not referer:
        return "/"
    p = urlparse(referer)
    path = p.path or "/"
    if not path.startswith("/") or path.startswith("//"):
        return "/"
    return path + (f"?{p.query}" if p.query else "")