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


def build_raw(xlsx_path: Path, warnings: list[str] | None = None) -> list[list]:
    """Lê todas as abas que começam com "Ocupação" e devolve a lista de
    linhas no formato de RAW. `warnings` (opcional) recebe uma mensagem por
    aba pulada ou problema encontrado, pra quem chamar decidir como
    reportar."""
    if warnings is None:
        warnings = []

    with pd.ExcelFile(xlsx_path) as xls:
        sheet_names = [s for s in xls.sheet_names if s.startswith("Ocupação")]
        if not sheet_names:
            raise RuntimeError('Nenhuma aba iniciada com "Ocupação" encontrada na planilha.')

        rows: list[list] = []
        for sheet in sheet_names:
            rows.extend(_build_raw_sheet(xls, sheet, warnings))

    if not rows:
        raise RuntimeError("Nenhuma linha de prática válida encontrada em nenhuma aba.")

    return rows


def _build_raw_sheet(xls: pd.ExcelFile, sheet: str, warnings: list[str]) -> list[list]:
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
        ag = _to_int(r[col["agendamentos"]])

        rows.append([turma, unidade, modulo, data_str, sp, se, st, ag])

    return rows
