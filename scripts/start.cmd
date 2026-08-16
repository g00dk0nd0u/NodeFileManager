@echo off
setlocal
cd /d "%~dp0.."

echo NodeFileManager を起動します...
echo URL: http://127.0.0.1:8000/
echo 終了するには Ctrl+C を押してください。

where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3.14 --version >nul 2>nul
  if %errorlevel% equ 0 (
    start "" "http://127.0.0.1:8000/"
    py -3.14 -m backend.server
    goto :end
  )
)

where python >nul 2>nul
if %errorlevel% equ 0 (
  python -c "import sys; raise SystemExit(sys.version_info[:2] != (3, 14))" >nul 2>nul
  if %errorlevel% equ 0 (
    python --version
    start "" "http://127.0.0.1:8000/"
    python -m backend.server
    goto :end
  )
)

echo エラー: Python 3.14 が見つかりません。
echo 社内 Software Center から Python 3.14 をインストールしてください。
pause
exit /b 1

:end
if errorlevel 1 (
  echo サーバーがエラーで終了しました。
  pause
)
