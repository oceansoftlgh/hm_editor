@echo off
REM ============================================================
REM  sync_editor_dist.bat
REM  双击即可把 grunt release 产物同步到
REM  nurse.board.ui/public/hmEditor
REM
REM  默认走 dry-run 模式（只打印计划，不落地），
REM  把第一行改为 CALL :RUN 才会真正执行。
REM ============================================================

setlocal

REM 切到脚本自身目录
cd /d "%~dp0"

REM ---------- 优先使用 py launcher（python 3.3+ 自带） ----------
where py >nul 2>&1
if %ERRORLEVEL%==0 (
    set "PY=py -3"
) else (
    where python >nul 2>&1
    if %ERRORLEVEL%==0 (
        set "PY=python"
    ) else (
        echo [错误] 未找到 Python。请先安装 Python 3.8+ 并加入 PATH。
        pause
        exit /b 1
    )
)

REM ---------- 选择模式 ----------
REM 取消下面一行的注释即可执行真实同步（默认 dry-run）
REM CALL :RUN
CALL :RUN

goto :eof

:DRYRUN
echo === DRY-RUN（不落地）===
%PY% sync_editor_dist.py --dry-run
echo.
echo ============================================================
echo  确认无误后，请用编辑器打开本文件，把 CALL :DRYRUN 改成
echo  CALL :RUN，再次双击即可真正同步。
echo ============================================================
goto :eofpause

:RUN
echo === 真正同步（将覆盖目标文件、清理孤儿）===
%PY% sync_editor_dist.py
echo.
echo === 完成 ===
goto :eof

:eofpause
pause
endlocal
