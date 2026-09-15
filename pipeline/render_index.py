"""Regrava a constante RAW dentro de ../index.html, preservando todo o
resto do arquivo (HTML, CSS, lógica de gráficos/filtros) intocado.

RAW pode estar em dois formatos, dependendo se este pipeline já rodou
antes: várias linhas (uma por registro, `const RAW = [` até uma linha só
com `];` -- formato original, feito por upload manual) ou uma linha só
(`const RAW = [...];` -- formato compacto que este pipeline grava, mesmo
padrão usado nos outros datasets deste workspace). upsert_raw() reconhece
os dois -- localiza a linha que começa com `const RAW = [` e, se ela já
terminar em `];` nessa mesma linha, é o formato compacto (substitui só
essa linha); senão, procura a linha seguinte que seja só `];` pra achar o
fim do bloco multi-linha.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_START_RE = re.compile(r"^const RAW = \[")
_END = "];"

_LAST_UPDATE_RE = re.compile(r'(<div id="last-update"[^>]*>)[^<]*(</div>)')


def upsert_raw(html_path: Path, rows: list[list]) -> None:
    # newline="" preserva o fim de linha original do arquivo (este index.html
    # usa CRLF, diferente dos outros deste workspace) -- sem isso o diff
    # mostraria o arquivo inteiro como alterado a cada execução.
    text = html_path.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)

    start = next((i for i, ln in enumerate(lines) if _START_RE.match(ln)), None)
    if start is None:
        raise RuntimeError(
            "Não encontrei a linha 'const RAW = [' no index.html -- abortando para não "
            "corromper o arquivo. Verifique manualmente antes de rodar de novo."
        )

    if lines[start].rstrip("\r\n").endswith(_END):
        end = start  # formato compacto: início e fim na mesma linha
    else:
        end = next(
            (i for i in range(start + 1, len(lines)) if lines[i].rstrip("\r\n") == _END), None
        )
        if end is None:
            raise RuntimeError(
                "Encontrei 'const RAW = [' mas não a linha de fechamento '];' correspondente -- "
                "abortando para não corromper o arquivo. Verifique manualmente antes de rodar de novo."
            )

    new_line = f"const RAW = {json.dumps(rows, ensure_ascii=False)};{nl}"
    lines[start:end + 1] = [new_line]

    html_path.write_text("".join(lines), encoding="utf-8", newline="")


def upsert_last_update(html_path: Path, label: str) -> None:
    """Atualiza o texto do card '<div id="last-update">' -- mesmo campo que
    handleUpload() atualiza no navegador ao processar uma planilha nova."""
    text = html_path.read_text(encoding="utf-8", newline="")
    new_text, n = _LAST_UPDATE_RE.subn(rf"\g<1>{label}\g<2>", text, count=1)
    if n == 0:
        raise RuntimeError('Não encontrei \'<div id="last-update">\' no index.html.')
    html_path.write_text(new_text, encoding="utf-8", newline="")
