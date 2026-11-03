from fastapi import HTTPException


def field_error(field: str, msg: str) -> HTTPException:
    """422 в формате pydantic: фронтэнд будет привязывать ошибку к полю по последнему элементу loc."""
    return HTTPException(status_code=422, detail=[
        {"loc": ["body", field], "msg": msg, "type": "value_error"}
    ])