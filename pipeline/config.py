"""Configuração do pipeline: caminhos.

Diferente dos outros pipelines deste workspace, este não chama nenhuma API
-- a planilha de origem (checklist-captacao.xlsx) vive no SharePoint
(site PsMed-Documentos / Shared Documents / General / 11. Ocupação de
agendas/) e é baixada manualmente (decisão consciente, ver
pipeline/README.md > "De onde vem o arquivo"). Este pipeline só processa o
arquivo já local, em dados-fonte/.

DADOS_FONTE_DIR aponta pra fora deste repositório, pra dados-fonte/ na raiz
do workspace (pasta NPS-PACIENTE, que contém este repositório como
subpasta) -- é a MESMA pasta compartilhada usada pelos outros pipelines
(ver CONTEXTO-GITHUB.md na raiz do workspace). Só funciona com essa
disposição de pastas -- se este repositório for movido pra fora de
NPS-PACIENTE, ajuste este caminho.
"""
from __future__ import annotations

from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PIPELINE_DIR.parent
INDEX_HTML_PATH = PROJECT_DIR / "index.html"
DADOS_FONTE_DIR = PROJECT_DIR.parent / "dados-fonte"

# Nome fixo -- ao contrário das planilhas baixadas por API (que levam a
# data no nome), este arquivo é mantido manualmente no SharePoint e cada
# nova versão baixada substitui a anterior.
XLSX_FILENAME = "checklist-captacao.xlsx"
XLSX_PATH = DADOS_FONTE_DIR / XLSX_FILENAME
