<#
.SYNOPSIS
    Sincroniza .agents/skills/ (fonte unica) para .codex/skills/ e .claude/skills/.

.DESCRIPTION
    Edite skills somente em .agents/skills/. Rode este script depois de qualquer
    alteracao. .codex/skills/ e .claude/skills/ sao saida gerada - nao edite
    diretamente, o proximo sync sobrescreve.

    Usa robocopy /MIR (espelha o destino, apagando o que nao existe mais na
    fonte). Os caminhos sao fixos e resolvidos a partir da localizacao deste
    script (nao aceitam entrada externa), entao /MIR nao corre risco de
    apagar algo fora de .codex/skills ou .claude/skills.

    A pasta agents/openai.yaml dentro de cada skill e um metadado especifico
    do Codex (nome de exibicao, prompt padrao). E copiada para .codex/skills
    mas excluida da copia para .claude/skills, que a ignoraria mesmo assim -
    isso so mantem a pasta do Claude mais limpa.
#>

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $repoRoot '.agents\skills'
$codexDest = Join-Path $repoRoot '.codex\skills'
$claudeDest = Join-Path $repoRoot '.claude\skills'

if (-not (Test-Path $source)) {
    throw "Fonte nao encontrada: $source"
}

function Invoke-RobocopyMirror {
    param(
        [string]$Src,
        [string]$Dst,
        [string[]]$ExcludeDirs = @()
    )

    $args = @($Src, $Dst, '/MIR', '/NFL', '/NDL', '/NJH', '/NJS')
    if ($ExcludeDirs.Count -gt 0) {
        $args += '/XD'
        $args += $ExcludeDirs
    }

    robocopy @args | Out-Null
    # Robocopy exit codes 0-7 sao sucesso (bitmask de "arquivos copiados/pulados/etc").
    # 8 ou mais indica falha real.
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy falhou (exit code $LASTEXITCODE) copiando $Src -> $Dst"
    }
}

Write-Host "Sincronizando $source -> $codexDest"
Invoke-RobocopyMirror -Src $source -Dst $codexDest

Write-Host "Sincronizando $source -> $claudeDest (sem pastas 'agents/', metadado especifico do Codex)"
Invoke-RobocopyMirror -Src $source -Dst $claudeDest -ExcludeDirs @('agents')

Write-Host 'Sync concluido.'
