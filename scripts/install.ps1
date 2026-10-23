[CmdletBinding(SupportsShouldProcess)]
param(
    [string[]]$Skills,
    [string]$Destination = (Join-Path $env:USERPROFILE ".codex\skills")
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$manifest = @(
    "academic-search",
    "ai-computing-research",
    "alpha-hypothesis-research",
    "android-phone-ops",
    "banner-design",
    "biomedical-evidence",
    "book-discovery",
    "brand",
    "brand-collateral",
    "context-budget",
    "data-report-deck",
    "deck-review",
    "design",
    "design-system",
    "evidence-driven-valuation",
    "evidence-research",
    "executive-decision-deck",
    "feishu-document-output",
    "financial-analyst",
    "find-media",
    "find-skills",
    "fundamental-signal-intake",
    "goutoujunshi",
    "hallmark",
    "handoff",
    "html-report",
    "humanizer-zh",
    "investment-research",
    "logo-design",
    "memory-curator",
    "pitch-deck",
    "presentation-studio",
    "research-presentation",
    "research-toolkit",
    "research-summarizer",
    "social-conversation-coach",
    "sre-command-delivery",
    "stock-analysis",
    "teaching-deck",
    "tech-mentor",
    "technical-explainer-deck",
    "ui-styling",
    "ui-ux-pro-max",
    "wechat-account-archive"
)

$selectedSkills = if ($Skills -and $Skills.Count -gt 0) { $Skills } else { $manifest }
$unknownSkills = @($selectedSkills | Where-Object { $_ -notin $manifest })

if ($unknownSkills.Count -gt 0) {
    throw "Unknown skills: $($unknownSkills -join ', '). Available skills: $($manifest -join ', ')"
}

$dependencies = @{
    "alpha-hypothesis-research" = @("research-toolkit")
    "book-discovery" = @("research-toolkit")
    "evidence-driven-valuation" = @("fundamental-signal-intake")
    "investment-research" = @("alpha-hypothesis-research", "fundamental-signal-intake", "evidence-driven-valuation", "stock-analysis", "research-toolkit")
}
$resolvedSkills = [System.Collections.Generic.List[string]]::new()
foreach ($skillName in $selectedSkills) {
    if (-not $resolvedSkills.Contains($skillName)) { $resolvedSkills.Add($skillName) }
}
for ($index = 0; $index -lt $resolvedSkills.Count; $index++) {
    foreach ($dependency in $dependencies[$resolvedSkills[$index]]) {
        if (-not $resolvedSkills.Contains($dependency)) { $resolvedSkills.Add($dependency) }
    }
}
$selectedSkills = @($resolvedSkills)

if ($PSCmdlet.ShouldProcess($Destination, "创建 Codex Skills 目录")) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
}

foreach ($skillName in $selectedSkills) {
    $sourcePath = Join-Path $repositoryRoot $skillName
    $targetPath = Join-Path $Destination $skillName

    if (-not (Test-Path -LiteralPath (Join-Path $sourcePath "SKILL.md"))) {
        throw "技能入口不存在：$sourcePath\SKILL.md"
    }

    if ($PSCmdlet.ShouldProcess($targetPath, "安装或更新 $skillName")) {
        Copy-Item -LiteralPath $sourcePath -Destination $Destination -Recurse -Force
    }
}

Write-Host "Processed $($selectedSkills.Count) skills. Available on your next turn; start a new chat if the skill list has not refreshed."
