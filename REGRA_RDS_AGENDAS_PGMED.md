# agendas_pgmed lendo o RDS do Raul (desde 24/11/2026)

Antes: slots so da planilha `checklist-captacao.xlsx`. Agora: de 01/09/2026 ate a ultima data da planilha (19/12/2026 em nov/26),
slots do RDS (`dados-fonte/checklist_real.json`), com as regras temporarias de Campinas e Brasilia (a partir de 23/11/2026) do
repo `agendas-pac-real` (`REGRA_TEMPORARIA_SLOTS_CAMPINAS.md` e `..._BRASILIA.md`). Antes de 01/09 segue a planilha.
"E paga?": todas, exceto "Pediatria" (regra de 29/09/2026 mantida; **pendencia**: usuario vai confirmar se Neuropediatria/Psicopediatria tambem).
Receita esperada = ticket medio x slots (recalculada nas praticas CPS/BSB com regra); valor agendado e a cobrar = RDS.

## Voltar ao original rapido
| Quero | Faco |
|---|---|
| Voltar a ler so a planilha | `pipeline/config.py`: `USAR_RDS = False`, commit/push e rodar o Actions |
| Desligar so as regras CPS/BSB (continua lendo o RDS puro) | `agendas-pac-real/pipeline/regras_slots_cps.json` e `regras_slots_bsb.json`: `"ativa": false` |
| Voltar o codigo todo como estava | tag `backup-antes-rds-agendas-pgmed-20261123` (`git revert` dos commits desta mudanca, ou `git checkout backup-antes-rds-agendas-pgmed-20261123 -- index.html index_responsivo.html pipeline/`) |
| Fazer valer | Actions do repo `automacao-dashboard`, grupo `agendas-pac-real,agendas_pgmed,coord_mandic_pgmed` (n8n `RDDWtJw1m7cuhuTn`, gatilho "Diario 11:00 BRT") |

## Aviso
Perto de 19/12/2026 o log traz um AVISO (a planilha termina e o dashboard so mostra datas ate la). Se o Raul ainda nao atualizou, decidir se estende ate mar/27.
Quando o Raul atualizar a view: desligar as regras temporarias e conferir.
