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
|-- finance_stocks.py                 # Ativos, calculo de RSI e sinais
|-- onchain.py                        # Coleta e classificacao MVRV BTC/ETH
|-- generate_dashboard.py             # Gera dashboard.html
|-- dashboard.html                    # Saida gerada localmente
|-- requirements.txt                  # Dependencias Python
`-- .github/workflows/update-dashboard.yml
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
4. copia de `dashboard.html` para `_site/index.html`;
5. publicacao no GitHub Pages.

Agenda configurada:

```yaml
cron: "0 15 * * *"
```

O cron do GitHub usa UTC. Essa configuracao roda diariamente as 15:00 UTC, equivalente a 12:00 em Brasilia/Sao Paulo quando o fuso esta em UTC-3.

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

## Fontes de Dados

- Yahoo Finance via `yfinance`
- CoinMetrics Community API

## Observacoes

Este projeto e uma ferramenta pessoal de monitoramento e pesquisa. Ele nao constitui recomendacao financeira. Os dados dependem da disponibilidade das APIs externas e podem falhar temporariamente por rede, rate limit ou indisponibilidade dos provedores.
