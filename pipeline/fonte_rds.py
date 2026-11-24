"""Fonte RDS (slots reais do Raul) para o agendas_pgmed -- mesma fonte do agendas-pac-real.

Antes, este dashboard lia so a planilha checklist-captacao.xlsx. Agora, para as
datas de 01/09/2026 ate a ultima data da planilha, a capacidade (slots) vem do
RDS (dados-fonte/checklist_real.json) COM as regras temporarias de Campinas e
Brasilia (agendas-pac-real/pipeline/regra_slots_cps.py e regra_slots_bsb.py, com
interruptor "ativa" nos .json). Datas antes do RDS ficam como a planilha.
Sem o json do RDS, tudo continua vindo da planilha (plano B).

Mapeamento: slots previstos = regulares; overbooking = buffer + extras (ConsultaJa);
slots totais = total do RDS (regulares + buffer + extras, ja com a regra
temporaria). Receita esperada = ticket medio x slots totais (como o RDS calcula),
recalculada quando a regra muda o total; valor agendado e a cobrar vem do RDS.

"E paga?" (decisao do usuario, 23/11/2026): TODAS pagas, exceto Neuropediatria
(vale para Out./Nov./Dez.; Set. e antes seguem as marcacoes da planilha).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from config import AGENDAS_PAC_REAL_PIPELINE_DIR
from transform_ocupacao import _norm, _resolve_agendamentos

MESES_PAGAS_RDS = ("10", "11", "12")  # meses em que "E paga?" nao vem preenchido na planilha


def _regras():
    p = str(AGENDAS_PAC_REAL_PIPELINE_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)
    from regra_slots_cps import aplicar as cps
    from regra_slots_bsb import aplicar as bsb
    return cps, bsb


def _dt(s: str) -> datetime:
    return datetime.strptime(s, "%d/%m/%Y")


def carregar_rds(json_path: Path, warnings: list[str]) -> dict[tuple[str, str], dict]:
    """(turma, 'dd/mm/YYYY') -> pratica do RDS ja com as regras temporarias."""
    dados = json.loads(Path(json_path).read_text(encoding="utf-8"))
    originais = dados.get("linhas", [])
    cps, bsb = _regras()
    novas = bsb(cps(originais, warnings), warnings)
    out: dict[tuple[str, str], dict] = {}
    for o, n in zip(originais, novas):
        data = datetime.strptime(str(o["data_pratica"])[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        total = int(n.get("total_real") or 0)
        buf = int(n.get("buf_reais") or 0)
        ext = int(n.get("extras_cj") or 0)
        ticket = o.get("ticket_medio")
        rec = int(o.get("receita_esperada") or 0)
        if total != int(o.get("total_real") or 0) and ticket:
            rec = round(float(ticket) * total)  # regra temporaria mudou o total
        out[(str(o["turma"]).strip(), data)] = {
            "turma": str(o["turma"]).strip(), "unidade": o["unidade"], "modulo": str(o.get("modulo") or "").strip(),
            "data": data, "sp": total - buf - ext, "se": buf + ext, "st": total,
            "receita_esperada": rec, "valor_agendado": int(o.get("receita_agendada") or 0),
            "a_cobrar": int(o.get("a_cobrar") or 0),
        }
    return out


def mesclar_raw(rows_xlsx: list[list], rds: dict, ini: datetime, attendance, warnings: list[str]) -> list[list]:
    """Troca, na janela [ini, ultima data da planilha], as linhas da planilha pelas do RDS."""
    fim = max(_dt(r[3]) for r in rows_xlsx)
    antigo_ag = {(r[0], r[3]): r[7] for r in rows_xlsx}
    mantidas = [r for r in rows_xlsx if _dt(r[3]) < ini]
    novas, warned = [], set()
    sem_rds = sum(1 for r in rows_xlsx if ini <= _dt(r[3]) <= fim and (r[0], r[3]) not in rds)
    for (turma, data), p in rds.items():
        if not (ini <= _dt(data) <= fim):
            continue
        ag = _resolve_agendamentos(antigo_ag.get((turma, data), 0), turma, data, attendance, warnings, warned)
        novas.append([turma, p["unidade"], p["modulo"], data, p["sp"], p["se"], p["st"], ag])
    warnings.append(
        f"RDS: {len(novas)} praticas do RDS (de {ini:%d/%m/%Y} a {fim:%d/%m/%Y}) no lugar das da planilha; "
        f"{len(mantidas)} da planilha antes do RDS; {sem_rds} linhas da planilha sem correspondente no RDS (descartadas)."
    )
    return mantidas + sorted(novas, key=lambda r: (_dt(r[3]), r[0]))


def pagas_rds(rds: dict, fim_planilha: datetime, attendance, warnings: list[str]) -> dict[str, list[dict]]:
    """Turmas pagas (Out./Nov./Dez.) a partir do RDS: todas, exceto Neuropediatria."""
    data: dict[str, dict[str, dict]] = {}
    warned: set[str] = set()
    for (turma, dstr), p in sorted(rds.items(), key=lambda kv: (_dt(kv[0][1]), kv[0][0])):
        d = _dt(dstr)
        mm = f"{d.month:02d}"
        if mm not in MESES_PAGAS_RDS or d.year != 2026 or d > fim_planilha:
            continue
        if _norm(turma).startswith("neuropediatria"):
            continue
        t = data.setdefault(mm, {}).setdefault(turma, {
            "turma": turma, "unidade": p["unidade"], "modulos": [], "sp": 0, "se": 0, "st": 0, "ag": 0, "n": 0,
            "valor": None, "valor60": None, "receita_esperada": 0, "valor_agendado": 0, "a_cobrar": 0})
        if p["modulo"] and p["modulo"] not in t["modulos"]:
            t["modulos"].append(p["modulo"])
        t["sp"] += p["sp"]
        t["se"] += p["se"]
        t["st"] += p["st"]
        t["ag"] += _resolve_agendamentos(0, turma, dstr, attendance, warnings, warned)
        t["n"] += 1
        t["receita_esperada"] += p["receita_esperada"]
        t["valor_agendado"] += p["valor_agendado"]
        t["a_cobrar"] += p["a_cobrar"]
    return {mm: list(v.values()) for mm, v in data.items()}
