# Pipeline de atualização de dados (Python)

Scripts para regenerar a constante `RAW` em `../index.html` (dashboard
"Acompanhamento Semanal de Práticas"), a partir da planilha
`checklist-captacao.xlsx`.

## De onde vem o arquivo

A planilha vive no SharePoint: site **PsMed-Documentos**, `Shared
Documents/General/11. Ocupação de agendas/checklist-captacao.xlsx`. Ao
contrário dos outros pipelines deste workspace (que buscam direto numa
API), **este passo é manual, por decisão consciente** (ver conversa de
2026-09-15) -- evita automatizar acesso a um sistema do SharePoint sem
passar pela TI. Pra atualizar:

1. Baixe `checklist-captacao.xlsx` do SharePoint (link acima).
2. Salve em `../../dados-fonte/checklist-captacao.xlsx` (pasta
   compartilhada com os outros pipelines deste workspace -- sempre
   sobrescreve a versão anterior, não leva data no nome).
3. Rode `python atualizar_tudo.py` (ou duplo clique em `Atualizar
   Dashboard.bat`, na raiz do projeto).

## Instalação

```
cd pipeline
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Uso

```
python atualizar_tudo.py
```

Não faz `git add`/`commit`/`push` -- isso continua manual de propósito,
pra sempre ter uma revisão antes de publicar no repositório público:

```
git status
git diff -- index.html
git add index.html
git commit -m "Atualiza dados do dashboard"
git push
```

## O que cada campo de `RAW` significa

Uma linha por combinação turma+data de prática:
`[turma, unidade, módulo, data, slots_previstos, overbooking, slots_totais, agendamentos]`.

- **`unidade`**: sigla (`CPS`, `SP`, `BSB`, `ONL`).
- **`slots_previstos`** / **`overbooking`** / **`slots_totais`**: capacidade
  planejada da prática (a taxa de ocupação, calculada no próprio
  `index.html`, não fica gravada aqui).
- **`agendamentos`**: quantidade de alunos agendados/atendidos nessa
  prática.

## Correção importante em relação ao upload manual (botão da página)

`index.html` também tem um botão "📂 Atualizar dados" que faz a mesma coisa
no navegador (`handleUpload()`, JavaScript). Esse código procura as
colunas da planilha pelos nomes **"Slots da prática"** e **"Slots
extras"** -- nomes que a planilha usava até Agosto. A partir de Setembro, a
planilha passou a usar **"Slots previstos"** e **"Overbooking previsto"**,
e o botão da página não reconhece os nomes novos: grava 0 nessas duas
colunas silenciosamente pra qualquer aba com o nome novo (`slots_totais` e
`agendamentos` continuam corretos, por coincidência de nome).

Este pipeline (`transform_ocupacao.py: ALIASES`) aceita os dois conjuntos
de nomes, então processa todas as abas corretamente. Se alguém for
continuar usando o botão de upload da página em vez deste pipeline, vale
levar essa mesma correção pro JS.

## O que o pipeline garante

- **Sem dado de aluno**: a planilha de origem já é agregada por
  turma/módulo/data -- não tem nome de aluno em nenhuma coluna lida aqui.
- **Regravação cirúrgica** (`render_index.py`): só a constante `RAW` (e o
  texto de "última atualização") são regravados -- o resto do arquivo
  (HTML, CSS, lógica de gráficos/filtros) não é tocado.
- **Sem automação não supervisionada**: nada aqui roda sozinho -- cada
  atualização depende de alguém baixar a planilha do SharePoint e rodar o
  script, por decisão.
