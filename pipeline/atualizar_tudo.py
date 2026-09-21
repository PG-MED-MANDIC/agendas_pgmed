"""Orquestra a atualização do dashboard "Acompanhamento Semanal de
Práticas": lê dados-fonte/checklist-captacao.xlsx (baixado manualmente do
SharePoint -- ver README.md > "De onde vem o arquivo") e regrava RAW em
../index.html. Um comando só:

    python pipeline/atualizar_tudo.py

O número de "Agendamentos" é cruzado com dados-fonte/Base_Consulta_Ja*.xlsx
(planilha compartilhada com os pipelines de agendas-pac-real/raiz -- este
pipeline nunca a baixa, só reaproveita a mais recente já presente) pra
usar quantos pacientes ocupam o slot (qualquer Status != "Cancelado") em
vez do valor digitado na checklist-captacao -- ver pipeline/README.md >
"De onde vem o número de Agendamentos" e attendance_consultaja.py. Se a
planilha da ConsultaJá não existir, cai de volta pro valor da checklist
(com aviso).

Não faz git add/commit/push -- isso continua manual de propósito (ver
README.md), pra sempre ter uma revisão humana antes de publicar no
repositório público.
"""
from __future__ import annotations

import sys
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

from attendance_consultaja import build_attendance, find_latest
from config import DADOS_FONTE_DIR, INDEX_HTML_PATH, PIPELINE_DIR, XLSX_PATH
from render_index import upsert_last_update, upsert_pagas, upsert_raw
from transform_ocupacao import build_pagas, build_raw

# Desde a migração pro GitHub Actions (2026-09-21), o runner roda em UTC --
# sem fuso explícito, "última atualização" saía 3h atrasada (hora de
# Brasília não observa horário de verão desde 2019, sempre UTC-3).
FUSO_BR = ZoneInfo("America/Sao_Paulo")

LOG_PATH = PIPELINE_DIR / "atualizacoes.log"


def _log(lines: list[str]) -> None:
    text = "\n".join(lines) + "\n"
    print(text)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
        f.write(text)


def main() -> int:
    report: list[str] = []

    report.append("PASSO 1/2 -- ler a planilha de ocupação")
    if not XLSX_PATH.exists():
        report.append(
            f"  FALHOU: {XLSX_PATH.relative_to(PIPELINE_DIR.parent.parent)} não existe. "
            "Baixe checklist-captacao.xlsx do SharePoint (ver README.md > "
            "\"De onde vem o arquivo\") e salve nesse caminho antes de rodar de novo."
        )
        _log(report)
        return 1

    report.append("\nPASSO 2/2 -- recalcular RAW e Turmas Pagas")
    try:
        warnings: list[str] = []

        consultaja_path = find_latest(DADOS_FONTE_DIR)
        if consultaja_path is None:
            attendance = None
            report.append(
                '  Aviso: nenhuma planilha "Base_Consulta_Ja*.xlsx" encontrada em dados-fonte/ -- '
                '"Agendamentos" vai usar o valor da própria checklist-captacao, sem cruzar com a ConsultaJá.'
            )
        else:
            attendance = build_attendance(consultaja_path)
            report.append(f"  Cruzando Agendamentos com {consultaja_path.name} (pacientes agendados, exceto cancelados).")

        rows = build_raw(XLSX_PATH, warnings=warnings, attendance=attendance)
        upsert_raw(INDEX_HTML_PATH, rows)

        pagas = build_pagas(XLSX_PATH, warnings=warnings, attendance=attendance)
        upsert_pagas(INDEX_HTML_PATH, pagas)

        upsert_last_update(INDEX_HTML_PATH, f"{datetime.now(FUSO_BR):%d/%m/%Y %H:%M}")
    except Exception:
        report.append("  FALHOU: erro ao processar/gravar os dados. Detalhes:")
        report.append(traceback.format_exc())
        _log(report)
        return 1

    report.append(f"  OK -- {len(rows)} linhas de prática.")
    report.append(
        f"  OK -- Turmas Pagas: {sum(len(v) for v in pagas.values())} turmas em "
        f"{len(pagas)} mês(es) ({', '.join(sorted(pagas))})."
    )
    if warnings:
        report.append("  Avisos (revisar manualmente):")
        for w in warnings:
            report.append(f"    - {w}")

    report.append(
        "\nTudo certo. Próximos passos (revise antes de publicar):\n"
        "  git status\n"
        "  git diff -- index.html\n"
        "  git add index.html\n"
        '  git commit -m "Atualiza dados do dashboard"\n'
        "  git push"
    )
    _log(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
