from typing import Annotated

from fastapi import Depends, Request


def _get_lang(request: Request) -> str:
    return request.state.lang


Lang = Annotated[str, Depends(_get_lang)]