"""Cruza as turmas da checklist-captacao com a base de agendamentos da
ConsultaJá (mesma planilha usada pelos pipelines de agendas-pac-real e da
raiz do workspace -- dados-fonte/Base_Consulta_Ja*.xlsx, compartilhada,
nunca baixada por este pipeline) pra substituir a coluna "Agendamentos" da
checklist (preenchida à mão) pelo número real de pacientes atendidos
(Status "Compareceu"/"Atendido"), casando por curso+turma+unidade+data.

Decisão de 2026-09-16: a checklist-captacao continua sendo a fonte de
"Slots previstos" (capacidade planejada) -- só o numerador (quantos
vieram de verdade) passa a vir da ConsultaJá.

O nome da turma na checklist ("Dermatologia Cirurgica SP T01") é composto
de curso + unidade (sigla) + turma; a ConsultaJá guarda essas 3 partes em
colunas separadas (Curso/Unidade/Turma), com Unidade por extenso
("São Paulo") e às vezes com inconsistência de acentuação no próprio
Curso (ex.: "Dermatologia Cirurgica" e "Dermatologia Cirúrgica" convivem
na mesma planilha) -- por isso toda comparação aqui é feita sem acento e
em minúsculo (ver _norm()).
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

REALIZADO_STATUSES = {"Compareceu", "Atendido"}

UNIDADE_MAP = {"BSB": "Brasília", "CPS": "Campinas", "SP": "São Paulo", "ONL": "Online"}

_TURMA_RE = re.compile(r"^(.+)\s(BSB|CPS|SP|ONL)\sT0*(\d+)$")


def _norm(value) -> str:
    s = str(value if value is not None else "").strip().lower()
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def parse_turma(turma: str) -> tuple[str, str, int] | None:
    """'Dermatologia Cirurgica SP T01' -> ('dermatologia cirurgica', 'SP', 1).
    None se o nome não seguir o padrão "<curso> <sigla unidade> T<número>".
    """
    m = _TURMA_RE.match(turma.strip())
    if not m:
        return None
    curso, unidade_code, num = m.groups()
    return _norm(curso), unidade_code, int(num)


def find_latest(dados_fonte_dir: Path) -> Path | None:
    """Última planilha Base_Consulta_Ja*.xlsx baixada em dados-fonte/ (por
    este pipeline ou pelos vizinhos agendas-pac-real/raiz -- pasta
    compartilhada). O nome do arquivo leva a data (YY_MM_DD), então ordenar
    o nome já ordena por data."""
    candidates = sorted(dados_fonte_dir.glob("Base_Consulta_Ja*.xlsx"))
    return candidates[-1] if candidates else None


class Attendance:
    """Lookup (curso, unidade sigla, turma, data) -> nº de pacientes que
    realmente vieram, mais o conjunto de combinações curso+unidade+turma
    conhecidas da ConsultaJá (pra distinguir "0 nessa data" de "turma que a
    ConsultaJá nem conhece")."""

    def __init__(self, counts: dict[tuple[str, str, int, str], int], known_turmas: set[tuple[str, str, int]]):
        self._counts = counts
        self._known_turmas = known_turmas

    def get(self, turma: str, data_str: str) -> tuple[int | None, str | None]:
        """Devolve (valor, motivo_do_fallback). motivo_do_fallback é None
        quando o valor veio da ConsultaJá; caso contrário, valor é None e
        motivo explica por que (pra quem chamar decidir o fallback)."""
        parsed = parse_turma(turma)
        if parsed is None:
            return None, "nome de turma fora do padrão \"<curso> <sigla> T<número>\""
        curso_norm, unidade_code, turma_num = parsed
        if (curso_norm, unidade_code, turma_num) not in self._known_turmas:
            return None, "turma não encontrada na ConsultaJá (curso/unidade/turma sem nenhum registro)"
        return self._counts.get((curso_norm, unidade_code, turma_num, data_str), 0), None


def build_attendance(xlsx_path: Path) -> Attendance:
    df = pd.read_excel(xlsx_path)
    unidade_code_by_norm = {_norm(nome): code for code, nome in UNIDADE_MAP.items()}

    known_turmas: set[tuple[str, str, int]] = set()
    counts: dict[tuple[str, str, int, str], int] = {}

    for row in df.itertuples(index=False):
        unidade_code = unidade_code_by_norm.get(_norm(row.Unidade))
        if unidade_code is None:
            continue
        try:
            turma_num = int(row.Turma)
        except (TypeError, ValueError):
            continue
        curso_norm = _norm(row.Curso)
        known_turmas.add((curso_norm, unidade_code, turma_num))

        if row.Status not in REALIZADO_STATUSES:
            continue
        data_str = str(row.Data).strip()
        key = (curso_norm, unidade_code, turma_num, data_str)
        counts[key] = counts.get(key, 0) + 1

    return Attendance(counts, known_turmas)
