from typing import Iterable


def describe_changes(old: dict, new: dict, show_values: Iterable[str] = ()) -> str:
    """Строка для аудита вида 'price: 100→120, name'. Пустая, если ничего не изменилось."""
    show = set(show_values)
    parts = []
    for field, new_value in new.items():
        old_value = old.get(field)
        if old_value == new_value:
            continue
        # Значения было/стало показываем только для полей из show_values
        parts.append(f"{field}: {old_value} -> {new_value}" if field in show else field)
    return ", ".join(parts)