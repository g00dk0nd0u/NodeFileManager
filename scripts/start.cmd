@echo off
setlocal
cd /d "%~dp0.."

echo NodeFileManager を起動します...
echo URL: http://127.0.0.1:8000/
echo 終了するには Ctrl+C を押してください。

set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 (
  py -3.14 --version >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_CMD=py -3.14"
  )
)

if not defined PYTHON_CMD (
  where python >nul 2>nul
  if not errorlevel 1 (
    python -c "import sys; raise SystemExit(sys.version_info[:2] != (3, 14))" >nul 2>nul
    if not errorlevel 1 (
      set "PYTHON_CMD=python"
    )
  )
)

if defined PYTHON_CMD goto :start_server

echo エラー: Python 3.14 が見つかりません。
echo 社内 Software Center から Python 3.14 をインストールしてください。
pause
exit /b 1

:start_server
echo Python バックエンドを起動しています...
start "" /b %PYTHON_CMD% -m backend.server

for /l %%A in (1,1,15) do (
  %PYTHON_CMD% -c "import json, urllib.request; response = urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=1); raise SystemExit(response.status != 200 or json.load(response).get('status') != 'ok')" >nul 2>nul
  if not errorlevel 1 goto :ready
  ping 127.0.0.1 -n 2 >nul
)

echo エラー: バックエンドのヘルスチェックに失敗しました。
echo 上に表示された Python のエラーを確認してください。
pause
exit /b 1

:ready
echo バックエンドの起動を確認しました。ブラウザーを開きます。
start "" "http://127.0.0.1:8000/"
