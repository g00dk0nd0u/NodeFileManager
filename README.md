# NodeFileManager

NodeFileManager は、実フォルダーを自由配置できるノードとして閲覧する Windows 向けローカルアプリです。Blender Node Editor の暗い、広い、直接操作できるワークスペースを参考にしつつ、ファイル管理に不要なソケット等は持ちません。

## HOW TO START NODEFILEMANAGER / 起動方法

いずれの方法も、ヘルス確認後に既定ブラウザーで NodeFileManager を開きます。Node.js、npm、管理者権限、CDN は不要です。

- **macOS — ソース checkout:** Finder で `scripts/NodeFileManager.command` をダブルクリックします。初回だけ terminal で `chmod +x scripts/NodeFileManager.command` を実行してください。終了は launcher の Terminal で `Ctrl+C` です。
- **Windows — ソース / 社内 PC fallback:** `scripts\start.cmd` をダブルクリックします。Python 3.14 を優先し、互換 Python 3 を安全に検出します。終了は command window で `Ctrl+C` です。
- **Windows — standalone:** `NodeFileManager-windows-x64.zip` を展開し、フォルダー内の `NodeFileManager.exe` をダブルクリックします。Python は不要です。
- **macOS — standalone:** `NodeFileManager-macos-x64.zip` を展開し、`NodeFileManager.app` をダブルクリックします。Python は不要です。

standalone では toolbar の **Quit** が所有中の localhost server を安全に停止します。ブラウザーのタブを閉じるだけでは application process は終了しません。ソース起動では **Quit** を表示せず、Terminal/command window が lifecycle を所有します。

### 開発者向け起動

Python 3.10 以降（3.14 推奨）で `python -m backend.launcher` を実行します。ブラウザー不要の診断は `python -m backend.launcher --no-browser`、従来の server-only 起動は `python -m backend.server` です。通常 UI はアプリ内 folder browser を使うため `tkinter` は必須ではありません。旧 Tk picker だけが隔離された fallback として残っています。

## 使い方

1. **Select Folder** を押し、アプリ内ダイアログでフォルダーを移動して **Select This Folder** を押します。
2. 新しいノードは直下のフォルダー行とファイル行を開いた状態で表示します。フォルダー行を押すと、そのフォルダーだけを次のノードとして開閉します。
3. ファイルはダブルクリックで開き、Rename で名前変更できます。別の表示中フォルダーノードへのドラッグは移動、Alt/Option+ドラッグはコピーです。
4. OS 側の変更は **Refresh** で再読み込みします。
5. ノードをドラッグして移動します。背景ドラッグでパン、ホイールでズームします。
6. 配置、展開状態、パン、ズームは自動保存され、次回起動時に現在のファイルシステムから復元されます。

## アーキテクチャと永続化

- `frontend/`: HTML/CSS、ネイティブ ES Modules。接続されたフォルダーパネル、Kanban列、previewを描画
- `backend/filesystem/`: ネイティブ選択ダイアログ、許可ルート、一覧、open、名前変更／コピー／移動
- `backend/workspace/`: UI 状態をローカル JSON に原子的に保存
- `backend/server.py`: Python 標準ライブラリだけの localhost HTTP API と静的配信

Windows では `%LOCALAPPDATA%\NodeFileManager\workspace.json`、macOS/その他では従来どおり `~/.nodefilemanager/workspace.json` を使います。log はそれぞれ同じ user-data directory の `logs/NodeFileManager.log`（rotating、最大 1 MB × 4 世代）です。アプリ本体や `.app` 内には書き込みません。JSON は表示状態だけを保存し、ファイル一覧は毎回ディスクから取得します。詳細は [architecture.md](docs/architecture.md) を参照してください。

## Standalone test build

build dependency は PyInstaller のみです。`python -m pip install -r requirements-build.txt` の後、対象 OS 上で `python scripts/build_standalone.py` を実行します。reviewable な `NodeFileManager.spec` が frontend 全体を含む onedir build を作り、次を生成します（cross compile はしません）。

- Windows x64: `dist/NodeFileManager/NodeFileManager.exe` と `dist/NodeFileManager-windows-x64.zip`
- macOS Intel: `dist/NodeFileManager.app` と `dist/NodeFileManager-macos-x64.zip`

GitHub Actions の **Standalone test builds** は Windows x64 / macOS x64 で tests、build、実 executable の `--no-browser` 起動、`/api/health` の identity と `packaged: true`、narrow quit endpoint による終了を確認し、commit SHA 付き artifact を upload します。Release は作りません。

これらは未署名の内部 test build です。Windows Defender/SmartScreen/企業 EDR が警告または遮断する場合があるため、security policy を弱めず source + Python の fallback を使ってください。macOS Gatekeeper は未署名 app を遮断する場合があります。承認された社内手順（Finder の「開く」など）に従い、Gatekeeper を無効化しないでください。x64 artifact を universal2/arm64 として扱わないでください。

### Standalone 手動確認

1. 対象 OS の x64 ZIP を repository Python 環境外へ展開します。
2. Windows は `NodeFileManager.exe`、macOS は `NodeFileManager.app` をダブルクリックします。
3. browser が開き、health 表示が `packaged` であること、Select Folder、一覧、move、JPG/PNG/PDF preview を disposable folder で確認します。
4. **Quit** を押し、port 8000 が解放されることを確認します。再起動し workspace が復元されることを確認します。

## 社内 Windows PC での手動確認

変異操作は必ず disposable なローカルテストフォルダーで実施してください。複数の子フォルダー、PDF、画像、テキスト／文書ファイルを用意し、展開、ファイルを開く、名前変更、コピー、Move、別ノードへのドラッグ移動（Alt でコピー）を順に確認します。OS 側でファイルを作成／削除して **Refresh** 後に表示が一致すること、終了・再起動後に配置と展開が戻りつつファイル一覧は現在のディスク内容になることも確認します。

社内 PC では Defender/EDR の警告、ネットワークドライブ、OneDrive/SharePoint のポリシー差を記録し、同期領域での変異テストはローカル確認後だけ行ってください。

1. Python 3.14 を導入します（通常起動に tkinter は不要です）。
2. `scripts\start.cmd` をダブルクリックし、ブラウザーが自動表示されることを確認します。
3. **Select Folder** で子フォルダーを持つ実フォルダーを選択します。
4. 親子パネルの接続、group移動、背景パン、ホイールズームを順に確認します。
5. `Ctrl+C` で終了し、再度 `start.cmd` を実行してルート、展開、位置、パン、ズームが戻ることを確認します。
6. 選択済みフォルダーを一時的に移動して再起動し、画面が停止せず復元不能件数を表示することを確認します。

旧Tk pickerはfallbackコードとして残っていますが、通常UIからは呼び出しません。アプリ内pickerの回帰確認では、次も実施します。

- `py -3.14 -m tkinter` が動作することを確認します。
- **Select Folder** がアプリ内dialogを即座に開き、選択、Escape、backdrop、Cancelを繰り返しても使い続けられることを確認します。
- 余分なコンソールウィンドウが表示されないことを確認します（Windows の子プロセスには `CREATE_NO_WINDOW` を使用します）。
- 権限が許す範囲で UNC、ネットワーク、OneDrive、SharePoint 同期フォルダーを選択します。
- picker を開いたまま <http://127.0.0.1:8000/api/health> が応答することを確認します。

## macOS source 手動確認

repository を空白を含む path に置き、Finder で `scripts/NodeFileManager.command` をダブルクリックします。health 成功後だけ browser が開くこと、上記 disposable フォルダーの一連の手順と、Finder の既定アプリで PDF、画像、文書が開くことを確認します。

1. NodeFileManager を起動します。
2. **Select Folder** を押します。
3. キャンセルします。
4. 再度 **Select Folder** を押します。
5. 実フォルダーを選択します。
6. ルートノードが表示されることを確認します。
7. **Select Folder** を少なくとも 5 回繰り返します。
8. picker を開いたまま <http://127.0.0.1:8000/api/health> が応答することを確認します。
9. 複数の方法で picker を閉じる、またはキャンセルします。
10. どの場合も NodeFileManager を引き続き利用できることを確認します。

続けて **Select Folder → Node → Expand → Edges → Drag → Pan/Zoom → Close → Restart → Restore** の一連の操作を再確認します。

回帰確認では、空の背景をドラッグすると viewport だけが動き、folder panelの操作ではpanしないことを確認します。また、open child panelを保存して終了した後、外部で子フォルダーを削除・追加し、再起動またはRefresh時に現在の階層と一致することを確認します。PDF previewはbrowser native rendererと`#page=N`を使うため、page fragmentの挙動はSafari/Edgeの内蔵PDF viewerに依存し、総page数は表示しません。

## Launcher の port 判定

- port 8000 が空き: server を起動し、identity health 成功後に browser を開きます。
- 正しい NodeFileManager が応答: server は増やさず既存 instance を再利用して browser を開きます。
- 別 process が占有: process を kill せず明確な error と exit code 2 を返します。

## 既知の制限

ファイル監視、検索、undo/redo、複数タブ、高度な自動配置は未実装です。削除は標準ライブラリだけで各 OS のごみ箱へ確実に送る共通手段がないため、永久削除を避けて延期しています。旧 Tk fallback picker は Tk がない環境では使えませんが、通常のアプリ内 picker には影響しません。巨大ディレクトリの性能は未調整です。
