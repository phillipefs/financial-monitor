# Financial Monitor

Dashboard estatico para acompanhar sinais de mercado com RSI semanal/mensal e indicadores on-chain de BTC/ETH.

O projeto foi desenhado para rodar sem servidor: um script Python coleta os dados, gera `dashboard.html` e um workflow do GitHub Actions publica o resultado no GitHub Pages em uma agenda diaria.

## Visao Geral

O monitor combina tres blocos principais:

- RSI de ativos globais, criptomoedas, acoes dos EUA, acoes brasileiras e cambio.
- Classificacao de sinais em `UltraBuy`, `Buy`, `Neutral` e `Sell`.
- MVRV on-chain para BTC e ETH usando dados da CoinMetrics.

O arquivo final e um HTML estatico, pronto para abrir no navegador ou publicar no GitHub Pages.

## Estrutura

```text
.
|-- .agents/skills/                   # Fonte unica das skills compartilhadas
|-- .codex/skills/                    # Copia sincronizada para Codex
|-- .claude/skills/                   # Copia sincronizada para Claude Code
|-- .github/workflows/update-dashboard.yml
|-- scripts/sync-skills.ps1           # Sincroniza skills entre ferramentas
|-- AGENTS.md                         # Instrucoes do projeto para Codex
|-- CLAUDE.md                         # Instrucoes do projeto para Claude Code
|-- finance_stocks.py                 # Ativos, calculo de RSI e sinais
|-- onchain.py                        # Coleta e classificacao MVRV BTC/ETH
|-- generate_dashboard.py             # Gera dashboard.html
|-- dashboard.html                    # Saida gerada localmente
|-- requirements.txt                  # Dependencias Python
|-- snapshot_history.json             # Historico versionado de KPIs
`-- signal_history.json               # Historico versionado de sinais
```

## Requisitos

- Python 3.11+
- Acesso de rede ao Yahoo Finance e CoinMetrics

Instale as dependencias:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Uso Local

Gere o dashboard:

```bash
python generate_dashboard.py
```

Por padrao, a execucao local le os historicos versionados, mas nao grava
`snapshot_history.json` nem `signal_history.json`. Isso evita conflito com os
commits automaticos do GitHub Actions. Para gravar historicos localmente:

```bash
FM_PERSIST_HISTORY=1 python generate_dashboard.py
```

Abra o arquivo gerado:

```text
dashboard.html
```

Os scripts auxiliares tambem podem ser executados separadamente:

```bash
python finance_stocks.py
python onchain.py
```

## GitHub Pages

O workflow em `.github/workflows/update-dashboard.yml` executa:

1. checkout do repositorio;
2. instalacao do Python e dependencias;
3. execucao de `generate_dashboard.py`;
4. commit de `snapshot_history.json` e `signal_history.json` quando houver mudanca;
5. copia de `dashboard.html` para `_site/index.html` e `_site/dashboard.html`;
6. publicacao no GitHub Pages.

Agenda configurada no GitHub Actions:

```yaml
- cron: "7 11 * * 1-5"  # seg-sex 08:07 BRT
- cron: "7 15 * * 1-5"  # seg-sex 12:07 BRT
- cron: "7 18 * * 1-5"  # seg-sex 15:07 BRT
- cron: "7 21 * * 1-5"  # seg-sex 18:07 BRT
- cron: "7 11 * * 6,0"  # sab-dom 08:07 BRT
```

O cron do GitHub usa UTC. Os minutos foram deslocados para `:07` para reduzir congestionamento no topo da hora.

Para ativar a publicacao:

1. No GitHub, abra `Settings`.
2. Va em `Pages`.
3. Em `Build and deployment`, selecione `GitHub Actions` como source.
4. Rode o workflow manualmente em `Actions > Update dashboard > Run workflow`.

Depois do primeiro deploy, o site ficara disponivel na URL do GitHub Pages do repositorio.

## Configuracao de Cache

O `yfinance` usa cache local para timezone/cookies. O projeto nao grava esse cache no repositorio.

Por padrao:

- no GitHub Actions, usa `RUNNER_TEMP`;
- localmente, usa a pasta temporaria do sistema;
- se necessario, defina `YFINANCE_CACHE_DIR`.

Exemplo:

```bash
YFINANCE_CACHE_DIR=/tmp/yfinance-cache python generate_dashboard.py
```

## Codex e Claude Code

O projeto usa uma estrutura de skills compartilhadas para evitar duplicacao entre Codex e Claude Code:

- `.agents/skills/` e a fonte oficial.
- `.codex/skills/` e a copia lida pelo Codex.
- `.claude/skills/` e a copia lida pelo Claude Code.
- `AGENTS.md` guarda instrucoes do projeto para Codex.
- `CLAUDE.md` guarda instrucoes equivalentes para Claude Code.

Edite skills somente em `.agents/skills/`. Depois, sincronize:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\sync-skills.ps1
```

Para conferir o que seria sincronizado sem escrever arquivos:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\sync-skills.ps1 -DryRun
```

O script usa `robocopy /MIR` com validacao de caminhos para espelhar apenas `.codex/skills/` e `.claude/skills/`. O arquivo local `.claude/settings.local.json` fica fora do Git.

## Fontes de Dados

- Yahoo Finance via `yfinance`
- CoinMetrics Community API

## Observacoes

Este projeto e uma ferramenta pessoal de monitoramento e pesquisa. Ele nao constitui recomendacao financeira. Os dados dependem da disponibilidade das APIs externas e podem falhar temporariamente por rede, rate limit ou indisponibilidade dos provedores.
