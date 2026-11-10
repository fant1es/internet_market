import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# Форматы для ячеек Excel
MONEY = "#,##0.00"
DATETIME = "DD.MM.YYYY HH:MM"
LOCAL_TZ = ZoneInfo("Europe/Minsk")

# Оформление
TITLE_ROW, SUBTITLE_ROW, HEADER_ROW, FIRST_ROW = 1, 2, 3, 4
_side = Side(style="thin", color="BFBFBF")
BORDER = Border(left=_side, right=_side, top=_side, bottom=_side)
TITLE_FILL = PatternFill("solid", fgColor="2F5597")
HEADER_FILL = PatternFill("solid", fgColor="DDE3EA")
ZEBRA_FILL = PatternFill("solid", fgColor="F5F7FA")
TOTAL_FILL = PatternFill("solid", fgColor="FFF2CC")


def to_local(dt):
    """Перевод времени из UTC (без пояса) в локальное. Для Excel пояс убираем."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ).replace(tzinfo=None)


@dataclass
class Column:
    """Описание колонки Excel"""
    title: str
    fmt: str | None = None              # Формат ячейки
    total: bool = False                 # Добавить итог в конце (=SUM())
    highlight_lt: int | None = None     # Порог для подсветки


@dataclass
class Sheet:
    """Описание листа Excel"""
    title: str                          # Название вкладки (до 31 символа)
    columns: list[Column]
    rows: list[tuple]                   # Данные
    heading: str | None = None          # Заголовок в ячейке над таблицей (по умолчанию title)


def _build(sheets: list[Sheet]) -> bytes:
    """Создание файла с переданными листами."""
    wb = Workbook()
    wb.remove(wb.active) # Удаляем автоматически созданный лист
    generated = to_local(datetime.now(timezone.utc).replace(tzinfo=None))

    for s in sheets:
        # У Excel есть ограничение по длине имени листа
        ws = wb.create_sheet(s.title[:31])

        # Рамки сами рисуют таблицу
        ws.sheet_view.showGridLines = False
        ncols = len(s.columns)
        last_col = get_column_letter(ncols)
        last = FIRST_ROW + len(s.rows) - 1

        # Заголовок и подзаголовок
        ws.cell(TITLE_ROW, 1, s.heading or s.title)
        ws.cell(SUBTITLE_ROW, 1, f"Сформировано: {generated:%d.%m.%Y %H:%M}")

        if ncols > 1:
            ws.merge_cells(start_row=TITLE_ROW, start_column=1, end_row=TITLE_ROW, end_column=ncols)
            ws.merge_cells(start_row=SUBTITLE_ROW, start_column=1, end_row=SUBTITLE_ROW, end_column=ncols)
        # Заливка и рамка на все ячейки объединения
        for col in range(1, ncols + 1):
            ws.cell(TITLE_ROW, col).fill = TITLE_FILL

        t = ws.cell(TITLE_ROW, 1)
        t.font = Font(bold=True, size=14, color="FFFFFF")
        t.alignment = Alignment(vertical="center", indent=1)
        ws.row_dimensions[TITLE_ROW].height = 28
        sub = ws.cell(SUBTITLE_ROW, 1)
        sub.font = Font(italic=True, size=9, color="6C757D")
        sub.alignment = Alignment(indent=1)

        # Шапка таблицы
        for idx, c in enumerate(s.columns, 1):
            cell = ws.cell(HEADER_ROW, idx, c.title)
            cell.font = Font(bold=True)
            cell.fill = HEADER_FILL
            cell.border = BORDER
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions[HEADER_ROW].height = 24

        # Данные
        for r_off, row in enumerate(s.rows):
            r = FIRST_ROW + r_off
            for idx, (value, c) in enumerate(zip(row, s.columns), 1):
                cell = ws.cell(r, idx, value)
                cell.border = BORDER
                cell.alignment = Alignment(vertical="center")
                if c.fmt:
                    cell.number_format = c.fmt
                if r_off % 2 == 1:
                    cell.fill = ZEBRA_FILL

        # Подсветка и ширина колонок
        for idx, c in enumerate(s.columns, 1):
            letter = get_column_letter(idx)
            if c.highlight_lt is not None and s.rows:
                ws.conditional_formatting.add(
                    f"{letter}{FIRST_ROW}:{letter}{last}",
                    CellIsRule(operator="lessThan", formula=[str(c.highlight_lt)],
                               font=Font(color="9C0006"),
                               fill=PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")),
                )
            longest = max([len(c.title)] + [len(str(r[idx - 1] or "")) for r in s.rows])
            ws.column_dimensions[letter].width = min(max(longest + 3, 12), 50)

        # Фильтр и закрепление с итогами
        ws.freeze_panes = ws.cell(FIRST_ROW, 1)   # Закреплены заголовок, дата и шапка
        if s.rows:
            ws.auto_filter.ref = f"A{HEADER_ROW}:{last_col}{last}"
            if any(c.total for c in s.columns):
                total_row = last + 1
                label_idx = next((i for i, c in enumerate(s.columns, 1) if not c.total), 1)
                for idx, c in enumerate(s.columns, 1):
                    cell = ws.cell(total_row, idx)
                    cell.fill = TOTAL_FILL
                    cell.border = BORDER
                    cell.font = Font(bold=True)
                    if idx == label_idx:
                        cell.value = "Итого"
                    elif c.total:
                        letter = get_column_letter(idx)
                        cell.value = f"=SUM({letter}{FIRST_ROW}:{letter}{last})"
                        if c.fmt:
                            cell.number_format = c.fmt

        # Печать
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.print_title_rows = f"{HEADER_ROW}:{HEADER_ROW}"

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def build_xlsx(sheets: list[Sheet]) -> bytes:
    return await asyncio.to_thread(_build, sheets)

