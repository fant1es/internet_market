import asyncio
from dataclasses import dataclass
from io import BytesIO
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# Форматы для ячеек Excel
MONEY = "#,##0.00"
DATETIME = "DD.MM.YYYY HH:MM"
LOCAL_TZ = ZoneInfo("Europe/Minsk")

def to_local(dt):
    """Перевод времени в локальное. Для Excel убираем временной пояс."""
    if dt is None:
        return None
    from datetime import timezone
    return dt.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ).replace(tzinfo=None)


@dataclass
class Column:
    """Класс с данными для форматирования ячеек Excel"""
    title: str
    fmt: str | None = None # Формат ячейки
    total: bool = None # Нужно ли указать итоги в конце (=SUM())
    highlight_lt: bool | None = None # Нужно ли подсветить значения меньше допустимых


@dataclass
class Sheet:
    """Класс с данными для листа Excel"""
    title: str
    columns: list[Column]
    rows: list[tuple] # Данные


def _build(sheets: list[Sheet]) -> bytes:
    """Создание файла с переданными листами."""
    wb = Workbook()
    wb.remove(wb.active) # Удаляем автоматически созданный лист
    header_fill = PatternFill("solid", fgColor="DDE3EA")

    for s in sheets:
        # У Excel есть ограничение по длине имени листа
        ws = wb.create_sheet(s.title[:31])
        ws.append([c.title for c in s.columns])

        # Стили для названий колонок
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = header_fill
            cell.alignment = Alignment(vertical="center", wrap_text=True)

        # Вставка данных в виде строк
        for rows in s.rows:
            ws.append(rows)

        last = len(s.rows) + 1
        for index, c in enumerate(s.columns, 1):
            letter = get_column_letter(index)
            if c.fmt:
                for r in range(2, last + 1):
                    ws.cell(r, index).number_format = c.fmt
            if c.highlight_lt is not None and s.rows:
                ws.conditional_formatting.add(
                    f"{letter}2:{letter}{last}",
                    CellIsRule(operator="lessThan", formula=[str(c.highlight_lt)],
                               font=Font(color="9C0006"), fill=PatternFill("solid", fgColor="FFC7CE"))
                )

            longest = max([len(c.title)] + [len(str(r[index - 1] or "")) for r in s.rows])
            ws.column_dimensions[letter].width = min(max(longest + 2, 10), 50)

        ws.freeze_panes = "A2"
        if s.rows:
            ws.auto_filter.ref = f"A1:{get_column_letter(len(s.columns))}{last}"
            if any(c.total for c in s.columns):
                total_row = last + 1
                ws.cell(total_row, 1, "Итого").font = Font(bold=True)
                for idx, c in enumerate(s.columns, 1):
                    if c.total:
                        letter = get_column_letter(idx)
                        cell = ws.cell(total_row, idx, f"=SUM({letter}2:{letter}{last})")
                        cell.font = Font(bold=True)
                        if c.fmt:
                            cell.number_format = c.fmt

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def build_xlsx(sheets: list[Sheet]) -> bytes:
    return await asyncio.to_thread(_build, sheets)

