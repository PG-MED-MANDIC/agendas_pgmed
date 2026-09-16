"""Regrava as constantes RAW e PAGAS_DATA dentro de ../index.html,
preservando todo o resto do arquivo (HTML, CSS, lógica de gráficos/
filtros) intocado.

Cada constante pode estar em dois formatos, dependendo se este pipeline já
rodou antes para ela: várias linhas (uma por registro, `const NOME = [`
até uma linha só com `];` -- formato original, feito por upload manual/
edição manual) ou uma linha só (`const NOME = ...;` -- formato compacto
que este pipeline grava, mesmo padrão usado nos outros datasets deste
workspace). _upsert_const() reconhece os dois -- localiza a linha que
começa com `const NOME = ` e, se ela já terminar em fechamento nessa mesma
linha, é o formato compacto (substitui só essa linha); senão, procura a
linha seguinte que seja só `];` ou `};` pra achar o fim do bloco
multi-linha.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_LAST_UPDATE_RE = re.compile(r'(<div id="last-update"[^>]*>)[^<]*(</div>)')


def _upsert_const(html_path: Path, const_name: str, value, closer: str) -> None:
    # newline="" preserva o fim de linha original do arquivo (este index.html
    # usa CRLF, diferente dos outros deste workspace) -- sem isso o diff
    # mostraria o arquivo inteiro como alterado a cada execução.
    text = html_path.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)

    start_re = re.compile(r"^const " + re.escape(const_name) + r" = ")
    start = next((i for i, ln in enumerate(lines) if start_re.match(ln)), None)
    if start is None:
        raise RuntimeError(
            f"Não encontrei a linha 'const {const_name} = ' no index.html -- abortando para não "
            "corromper o arquivo. Verifique manualmente antes de rodar de novo."
        )

    if lines[start].rstrip("\r\n").endswith(closer):
        end = start  # formato compacto: início e fim na mesma linha
    else:
        end = next(
            (i for i in range(start + 1, len(lines)) if lines[i].rstrip("\r\n") == closer), None
        )
        if end is None:
            raise RuntimeError(
                f"Encontrei 'const {const_name} = ' mas não a linha de fechamento '{closer}' "
                "correspondente -- abortando para não corromper o arquivo. Verifique manualmente "
                "antes de rodar de novo."
            )

    new_line = f"const {const_name} = {json.dumps(value, ensure_ascii=False)};{nl}"
    lines[start:end + 1] = [new_line]

    html_path.write_text("".join(lines), encoding="utf-8", newline="")


def upsert_raw(html_path: Path, rows: list[list]) -> None:
    _upsert_const(html_path, "RAW", rows, "];")


def upsert_pagas(html_path: Path, data: dict[str, list[dict]]) -> None:
    """Regrava PAGAS_DATA (turmas pagas agregadas por mês, ver
    transform_ocupacao.build_pagas). O JS de index.html lê PAGAS_DATA e
    escolhe o mês atual via dropdown -- ver initMesPagasDropdown()."""
    _upsert_const(html_path, "PAGAS_DATA", data, "};")


def upsert_last_update(html_path: Path, label: str) -> None:
    """Atualiza o texto do card '<div id="last-update">' -- mesmo campo que
    handleUpload() atualiza no navegador ao processar uma planilha nova."""
    text = html_path.read_text(encoding="utf-8", newline="")
    new_text, n = _LAST_UPDATE_RE.subn(rf"\g<1>{label}\g<2>", text, count=1)
    if n == 0:
        raise RuntimeError('Não encontrei \'<div id="last-update">\' no index.html.')
    html_path.write_text(new_text, encoding="utf-8", newline="")
