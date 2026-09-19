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
- **`agendamentos`**: quantidade de pacientes que **ocupam o slot**
  (agendado, confirmado, compareceu, atendido ou faltou -- qualquer coisa
  exceto cancelado) nessa prática (ver "De onde vem o número de
  Agendamentos" abaixo).

## De onde vem o número de Agendamentos (decisão de 2026-09-17)

`agendamentos` não vem da coluna "Agendamentos" da própria
checklist-captacao (essa coluna é preenchida à mão). Em vez disso,
`attendance_consultaja.py` cruza cada turma+data com
`dados-fonte/Base_Consulta_Ja*.xlsx` (a mesma planilha usada pelos
pipelines de `agendas-pac-real` e da raiz do workspace -- **este pipeline
nunca a baixa**, só reaproveita a mais recente já presente na pasta
compartilhada) e conta quantos pacientes têm qualquer Status **diferente
de "Cancelado"** (Agendado, Confirmado, Compareceu, Atendido ou Faltou)
naquele curso+turma+unidade+data.

Isso já foi tentado de outro jeito (decisão de 2026-09-16, revertida):
contar só Status "Compareceu"/"Atendido" (comparecimento real). O
problema é que esse dashboard compara **capacidade** (slots previstos)
com **demanda** (quantos pacientes ocupam a turma) pra qualquer semana,
inclusive futuras -- e uma data que ainda não aconteceu nunca tem
"Compareceu"/"Atendido", então a ocupação de toda semana futura ficava
zerada mesmo com pacientes já marcados. Contar por "não foi cancelado"
resolve isso sem precisar de nenhuma lógica de "hoje": um paciente que
faltou ainda ocupou o slot no momento em que agendou, só o cancelamento
libera a vaga.

O casamento funciona porque o nome da turma na checklist já é
"`<curso> <sigla da unidade> T<número>`" (ex.: `Dermatologia Cirurgica SP
T01`), e a ConsultaJá guarda essas 3 partes em colunas separadas (Curso/
Unidade/Turma) -- `attendance_consultaja.parse_turma()` separa um do
outro. **`slots_previstos` continua vindo só da checklist-captacao** (a
ConsultaJá não tem capacidade planejada, só agendamentos individuais).

Se uma turma da checklist não bate com nenhuma combinação curso+unidade+
turma da ConsultaJá (nome digitado diferente, turma nova ainda não
cadastrada lá, etc.), o pipeline **mantém o valor antigo da checklist**
pra essa turma e avisa no relatório -- nunca zera silenciosamente. Se a
planilha da ConsultaJá não for encontrada em `dados-fonte/`, o pipeline
inteiro cai de volta pro comportamento antigo (valor da checklist), com
aviso.

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

O botão da página também **não** cruza com a ConsultaJá (ver seção acima)
-- `agendamentos`, se gerado por ele, continua sendo o valor bruto da
coluna "Agendamentos" da checklist-captacao, não o comparecimento real.

## Turmas Pagas

A aba "💰 Turmas Pagas" do dashboard lê a constante `PAGAS_DATA`
(`transform_ocupacao.build_pagas` + `render_index.upsert_pagas`),
regravada a cada execução deste pipeline junto com `RAW`. Ela agrega, por
turma e por mês, as práticas marcadas como pagas na planilha (coluna
**"É paga?"** = "Sim"), somando slots/agendamentos e a coluna **"Valor
total"** de cada linha. O dropdown "Competência" na página escolhe qual
mês de `PAGAS_DATA` exibir (por padrão, o mais recente com dado).

Como a planilha teve cabeçalhos corrompidos em algumas abas (célula da
coluna "Valor total" virou um número solto ou ficou vazia -- visto em
Jul./Ago./Mai./Jun.), `_find_pagas_cols()` cai pro fallback posicional
(coluna logo após "É paga?") nesses casos, com aviso no relatório.

## O que o pipeline garante

- **Sem dado de aluno**: a planilha de origem já é agregada por
  turma/módulo/data -- não tem nome de aluno em nenhuma coluna lida aqui.
- **Regravação cirúrgica** (`render_index.py`): só a constante `RAW` (e o
  texto de "última atualização") são regravados -- o resto do arquivo
  (HTML, CSS, lógica de gráficos/filtros) não é tocado.
- **Download da planilha continua manual**: baixar `checklist-captacao.xlsx`
  do SharePoint continua depender de alguém, por decisão de 2026-09-15 (evita
  automatizar acesso a um sistema do SharePoint sem passar pela TI) -- isso
  não mudou.
- **Execução do script deixou de ser só manual (2026-09-18)**: a rotina
  `atualizar_diario_n8n.py` (raiz do workspace) roda este pipeline sozinha
  todo dia às 06:00 via n8n, usando a planilha que já estiver em
  `dados-fonte/` -- decisão consciente do usuário, que substituiu a regra
  anterior de "nada roda sozinho" só pra este passo. Se a planilha estiver
  desatualizada, a rotina só *avisa* (checa a idade do arquivo), nunca baixa
  nem toca no SharePoint.
