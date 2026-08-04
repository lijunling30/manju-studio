#Requires -Version 5.1
<#
漫镜工场 ManJu Studio 一键启动器
================================
功能：
  1. 一键启动后端（FastAPI/uvicorn）与前端（Next.js），就绪后自动打开浏览器
  2. 启动提示框（深色影院风）：显示启动进度，支持「停止」与「停止后重试」
  3. 闲置检测：平台未被使用（浏览器未打开页面）超过 IdleMinutes 分钟后自动关闭所有进程

用法：
  start_manju.ps1                          # 默认 UI 模式（配合 start_manju.bat 双击）
  start_manju.ps1 -Command check           # 检查运行状态
  start_manju.ps1 -Command start           # 静默启动（后台运行，不阻塞）
  start_manju.ps1 -Command stop            # 静默停止
  start_manju.ps1 -Command run             # 控制台模式：启动 + 闲置自动关闭（验证/无头用）

参数：
  -IdleMinutes 5           闲置宽限分钟数（无浏览器访问达到该时长即自动关闭）
  -IdleCheckIntervalSec 30 闲置检测间隔（秒）
#>
param(
    [ValidateSet("ui", "check", "start", "stop", "run")]
    [string]$Command = "ui",
    [double]$IdleMinutes = 5,
    [int]$IdleCheckIntervalSec = 30,
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000
)

$ErrorActionPreference = "Stop"

# 全局错误兜底：任何未捕获异常写日志，UI 模式弹窗提示（双击启动时错误不再不可见）
$script:LauncherError = $null
trap {
    $script:LauncherError = $_.Exception.Message
    Write-Log "脚本错误: $script:LauncherError"
    try {
        Add-Type -AssemblyName System.Windows.Forms | Out-Null
        [System.Windows.Forms.MessageBox]::Show(
            "启动器发生错误：`n$script:LauncherError`n`n详细日志：$($script:LogFile)",
            "漫镜工场启动器", 'OK', 'Error') | Out-Null
    } catch { }
    exit 1
}

# ============ 路径与配置 ============
$script:RootDir     = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:BackendDir  = Join-Path $script:RootDir "backend"
$script:FrontendDir = Join-Path $script:RootDir "frontend"
$script:PythonExe   = Join-Path $script:BackendDir ".venv\Scripts\python.exe"
$script:LogFile     = Join-Path $script:RootDir "manju_launcher.log"
$script:PlatformUrl = "http://localhost:$FrontendPort"

# ============ 运行时状态 ============
$script:Phase        = "init"      # init/backend_wait/frontend_wait/ready/error/stopped
$script:PhaseSince   = $null
$script:BackendPid   = $null
$script:FrontendPid  = $null
$script:IdleSeconds  = 0
$script:AutoExit     = $false
$script:UI           = $false      # 是否 UI 模式
$script:OpenBrowser  = $false      # 就绪后是否自动打开浏览器（仅 UI 模式）
$script:ReadyHandled = $false      # ready 阶段是否已处理（打开浏览器+启动后台监控+关闭提示框）
$script:StatusTitle  = ""
$script:StatusDetail = ""

function Write-Log($msg) {
    $line = "{0} [launcher] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg
    try { Add-Content -Path $script:LogFile -Value $line -Encoding UTF8 } catch { }
}

# ============ 端口与进程工具 ============
function Get-PortListenerPid([int]$Port) {
    $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($c) { return ($c | Select-Object -First 1 -ExpandProperty OwningProcess) }
    return $null
}
function Test-PortListening([int]$Port) { return $null -ne (Get-PortListenerPid $Port) }
# 平台是否正被使用：前端端口存在浏览器等客户端的活跃 TCP 连接
function Test-PlatformInUse([int]$Port) {
    return $null -ne (Get-NetTCPConnection -LocalPort $Port -State Established -ErrorAction SilentlyContinue)
}
function Stop-Port([int]$Port) {
    $pids = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($p in $pids) {
        if ($p) {
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            Write-Log "已结束进程 $p（端口 $Port）"
        }
    }
}

# ============ 启动 / 停止 ============
function Start-Backend {
    $exe = $script:PythonExe
    if (-not (Test-Path $exe)) {
        $exe = (Get-Command python -ErrorAction SilentlyContinue).Source
    }
    if (-not $exe) { throw "找不到 Python 解释器（backend/.venv 或系统 python）" }
    $p = Start-Process -FilePath $exe `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
        -WorkingDirectory $script:BackendDir -WindowStyle Hidden -PassThru
    $script:BackendPid = $p.Id
    Write-Log "后端启动 PID=$($p.Id)（$exe）"
}
function Start-Frontend {
    $p = Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/c", "npm run dev" `
        -WorkingDirectory $script:FrontendDir -WindowStyle Hidden -PassThru
    $script:FrontendPid = $p.Id
    Write-Log "前端启动 PID=$($p.Id)（npm run dev）"
}
function Stop-Platform {
    Stop-Port $script:FrontendPort
    Stop-Port $script:BackendPort
    if ($script:FrontendPid) { Stop-Process -Id $script:FrontendPid -Force -ErrorAction SilentlyContinue; $script:FrontendPid = $null }
    if ($script:BackendPid)   { Stop-Process -Id $script:BackendPid   -Force -ErrorAction SilentlyContinue; $script:BackendPid   = $null }
    Write-Log "已停止全部平台进程"
}

# ============ 状态展示（UI 或控制台） ============
function Set-Status($title, $detail) {
    $script:StatusTitle = $title; $script:StatusDetail = $detail
    if ($script:UI) {
        if ($script:lblStatus) { $script:lblStatus.Text = $title }
        if ($script:lblDetail) { $script:lblDetail.Text = $detail }
        if ($script:prg) {
            $busy = $script:Phase -notin @("ready", "error", "stopped")
            $script:prg.Style = [System.Windows.Forms.ProgressBarStyle]::Marquee
            $script:prg.MarqueeAnimationSpeed = if ($busy) { 30 } else { 0 }
        }
    } else {
        Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $title) -ForegroundColor Cyan
        if ($detail) { Write-Host ("        {0}" -f $detail) -ForegroundColor DarkGray }
    }
}
function Set-Idle($text) {
    if ($script:UI) { if ($script:lblIdle) { $script:lblIdle.Text = $text } }
    else { Write-Host ("        {0}" -f $text) -ForegroundColor DarkGray }
}

# ============ 阶段状态机（启动流程） ============
function Update-Phase {
    $now = Get-Date
    switch ($script:Phase) {
        "init" {
            $script:PhaseSince = $now
            if (Test-PortListening $BackendPort) { Write-Log "端口 $BackendPort 已有服务，复用" }
            else {
                try { Start-Backend } catch { Set-Status "后端启动失败" $_.Exception.Message; $script:Phase = "error"; Write-Log "后端启动失败: $($_.Exception.Message)"; return }
            }
            $script:Phase = "backend_wait"; $script:PhaseSince = $now
            Set-Status "正在启动后端服务…" "uvicorn (FastAPI) · 端口 $BackendPort"
        }
        "backend_wait" {
            if (Test-PortListening $BackendPort) {
                $script:Phase = "frontend_start"; $script:PhaseSince = $now
                Set-Status "后端已就绪，正在启动前端工作台…" "npm run dev (Next.js) · 端口 $FrontendPort"
                if (Test-PortListening $FrontendPort) { Write-Log "端口 $FrontendPort 已有服务，复用" }
                else { try { Start-Frontend } catch { Set-Status "前端启动失败" $_.Exception.Message; $script:Phase = "error"; Write-Log "前端启动失败: $($_.Exception.Message)"; return } }
                $script:Phase = "frontend_wait"; $script:PhaseSince = $now
            }
            elseif (($now - $script:PhaseSince).TotalSeconds -gt 60) {
                Set-Status "后端启动超时" "请查看日志：$($script:LogFile)"; $script:Phase = "error"
            }
        }
        "frontend_wait" {
            if (Test-PortListening $FrontendPort) {
                $script:Phase = "ready"; $script:PhaseSince = $now; $script:IdleSeconds = 0
                if ($script:OpenBrowser) {
                    Set-Status "平台已就绪，正在打开浏览器…" $script:PlatformUrl
                    Start-Process $script:PlatformUrl
                } else {
                    Set-Status "平台已就绪" $script:PlatformUrl
                }
                Write-Log "平台就绪：$script:PlatformUrl"
            }
            elseif (($now - $script:PhaseSince).TotalSeconds -gt 120) {
                Set-Status "前端启动超时" "请查看日志：$($script:LogFile)"; $script:Phase = "error"
            }
        }
        "ready" {
            # 首次进入 ready：UI 模式下打开浏览器 → 启动后台闲置监控 → 自动关闭提示框
            if (-not $script:ReadyHandled) {
                $script:ReadyHandled = $true
                if ($script:OpenBrowser) {
                    Start-Process $script:PlatformUrl
                }
                Write-Log "平台就绪：$script:PlatformUrl"
                # UI 模式：启动后台隐藏进程接管闲置检测，然后关闭提示框
                if ($script:UI) {
                    Start-Process -FilePath "powershell.exe" -ArgumentList @(
                        "-NoProfile","-ExecutionPolicy","Bypass","-WindowStyle","Hidden",
                        "-File",$PSCommandPath,"-Command","run",
                        "-IdleMinutes",$IdleMinutes
                    ) -WindowStyle Hidden
                    Write-Log "已启动后台闲置监控进程，2 秒后关闭启动提示框"
                    # 延迟 2 秒关闭提示框（让用户看到"已就绪"状态）
                    $script:closeTimer = New-Object System.Windows.Forms.Timer
                    $script:closeTimer.Interval = 2000
                    $script:closeTimer.Add_Tick({
                        $script:closeTimer.Stop()
                        $script:AutoExit = $true   # 标记自动退出，FormClosing 不停止平台
                        $script:form.Close()
                    })
                    $script:closeTimer.Start()
                }
            }
            $mins = [math]::Round($script:IdleSeconds / 60, 1)
            Set-Idle "闲置检测：连续 $IdleMinutes 分钟无访问将自动关闭（当前 $mins 分钟）"
        }
    }
}

# ============ 闲置检测 ============
function Update-Idle {
    if ($script:Phase -ne "ready") { return }
    if (Test-PlatformInUse $FrontendPort) { $script:IdleSeconds = 0; return }
    $script:IdleSeconds += $IdleCheckIntervalSec
    if ($script:IdleSeconds -ge ($IdleMinutes * 60)) {
        Write-Log "闲置超过 $IdleMinutes 分钟（无浏览器访问），自动关闭平台"
        Stop-Platform
        $script:AutoExit = $true
        $script:Phase = "stopped"
        if ($script:UI) {
            Set-Status "平台闲置，已自动关闭" "所有服务已停止，可重新双击启动"
            $script:lblIdle.Text = ""
        } else {
            Set-Status "平台闲置，已自动关闭" "所有服务已停止"
        }
    }
}

# ============ 检查状态 ============
function Show-Status {
    $b = Get-PortListenerPid $BackendPort
    $f = Get-PortListenerPid $FrontendPort
    if ($b -or $f) {
        $parts = @()
        if ($b) { $parts += "后端 8000 ✓ PID=$b" } else { $parts += "后端 8000 ✗" }
        if ($f) { $parts += "前端 3000 ✓ PID=$f" } else { $parts += "前端 3000 ✗" }
        Write-Host ("平台运行中：{0}" -f ($parts -join " · ")) -ForegroundColor Green
        if (Test-PlatformInUse $FrontendPort) { Write-Host "浏览器访问：有活跃连接（页面打开中）" -ForegroundColor Cyan }
        else { Write-Host "浏览器访问：无活跃连接（页面已关闭）" -ForegroundColor Yellow }
    } else {
        Write-Host "平台未运行。" -ForegroundColor Yellow
    }
}

# ============ 主流程分发 ============
switch ($Command) {
    "check" { Show-Status }
    "stop"  { Stop-Platform; Show-Status }
    "start" {
        # 静默启动：推进到就绪后返回，服务在后台持续运行（不附带闲置监控）
        $script:Phase = "init"
        while ($script:Phase -notin @("ready", "error", "stopped")) {
            Update-Phase
            if ($script:Phase -eq "init" -or $script:Phase -eq "backend_wait" -or $script:Phase -eq "frontend_wait") {
                Start-Sleep -Milliseconds 800
            }
        }
        if ($script:Phase -eq "ready") { Write-Host "启动完成：$script:PlatformUrl" -ForegroundColor Green; exit 0 }
        else { Write-Host "启动失败，请查看日志：$($script:LogFile)" -ForegroundColor Red; exit 1 }
    }
    "run" {
        # 控制台模式：启动 + 闲置自动关闭（供验证 / 无头环境）
        $script:Phase = "init"
        while ($script:Phase -notin @("ready", "error", "stopped")) {
            Update-Phase
            if ($script:Phase -in @("init", "backend_wait", "frontend_wait")) { Start-Sleep -Milliseconds 800 }
        }
        if ($script:Phase -eq "ready") {
            Write-Host "平台已就绪：$script:PlatformUrl（Ctrl+C 手动退出）" -ForegroundColor Green
            while (-not $script:AutoExit) {
                Start-Sleep -Seconds $IdleCheckIntervalSec
                Update-Idle
            }
            Write-Host "启动器已退出。" -ForegroundColor Cyan
        } else {
            Write-Host "启动失败，请查看日志：$($script:LogFile)" -ForegroundColor Red
            exit 1
        }
    }
    "ui" {
        # ============ UI 模式（默认） ============
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing
        # 隐藏宿主控制台窗口（仅保留启动提示框；bat 不再用 -WindowStyle Hidden，出错时错误可见）
        Add-Type -Name Win32Console -Namespace Native -MemberDefinition @'
[DllImport("user32.dll")] public static extern IntPtr GetConsoleWindow();
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
'@
        try { [Native.Win32Console]::ShowWindow([Native.Win32Console]::GetConsoleWindow(), 0) | Out-Null } catch { }
        $script:UI = $true
        $script:OpenBrowser = $true

        $script:form = New-Object System.Windows.Forms.Form
        $script:form.Text = "漫镜工场 ManJu Studio 启动器"
        $script:form.Size = New-Object System.Drawing.Size(480, 300)
        $script:form.StartPosition = "CenterScreen"
        $script:form.FormBorderStyle = "FixedSingle"
        $script:form.MaximizeBox = $false
        $script:form.BackColor = [System.Drawing.Color]::FromArgb(20, 22, 28)

        $baseFont = New-Object System.Drawing.Font("Microsoft YaHei UI", 9)
        $titleFont = New-Object System.Drawing.Font("Microsoft YaHei UI", 16, [System.Drawing.FontStyle]::Bold)

        # 标题
        $lblTitle = New-Object System.Windows.Forms.Label
        $lblTitle.Text = "漫镜工场 · ManJu Studio"
        $lblTitle.Font = $titleFont
        $lblTitle.ForeColor = [System.Drawing.Color]::FromArgb(127, 119, 221)
        $lblTitle.Location = New-Object System.Drawing.Point(24, 20)
        $lblTitle.Size = New-Object System.Drawing.Size(430, 30)
        $script:form.Controls.Add($lblTitle)

        # 状态大字
        $script:lblStatus = New-Object System.Windows.Forms.Label
        $script:lblStatus.Text = "正在启动…"
        $script:lblStatus.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 13, [System.Drawing.FontStyle]::Bold)
        $script:lblStatus.ForeColor = [System.Drawing.Color]::FromArgb(237, 237, 240)
        $script:lblStatus.Location = New-Object System.Drawing.Point(24, 66)
        $script:lblStatus.Size = New-Object System.Drawing.Size(430, 26)
        $script:form.Controls.Add($script:lblStatus)

        # 详情小字
        $script:lblDetail = New-Object System.Windows.Forms.Label
        $script:lblDetail.Text = ""
        $script:lblDetail.Font = $baseFont
        $script:lblDetail.ForeColor = [System.Drawing.Color]::FromArgb(154, 154, 165)
        $script:lblDetail.Location = New-Object System.Drawing.Point(24, 96)
        $script:lblDetail.Size = New-Object System.Drawing.Size(430, 20)
        $script:form.Controls.Add($script:lblDetail)

        # 进度条
        $script:prg = New-Object System.Windows.Forms.ProgressBar
        $script:prg.Style = [System.Windows.Forms.ProgressBarStyle]::Marquee
        $script:prg.MarqueeAnimationSpeed = 30
        $script:prg.Location = New-Object System.Drawing.Point(24, 128)
        $script:prg.Size = New-Object System.Drawing.Size(430, 12)
        $script:form.Controls.Add($script:prg)

        # 闲置提示
        $script:lblIdle = New-Object System.Windows.Forms.Label
        $script:lblIdle.Text = ""
        $script:lblIdle.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 8.5)
        $script:lblIdle.ForeColor = [System.Drawing.Color]::FromArgb(124, 124, 136)
        $script:lblIdle.Location = New-Object System.Drawing.Point(24, 152)
        $script:lblIdle.Size = New-Object System.Drawing.Size(430, 18)
        $script:form.Controls.Add($script:lblIdle)

        # 底部提示
        $lblTip = New-Object System.Windows.Forms.Label
        $lblTip.Text = "关闭浏览器后，平台闲置 $IdleMinutes 分钟将自动停止服务"
        $lblTip.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 8.5)
        $lblTip.ForeColor = [System.Drawing.Color]::FromArgb(107, 107, 118)
        $lblTip.Location = New-Object System.Drawing.Point(24, 182)
        $lblTip.Size = New-Object System.Drawing.Size(430, 18)
        $script:form.Controls.Add($lblTip)

        # 按钮样式
        $btnStyle = {
            param($c)
            $c.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
            $c.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(51, 53, 74)
            $c.BackColor = [System.Drawing.Color]::FromArgb(34, 36, 46)
            $c.ForeColor = [System.Drawing.Color]::FromArgb(232, 232, 238)
            $c.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 9)
        }

        $btnRestart = New-Object System.Windows.Forms.Button
        $btnRestart.Text = "停止后重试"
        $btnRestart.Location = New-Object System.Drawing.Point(250, 214)
        $btnRestart.Size = New-Object System.Drawing.Size(95, 36)
        & $btnStyle $btnRestart
        $btnRestart.Add_Click({
            Stop-Platform
            $script:Phase = "init"; $script:IdleSeconds = 0
            Set-Status "正在重新启动…" ""
            Write-Log "用户点击「停止后重试」"
        })
        $script:form.Controls.Add($btnRestart)

        $btnStop = New-Object System.Windows.Forms.Button
        $btnStop.Text = "停止"
        $btnStop.Location = New-Object System.Drawing.Point(359, 214)
        $btnStop.Size = New-Object System.Drawing.Size(95, 36)
        & $btnStyle $btnStop
        $btnStop.Add_Click({
            Stop-Platform
            Write-Log "用户点击「停止」，退出启动器"
            $script:AutoExit = $true
            $script:form.Close()
        })
        $script:form.Controls.Add($btnStop)

        # 关闭窗体（X）→ 停止服务并退出
        $script:form.Add_FormClosing({
            param($sender, $e)
            if (-not $script:AutoExit) {
                Write-Log "窗口被关闭，停止平台"
                Stop-Platform
            }
        })

        # 定时器：阶段推进（500ms）
        $tick = New-Object System.Windows.Forms.Timer
        $tick.Interval = 500
        $tick.Add_Tick({ Update-Phase })
        # 定时器：闲置检测
        $idleTimer = New-Object System.Windows.Forms.Timer
        $idleTimer.Interval = [math]::Max(1, $IdleCheckIntervalSec) * 1000
        $idleTimer.Add_Tick({ Update-Idle })

        $script:form.Add_Shown({
            $tick.Start()
            $idleTimer.Start()
            $script:Phase = "init"
        })

        try {
            [System.Windows.Forms.Application]::Run($script:form)
        } finally {
            $tick.Stop(); $idleTimer.Stop()
            if ($script:closeTimer) { $script:closeTimer.Stop(); $script:closeTimer.Dispose() }
            $tick.Dispose(); $idleTimer.Dispose()
            $script:form.Dispose()
        }
    }
}
