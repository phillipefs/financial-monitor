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

param(
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$source = [System.IO.Path]::GetFullPath((Join-Path $repoRoot '.agents\skills'))
$codexDest = [System.IO.Path]::GetFullPath((Join-Path $repoRoot '.codex\skills'))
$claudeDest = [System.IO.Path]::GetFullPath((Join-Path $repoRoot '.claude\skills'))

function Assert-ExactRepoPath {
    param(
        [string]$Actual,
        [string]$ExpectedRelative,
        [string]$Label
    )

    $expected = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $ExpectedRelative))
    $actualNorm = $Actual.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    $expectedNorm = $expected.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)

    if (-not [string]::Equals($actualNorm, $expectedNorm, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Label resolveu para caminho inesperado: $Actual (esperado: $expected)"
    }
}

Assert-ExactRepoPath -Actual $source -ExpectedRelative '.agents\skills' -Label 'Fonte'
Assert-ExactRepoPath -Actual $codexDest -ExpectedRelative '.codex\skills' -Label 'Destino Codex'
Assert-ExactRepoPath -Actual $claudeDest -ExpectedRelative '.claude\skills' -Label 'Destino Claude'

if (
    [string]::Equals($source, $codexDest, [System.StringComparison]::OrdinalIgnoreCase) -or
    [string]::Equals($source, $claudeDest, [System.StringComparison]::OrdinalIgnoreCase) -or
    [string]::Equals($codexDest, $claudeDest, [System.StringComparison]::OrdinalIgnoreCase)
) {
    throw 'Fonte e destinos de sync precisam ser caminhos distintos.'
}

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
    if ($DryRun) {
        $args += '/L'
    }
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

if ($DryRun) {
    Write-Host 'Dry run ativo: nenhuma alteracao sera feita.'
}

Write-Host "Sincronizando $source -> $codexDest"
Invoke-RobocopyMirror -Src $source -Dst $codexDest

Write-Host "Sincronizando $source -> $claudeDest (sem pastas 'agents/', metadado especifico do Codex)"
Invoke-RobocopyMirror -Src $source -Dst $claudeDest -ExcludeDirs @('agents')

Write-Host 'Sync concluido.'
