"""Transforma a planilha checklist-captacao.xlsx (abas "Ocupação - <Mês>")
na constante RAW que ../index.html usa: uma lista de
[turma, unidade, módulo, data, slots_previstos, overbooking, slots_totais,
agendamentos] por linha de prática.

Baseado na função handleUpload() que já existe dentro de index.html
(JavaScript -- roda quando alguém sobe a planilha pelo botão "Atualizar
dados" da própria página), com uma correção importante:

CORREÇÃO (achado ao montar este pipeline, 2026-09-15): o handleUpload() do
JS procura as colunas pelo texto "slots da prática"/"extra" -- nomes que a
planilha usava até a aba de Agosto. A partir de Setembro, as colunas foram
renomeadas pra "Slots previstos"/"Overbooking previsto", e o JS não
reconhece os nomes novos -- silenciosamente grava 0 nessas duas colunas pra
qualquer aba com o nome novo. Este módulo aceita os dois nomes (ver
ALIASES), então processa Set./Out. (e daí em diante) corretamente. Essa
mesma correção pode/deve ser levada de volta pro handleUpload() do JS se
alguém for continuar usando o botão de upload manual da página.
"""
from __future__ import annotations

import math
import unicodedata
from pathlib import Path

import pandas as pd

# Cada campo aceita qualquer um dos nomes de coluna já usados na planilha ao
# longo dos meses (comparação por "contém", já sem acento e em minúsculo --
# ver _norm()). Ordem importa: tenta o primeiro alias em todas as colunas
# antes de cair pro próximo, então um nome mais específico não perde pra um
# mais genérico que apareça em outra coluna.
ALIASES: dict[str, list[str]] = {
    "turma": ["turma"],
    "unidade": ["unidade"],
    "modulo": ["modulo"],
    "data": ["data da pratica", "data"],
    "slots_previstos": ["slots da pratica", "slots previstos"],
    "overbooking": ["slots extras", "overbooking previsto"],
    "slots_totais": ["slots totais", "total previsto"],
    "agendamentos": ["agendamento", "agendado"],
    # Não é um campo de saída -- só serve de referência posicional pro
    # fallback de "agendamentos" abaixo (ver _find_agendamentos_col()).
    "ocupacao": ["ocupacao"],
}

# Campos sem os quais uma aba não pode ser processada -- se algum estiver
# ausente, a aba inteira é pulada (com aviso), igual ao "if(headerRow<0)
# return;" do JS original pra aba sem cabeçalho reconhecível.
CAMPOS_OBRIGATORIOS = ("turma", "unidade", "modulo", "data", "agendamentos")

TURMAS_IGNORADAS = {"", "total do mês", "total do mes", "turma"}

# Abas "Ocupação - <Mês>" -> "MM", pra casar com getMesLabel() do index.html
# (mesmo dicionário de abreviação, só invertido). Só usado por build_pagas().
MESES_SHEET_TO_MM: dict[str, str] = {
    "mai": "05", "jun": "06", "jul": "07", "ago": "08",
    "set": "09", "out": "10", "nov": "11", "dez": "12", "jan": "01",
    "fev": "02", "mar": "03", "abr": "04",
}


def _norm(value) -> str:
    s = str(value if value is not None else "").strip().lower()
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _find_col(headers_norm: list[str], aliases: list[str]) -> int:
    for alias in aliases:
        for i, h in enumerate(headers_norm):
            if alias in h:
                return i
    return -1


def _to_date_str(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if isinstance(value, str):
        return value.strip()
    d = pd.to_datetime(value, errors="coerce")
    if pd.isna(d):
        return str(value).strip()
    return d.strftime("%d/%m/%Y")


def _to_int(value) -> int:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0
    try:
        return round(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return 0


def _find_header_row(sheet_df: pd.DataFrame) -> int | None:
    """Mesma heurística do JS: procura, nas 10 primeiras linhas, a que tem
    uma célula igual a "Turma" -- essa é a linha de cabeçalho."""
    for i in range(min(10, len(sheet_df))):
        values = [str(c).strip() for c in sheet_df.iloc[i].tolist()]
        if "Turma" in values:
            return i
    return None


def build_raw(xlsx_path: Path, warnings: list[str] | None = None, attendance=None) -> list[list]:
    """Lê todas as abas que começam com "Ocupação" e devolve a lista de
    linhas no formato de RAW. `warnings` (opcional) recebe uma mensagem por
    aba pulada ou problema encontrado, pra quem chamar decidir como
    reportar. `attendance` (opcional, ver attendance_consultaja.Attendance)
    substitui o valor de "Agendamentos" pelo número real de pacientes que
    compareceram, cruzado com a base da ConsultaJá por turma+data -- se
    None, mantém o valor da própria coluna "Agendamentos" da checklist."""
    if warnings is None:
        warnings = []

    with pd.ExcelFile(xlsx_path) as xls:
        sheet_names = [s for s in xls.sheet_names if s.startswith("Ocupação")]
        if not sheet_names:
            raise RuntimeError('Nenhuma aba iniciada com "Ocupação" encontrada na planilha.')

        rows: list[list] = []
        warned_turmas: set[str] = set()
        for sheet in sheet_names:
            rows.extend(_build_raw_sheet(xls, sheet, warnings, attendance, warned_turmas))

    if not rows:
        raise RuntimeError("Nenhuma linha de prática válida encontrada em nenhuma aba.")

    return rows


def _resolve_agendamentos(
    checklist_ag: int, turma: str, data_str: str, attendance, warnings: list[str], warned_turmas: set[str]
) -> int:
    if attendance is None:
        return checklist_ag
    valor, motivo = attendance.get(turma, data_str)
    if valor is not None:
        return valor
    if turma not in warned_turmas:
        warned_turmas.add(turma)
        warnings.append(
            f'Turma "{turma}": {motivo} -- mantive "Agendamentos" da checklist-captacao pra essa turma.'
        )
    return checklist_ag


def _build_raw_sheet(
    xls: pd.ExcelFile,
    sheet: str,
    warnings: list[str],
    attendance=None,
    warned_turmas: set[str] | None = None,
) -> list[list]:
    if warned_turmas is None:
        warned_turmas = set()
    rows: list[list] = []
    raw = xls.parse(sheet, header=None, dtype=object)

    header_row = _find_header_row(raw)
    if header_row is None:
        warnings.append(f'Aba "{sheet}" pulada -- nenhuma linha de cabeçalho com "Turma" encontrada.')
        return rows

    headers_norm = [_norm(c) for c in raw.iloc[header_row].tolist()]
    col = {key: _find_col(headers_norm, aliases) for key, aliases in ALIASES.items()}

    if col["agendamentos"] < 0 and col["ocupacao"] > 0:
        # Achado real (aba "Ocupação - Mai."): o cabeçalho dessa coluna
        # ficou como um número solto (ex. "322") em vez de "Agendamentos" --
        # erro de digitação na planilha de origem. Em todas as versões da
        # planilha (antiga e nova) a coluna de agendamentos vem
        # imediatamente antes da de "Ocupação"/"Taxa de ocupação", então
        # usa essa posição como último recurso.
        warnings.append(
            f'Aba "{sheet}": coluna "Agendamentos" sem nome reconhecível -- usando a coluna '
            f'antes de "Ocupação" (posição {col["ocupacao"] - 1}) como fallback.'
        )
        col["agendamentos"] = col["ocupacao"] - 1

    faltando = [k for k in CAMPOS_OBRIGATORIOS if col[k] < 0]
    if faltando:
        warnings.append(f'Aba "{sheet}" pulada -- colunas não encontradas: {", ".join(faltando)}.')
        return rows

    for i in range(header_row + 1, len(raw)):
        r = raw.iloc[i].tolist()
        turma = str(r[col["turma"]] or "").strip()
        if _norm(turma) in TURMAS_IGNORADAS:
            continue

        data_str = _to_date_str(r[col["data"]])
        if not data_str:
            continue

        unidade = str(r[col["unidade"]] or "").strip()
        modulo = str(r[col["modulo"]] or "").strip()
        sp = _to_int(r[col["slots_previstos"]]) if col["slots_previstos"] >= 0 else 0
        se = _to_int(r[col["overbooking"]]) if col["overbooking"] >= 0 else 0
        st = _to_int(r[col["slots_totais"]]) if col["slots_totais"] >= 0 else sp + se
        checklist_ag = _to_int(r[col["agendamentos"]])
        ag = _resolve_agendamentos(checklist_ag, turma, data_str, attendance, warnings, warned_turmas)

        rows.append([turma, unidade, modulo, data_str, sp, se, st, ag])

    return rows


def _sheet_mes_mm(sheet: str) -> str | None:
    """'Ocupação - Set.' -> '09'. Usa as 3 primeiras letras do nome do mês
    (sem acento, minúsculo) contra MESES_SHEET_TO_MM."""
    suffix = sheet.split("-", 1)[-1] if "-" in sheet else sheet
    key = _norm(suffix).strip(" .")[:3]
    return MESES_SHEET_TO_MM.get(key)


def _find_pagas_cols(headers_norm: list[str], sheet: str, warnings: list[str]) -> tuple[int, int]:
    """Localiza as colunas 'É paga?' e 'Valor total'. Achado ao montar isso
    (2026-09-16): nas abas de Jul./Ago., o cabeçalho de "Valor total" veio
    corrompido na planilha de origem (um número solto ou célula vazia em
    vez do texto) -- mesmo tipo de falha já visto na aba "Ocupação - Mai."
    pra "Agendamentos" (ver o fallback logo acima, em _build_raw_sheet).
    Nesses casos cai pro fallback posicional: a coluna de valor sempre vem
    logo depois de "É paga?" na planilha."""
    col_epaga = _find_col(headers_norm, ["e paga"])
    if col_epaga < 0:
        return -1, -1
    col_valor = _find_col(headers_norm, ["valor total"])
    if col_valor < 0:
        warnings.append(
            f'Aba "{sheet}": coluna "Valor total" sem nome reconhecível -- usando a coluna '
            f'logo após "É paga?" (posição {col_epaga + 1}) como fallback.'
        )
        col_valor = col_epaga + 1
    return col_epaga, col_valor


def build_pagas(
    xlsx_path: Path, warnings: list[str] | None = None, attendance=None
) -> dict[str, list[dict]]:
    """Lê as mesmas abas "Ocupação - <Mês>" e agrega, por turma, as práticas
    marcadas como pagas (coluna "É paga?" == "Sim"), somando slots e
    agendamentos e o "Valor total" de cada linha -- mesma fonte que hoje
    alimenta PAGAS_MES à mão em index.html, só que pra todos os meses com
    dado, não só Setembro. Meses sem a coluna "É paga?" (Mai./Jun.) ou sem
    nenhuma turma paga ficam de fora do dict. `attendance` (opcional, ver
    build_raw) substitui "Agendamentos" pelo número real de comparecimentos
    cruzado com a ConsultaJá, mesmo critério usado no RAW."""
    if warnings is None:
        warnings = []

    with pd.ExcelFile(xlsx_path) as xls:
        sheet_names = [s for s in xls.sheet_names if s.startswith("Ocupação")]
        data: dict[str, list[dict]] = {}
        warned_turmas: set[str] = set()
        for sheet in sheet_names:
            mm = _sheet_mes_mm(sheet)
            if mm is None:
                warnings.append(f'Aba "{sheet}" (turmas pagas): mês não reconhecido no nome da aba -- pulada.')
                continue
            turmas = _build_pagas_sheet(xls, sheet, warnings, attendance, warned_turmas)
            if turmas:
                data[mm] = turmas

    return data


def _build_pagas_sheet(
    xls: pd.ExcelFile,
    sheet: str,
    warnings: list[str],
    attendance=None,
    warned_turmas: set[str] | None = None,
) -> list[dict]:
    if warned_turmas is None:
        warned_turmas = set()
    raw = xls.parse(sheet, header=None, dtype=object)

    header_row = _find_header_row(raw)
    if header_row is None:
        return []

    headers_norm = [_norm(c) for c in raw.iloc[header_row].tolist()]
    col_turma = _find_col(headers_norm, ALIASES["turma"])
    col_unidade = _find_col(headers_norm, ALIASES["unidade"])
    col_modulo = _find_col(headers_norm, ALIASES["modulo"])
    col_sp = _find_col(headers_norm, ALIASES["slots_previstos"])
    col_se = _find_col(headers_norm, ALIASES["overbooking"])
    col_st = _find_col(headers_norm, ALIASES["slots_totais"])
    col_ag = _find_col(headers_norm, ALIASES["agendamentos"])
    col_data = _find_col(headers_norm, ALIASES["data"])
    col_epaga, col_valor = _find_pagas_cols(headers_norm, sheet, warnings)

    if col_turma < 0 or col_epaga < 0:
        return []  # aba sem coluna "É paga?" (ex.: Mai./Jun.) -- sem dado de turmas pagas

    def _cell(r: list, idx: int):
        return r[idx] if 0 <= idx < len(r) else None

    por_turma: dict[str, dict] = {}
    ordem: list[str] = []
    for i in range(header_row + 1, len(raw)):
        r = raw.iloc[i].tolist()
        turma = str(_cell(r, col_turma) or "").strip()
        if _norm(turma) in TURMAS_IGNORADAS:
            continue
        if _norm(str(_cell(r, col_epaga) or "")) != "sim":
            continue

        d = por_turma.setdefault(turma, {
            "turma": turma,
            "unidade": str(_cell(r, col_unidade) or "").strip(),
            "modulos": [],
            "sp": 0, "se": 0, "st": 0, "ag": 0, "n": 0, "valor": 0,
        })
        if turma not in ordem:
            ordem.append(turma)

        modulo = str(_cell(r, col_modulo) or "").strip()
        if modulo and modulo not in d["modulos"]:
            d["modulos"].append(modulo)

        data_str = _to_date_str(_cell(r, col_data)) if col_data >= 0 else ""
        checklist_ag = _to_int(_cell(r, col_ag))
        row_ag = _resolve_agendamentos(checklist_ag, turma, data_str, attendance, warnings, warned_turmas)

        d["sp"] += _to_int(_cell(r, col_sp))
        d["se"] += _to_int(_cell(r, col_se))
        d["st"] += _to_int(_cell(r, col_st))
        d["ag"] += row_ag
        d["n"] += 1
        d["valor"] += _to_int(_cell(r, col_valor))

    for turma in ordem:
        por_turma[turma]["valor60"] = round(por_turma[turma]["valor"] * 0.6)

    return [por_turma[t] for t in ordem]
