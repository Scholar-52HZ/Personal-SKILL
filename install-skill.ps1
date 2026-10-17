<#
.SYNOPSIS
    Personal-SKILL Installer Script
.DESCRIPTION
    Installs or synchronizes a skill from this repository to Antigravity global config or a target workspace.
.EXAMPLE
    .\install-skill.ps1 -List
    .\install-skill.ps1 -Skill agent-handoff-workflow
    .\install-skill.ps1 -Skill agent-handoff-workflow -ProjectPath "E:\DevelopProject\MyProject"
#>

param (
    [string]$Skill,
    [string]$ProjectPath,
    [switch]$List,
    [switch]$Help
)

$RepoRoot = $PSScriptRoot
$SkillsDir = Join-Path $RepoRoot "skills"

if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path -Full
    exit 0
}

# List available skills
if ($List -or [string]::IsNullOrWhiteSpace($Skill)) {
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "       Personal-SKILL Available Skills    " -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    
    if (Test-Path $SkillsDir) {
        $availableSkills = Get-ChildItem -Path $SkillsDir -Directory
        if ($availableSkills.Count -eq 0) {
            Write-Host "No skills found under skills/ directory." -ForegroundColor Yellow
        } else {
            foreach ($s in $availableSkills) {
                $skillMd = Join-Path $s.FullName "SKILL.md"
                $version = "unknown"
                if (Test-Path $skillMd) {
                    $content = Get-Content $skillMd -Raw -Encoding UTF8
                    if ($content -match 'version:\s*"([^"]+)"') {
                        $version = $matches[1]
                    }
                }
                Write-Host " - $($s.Name) (v$version)" -ForegroundColor Green
            }
        }
    } else {
        Write-Host "Skills directory not found!" -ForegroundColor Red
    }
    Write-Host "`nUsage: .\install-skill.ps1 -Skill agent-handoff-workflow" -ForegroundColor Gray
    exit 0
}

$SourceSkillPath = Join-Path $SkillsDir $Skill

if (-not (Test-Path $SourceSkillPath)) {
    Write-Host "[ERROR] Skill not found: $Skill ($SourceSkillPath)" -ForegroundColor Red
    exit 1
}

if ([string]::IsNullOrWhiteSpace($ProjectPath)) {
    # Default: Global Antigravity config
    $GlobalSkillsDir = Join-Path $HOME ".gemini\config\skills"
    $DestSkillPath = Join-Path $GlobalSkillsDir $Skill
    
    if (-not (Test-Path $GlobalSkillsDir)) {
        New-Item -ItemType Directory -Path $GlobalSkillsDir -Force | Out-Null
    }
    
    Write-Host "[INSTALL] Installing '$Skill' to global directory: $DestSkillPath ..." -ForegroundColor Cyan
    Copy-Item -Path $SourceSkillPath -Destination $GlobalSkillsDir -Recurse -Force
    Write-Host "[SUCCESS] Successfully installed '$Skill' globally! Accessible in any workspace." -ForegroundColor Green
} else {
    # Target: Project workspace
    $WorkspaceSkillsDir = Join-Path $ProjectPath ".gemini\skills"
    $DestSkillPath = Join-Path $WorkspaceSkillsDir $Skill
    
    if (-not (Test-Path $WorkspaceSkillsDir)) {
        New-Item -ItemType Directory -Path $WorkspaceSkillsDir -Force | Out-Null
    }
    
    Write-Host "[INSTALL] Installing '$Skill' to workspace: $DestSkillPath ..." -ForegroundColor Cyan
    Copy-Item -Path $SourceSkillPath -Destination $WorkspaceSkillsDir -Recurse -Force
    Write-Host "[SUCCESS] Successfully installed '$Skill' to workspace: $WorkspaceSkillsDir" -ForegroundColor Green
}