#Requires -Version 5.1
<#
漫镜工场 ManJu Studio · 一键部署脚本
======================================
在全新 Windows 电脑上一键完成：
  1. 检查运行环境（Python / Node.js / npm）
  2. 创建 Python 虚拟环境 + 安装后端依赖
  3. 安装前端依赖 + 构建前端
  4. 生成 .env 配置文件（首次部署）
  5. 初始化数据库
  6. 可选：启动平台

用法：
  右键 → "使用 PowerShell 运行"  （推荐，图形界面）
  或在终端执行：
    powershell -ExecutionPolicy Bypass -File deploy.ps1              # 完整部署
    powershell -ExecutionPolicy Bypass -File deploy.ps1 -SkipStart   # 部署完不启动
    powershell -ExecutionPolicy Bypass -File deploy.ps1 -CheckOnly   # 仅检查环境

参数：
  -SkipStart    部署完成后不自动启动平台
  -CheckOnly    仅检查环境依赖，不执行部署
  -PythonExe   指定 Python 路径（默认自动检测 python / py）
  -NodeExe     指定 Node.js 路径（默认自动检测 node）
#>
param(
    [switch]$SkipStart,
    [switch]$CheckOnly,
    [string]$PythonExe = "",
    [string]$NodeExe = ""
)

$ErrorActionPreference = "Stop"
$RootDir = $PSScriptRoot
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$VenvDir = Join-Path $BackendDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

# ============ 工具函数 ============
function Write-Step($msg) {
    Write-Host ""
    Write-Host "──[ $msg ]" -ForegroundColor Cyan
}
function Write-OK($msg) {
    Write-Host "  ✓ $msg" -ForegroundColor Green
}
function Write-Warn($msg) {
    Write-Host "  ⚠ $msg" -ForegroundColor Yellow
}
function Write-Err($msg) {
    Write-Host "  ✗ $msg" -ForegroundColor Red
}
function Write-Info($msg) {
    Write-Host "  · $msg" -ForegroundColor DarkGray
}

# ============ 环境检查 ============
function Test-Command($name, $hint) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) {
        $ver = & $name --version 2>&1 | Select-Object -First 1
        Write-OK "$name $ver"
        return $cmd.Source
    }
    Write-Err "$name 未安装 — $hint"
    return $null
}

Write-Host ""
Write-Host "══════════════════════════════════════════" -ForegroundColor Magenta
Write-Host "  漫镜工场 ManJu Studio · 一键部署" -ForegroundColor Magenta
Write-Host "══════════════════════════════════════════" -ForegroundColor Magenta

# ── 1. 检查环境 ──
Write-Step "步骤 1/6 · 检查运行环境"

# Python
$pyPath = if ($PythonExe) { $PythonExe } else { (Get-Command python -ErrorAction SilentlyContinue).Source }
if (-not $pyPath) {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        $pyPath = "py"
        $ver = & py --version 2>&1
        Write-OK "Python $ver（via py launcher）"
    }
}
if (-not $pyPath) {
    Write-Err "Python 未安装"
    Write-Info "请安装 Python 3.10+：https://www.python.org/downloads/"
    Write-Info "安装时务必勾选 'Add Python to PATH'"
    exit 1
} elseif (-not $PythonExe -and $pyPath -ne "py") {
    $ver = & python --version 2>&1
    Write-OK "Python $ver"
}

# 检查 Python 版本 ≥ 3.10
try {
    if ($pyPath -eq "py") {
        $pyVer = (& py -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1).ToString()
    } else {
        $pyVer = (& $pyPath -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1).ToString()
    }
    $verParts = $pyVer.Split('.')
    $major = [int]$verParts[0]; $minor = [int]$verParts[1]
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
        Write-Err "Python 版本过低（$pyVer），需要 3.10+"
        exit 1
    }
    Write-Info "Python 版本 $pyVer ≥ 3.10 ✓"
} catch {
    Write-Warn "无法检测 Python 版本，继续部署..."
}

# Node.js
$nodePath = if ($NodeExe) { $NodeExe } else { (Get-Command node -ErrorAction SilentlyContinue).Source }
if (-not $nodePath) {
    Write-Err "Node.js 未安装"
    Write-Info "请安装 Node.js 18+（推荐 LTS）：https://nodejs.org/"
    exit 1
}
$nodeVer = (& $nodePath --version 2>&1).ToString()
Write-OK "Node.js $nodeVer"

# 检查 Node 版本 ≥ 18（Next.js 14 要求）
try {
    $nodeMajor = [int]($nodeVer.TrimStart('v').Split('.')[0])
    if ($nodeMajor -lt 18) {
        Write-Err "Node.js 版本过低（$nodeVer），需要 18+"
        Write-Info "请安装 Node.js 18+（推荐 LTS）：https://nodejs.org/"
        exit 1
    }
    Write-Info "Node 版本 $nodeVer ≥ 18 ✓"
} catch {
    Write-Warn "无法解析 Node 版本，继续部署..."
}

# npm
$npmPath = (Get-Command npm -ErrorAction SilentlyContinue).Source
if (-not $npmPath) {
    Write-Err "npm 未安装（通常随 Node.js 一起安装）"
    exit 1
}
$npmVer = & npm --version 2>&1
Write-OK "npm $npmVer"

if ($CheckOnly) {
    Write-Host ""
    Write-Host "环境检查完成（-CheckOnly 模式，跳过部署）" -ForegroundColor Green
    exit 0
}

# ── 2. Python 虚拟环境 + 后端依赖 ──
Write-Step "步骤 2/6 · 配置 Python 虚拟环境 + 安装后端依赖"

if (-not (Test-Path $VenvPython)) {
    Write-Info "创建虚拟环境 .venv ..."
    if ($pyPath -eq "py") {
        & py -m venv $VenvDir
    } else {
        & $pyPath -m venv $VenvDir
    }
    if (-not (Test-Path $VenvPython)) {
        Write-Err "虚拟环境创建失败"
        exit 1
    }
    Write-OK "虚拟环境已创建"
} else {
    Write-OK "虚拟环境已存在，跳过创建"
}

Write-Info "安装后端依赖..."
& $VenvPython -m pip install --upgrade pip -q
$installResult = & $VenvPython -m pip install -r (Join-Path $BackendDir "requirements.txt") 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Err "后端依赖安装失败"
    Write-Info $installResult
    exit 1
}
Write-OK "后端依赖安装完成"

# ── 3. 前端依赖 ──
Write-Step "步骤 3/6 · 安装前端依赖"

$nodeModules = Join-Path $FrontendDir "node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Info "安装前端依赖（首次较慢，约 1-3 分钟）..."
    Push-Location $FrontendDir
    npm install 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Err "前端依赖安装失败"
        Pop-Location
        exit 1
    }
    Pop-Location
    Write-OK "前端依赖安装完成"
} else {
    Write-OK "前端依赖已存在，跳过安装"
}

# ── 4. 生成 .env 配置 ──
Write-Step "步骤 4/6 · 生成配置文件"

$envFile = Join-Path $BackendDir ".env"
$envExample = Join-Path $BackendDir ".env.example"
if (-not (Test-Path $envFile)) {
    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
        Write-OK "已从 .env.example 生成 backend/.env"
        Write-Warn "当前为 MOCK_MODE=true（模拟模式），可体验全流程"
        Write-Info "切换真实 AI：编辑 backend/.env，设 MOCK_MODE=false 并填写 API Key"
    } else {
        Write-Err ".env.example 不存在，无法生成配置"
        exit 1
    }
} else {
    Write-OK "backend/.env 已存在，跳过生成"
}

# 前端 .env.local
$feEnvFile = Join-Path $FrontendDir ".env.local"
if (-not (Test-Path $feEnvFile)) {
    $feEnvExample = Join-Path $FrontendDir ".env.local.example"
    if (Test-Path $feEnvExample) {
        Copy-Item $feEnvExample $feEnvFile
        Write-OK "已生成 frontend/.env.local"
    }
} else {
    Write-OK "frontend/.env.local 已存在"
}

# ── 5. 初始化数据库 ──
Write-Step "步骤 5/6 · 初始化数据库"

Write-Info "启动后端以自动建表..."
# 调用独立的初始化脚本（避免 PowerShell here-string 引号冲突）
$dbResult = & $VenvPython (Join-Path $BackendDir "init_db.py") 2>&1
if ($dbResult -match "DB_OK") {
    Write-OK "数据库已初始化（SQLite）"
} else {
    Write-Warn "数据库初始化可能有警告（通常无碍）"
    Write-Info $dbResult
}

# ── 6. 完成 ──
Write-Step "部署完成"

Write-Host ""
Write-Host "  ┌─────────────────────────────────────────┐" -ForegroundColor Green
Write-Host "  │  ✓ 漫镜工场部署完成！                    │" -ForegroundColor Green
Write-Host "  └─────────────────────────────────────────┘" -ForegroundColor Green
Write-Host ""
Write-Info "后端 API：  http://localhost:8000  （文档 /docs）"
Write-Info "前端工作台：http://localhost:3000"
Write-Info "配置文件：  backend/.env（修改 AI Key / 模式开关）"
Write-Host ""

if ($SkipStart) {
    Write-Host "  -SkipStart 已指定，不自动启动。" -ForegroundColor DarkGray
    Write-Host "  手动启动：双击 start_manju.bat" -ForegroundColor DarkGray
    exit 0
}

# 询问是否启动
$startChoice = Read-Host "是否立即启动平台？(Y/n)"
if ($startChoice -eq "n" -or $startChoice -eq "N") {
    Write-Host "  部署完成。双击 start_manju.bat 即可启动。" -ForegroundColor Cyan
    exit 0
}

Write-Host ""
Write-Host "  正在启动平台..." -ForegroundColor Cyan
Write-Host "  （浏览器将自动打开 http://localhost:3000）" -ForegroundColor DarkGray
Write-Host ""

# 调用现有启动器（UI 模式）
$launcher = Join-Path $RootDir "start_manju.ps1"
if (Test-Path $launcher) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $launcher -Command ui
} else {
    # 回退：分别启动后端和前端
    Write-Warn "启动器不存在，手动启动后端和前端..."
    Start-Process -FilePath $VenvPython -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "8000" -WorkingDirectory $BackendDir -WindowStyle Hidden
    Start-Sleep -Seconds 3
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run dev" -WorkingDirectory $FrontendDir -WindowStyle Hidden
    Start-Sleep -Seconds 5
    Start-Process "http://localhost:3000"
}
