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


def _no_dups(pairs):
    """Проверка на отсутствие дубликатов ключей, так как это вызовет ошибку."""
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError(f"Дубликат ключа в JSON: {k}")
        d[k] = v
    return d


def _load(code: str) -> dict:
    """Собирает все файлы папки locales/<code>/ в один плоский словарь."""
    strings = {}
    for path in sorted((LOCALES_DIR / code).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_dups)
        flat = _flatten(data)
        dup = strings.keys() & flat.keys()
        if dup:
            raise ValueError(f"Ключи повторяются в {path.name}: {sorted(dup)}")
        strings.update(flat)
    return strings


# Получаем для каждого языка сложенные словари
_STRINGS = {code: _load(code) for code in SUPPORTED}


def translate(key: str, lang: str = DEFAULT, **params) -> str:
    # Получаем нужный язык, затем русский, затем сам ключ
    text = _STRINGS.get(lang, {}).get(key) or _STRINGS[DEFAULT].get(key, key)
    return text.format(**params) if params else text


def js_strings(lang: str, admin: bool = False) -> dict:
    """Ключи js.* и status.*, которые забирает браузер.
    Тексты админки (js.admin.*) отдаём только администратору."""
    keys = [k for k in _STRINGS[DEFAULT]
            if k.startswith(("js.", "status."))
            and (admin or not k.startswith("js.admin."))]
    return {k: translate(k, lang) for k in keys}


def detect_lang(request) -> str:
    # cookie, затем Accept-Language, затем русский
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