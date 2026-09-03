# NodeFileManager

NodeFileManager は、実フォルダーを Folder Panel として空間的に扱う Windows / macOS 向けローカルアプリです。Blender Node Editor の暗い広いキャンバスと直接操作感を参考にしつつ、目的はノード編集ではなく **「今使うフォルダーだけを机の上に出しておく persistent spatial workspace」** です。

## HOW TO START NODEFILEMANAGER / 起動方法

いずれの方法も、ヘルス確認後に既定ブラウザーで NodeFileManager を開きます。Node.js、npm、管理者権限、CDN は不要です。

- **macOS — ソース checkout:** Finder で `scripts/NodeFileManager.command` をダブルクリックします。初回だけ terminal で `chmod +x scripts/NodeFileManager.command` を実行してください。終了は launcher の Terminal で `Ctrl+C` です。
- **Windows — ソース（推奨）:** repository 直下の `NodeFileManager.pyw` をダブルクリックします。console window なしでブラウザーが開き、toolbar の **Quit** で安全に終了できます。
- **Windows — ソース / console・debug fallback:** `scripts\start.cmd` をダブルクリックします。Python 3.14 を優先し、互換 Python 3 を安全に検出します。終了は command window で `Ctrl+C` です。
- **Windows — standalone:** `NodeFileManager-windows-x64.zip` を展開し、フォルダー内の `NodeFileManager.exe` をダブルクリックします。Python は不要です。
- **macOS — standalone:** `NodeFileManager-macos-x64.zip` を展開し、`NodeFileManager.app` をダブルクリックします。Python は不要です。

standalone と Windows の `NodeFileManager.pyw` 起動では toolbar の **Quit** が所有中の localhost server を安全に停止します。ブラウザーのタブを閉じるだけでは application process は終了しません。console launcher でのソース起動では **Quit** を表示せず、Terminal/command window が lifecycle を所有します。

### 開発者向け起動

Python 3.10 以降（3.14 推奨）で `python -m backend.launcher` を実行します。ブラウザー不要の診断は `python -m backend.launcher --no-browser`、従来の server-only 起動は `python -m backend.server` です。通常 UI はアプリ内 folder browser を使うため `tkinter` は必須ではありません。旧 Tk picker だけが隔離された fallback として残っています。

## 現在の操作モデル

### フォルダーをワークスペースへ追加

空のキャンバスを右クリックし **Select Folder** を選び、アプリ内 folder browser から実フォルダーを選択します。追加したフォルダーは新しい **Working Set** の root Folder Panel になります。

### Folder Panel と階層

- フォルダー行をクリックすると、そのフォルダーが別の Folder Panel として materialize されます。
- 同じ親から direct child が1つなら右方向の **Trail**、複数なら親の下に **Shelf** として自動配置します。
- connector は親 Folder Panel 内の該当フォルダー行から子 Folder Panel へ接続します。
- 開いているフォルダー行は open 状態として表示されます。
- Folder Panel 右上の **×** は、その Panel と descendants をまとめて閉じます。
- 実親が表示されていない root Panel には **Compact Parent** が上流タブとして表示され、クリックすると実親を同じ Working Set 内へ materialize します。

階層内の Folder Panel 配置は自動です。通常の Folder Panel を自由配置するモデルではありません。Working Set 自体はひとつのグループとして移動できます。

### Working Set

Working Set は関連する Folder Panel 群をひとつの作業単位として囲います。ラベルは `WORKING SET` と現在の visual root context を表示します。単一 root なら root Folder名、複数 root がある場合は `N roots` と表示します。

### Isolate / Reattach

- Panel の右クリックメニューから **Isolate** を実行すると、その branch を descendants ごと別 Working Set に分離します。
- 親が別 Working Set に存在する isolated branch は、その親を持つ Working Set へドラッグすることで **Reattach** できます。
- Isolate / Reattach は filesystem のフォルダーパスを変更しません。表示上の Working Set / visual hierarchy の操作です。

### 実ファイル / 実フォルダーの Move

NodeFileManager には **表示上の navigation** と **実 filesystem mutation** の両方があります。混同しないでください。

- ファイル行を別 Folder Panel の file region へドラッグすると、その実ファイルを移動します。
- Alt / Option を押しながらファイルをドロップするとコピーします。
- Folder Panel を別 Folder Panel の folder region / folder row へドラッグすると、その実フォルダーを移動します。
- filesystem Move 後は表示中の identity / hierarchy を再調整します。

変異操作の検証は必ず disposable なテストフォルダーで行ってください。

### 検索

- 各 Folder Panel の検索ボタンから、そのフォルダー以下を recursive search できます。検索入力欄と結果カードは対象 Panel の上に一時表示されます。
- 空のキャンバスを右クリックして **Search Workspace** を選ぶか、`Ctrl+K` / `Cmd+K` で、現在 materialize されている workspace 内を検索できます。
- 検索結果を選択すると該当 Panel / 行へ移動します。

### その他

- ファイルはダブルクリックで既定アプリから開きます。
- JPG / PNG / PDF は Panel 下部で preview できます。
- **Rename** で選択中の file / folder を rename できます。
- **Refresh** は表示中 filesystem state を再読み込みします。
- 背景ドラッグで pan、ホイールで zoom します。
- Working Set、展開状態、viewport は自動保存され、再起動時に現在の filesystem と照合して復元されます。

### Undo / Redo

- `Ctrl+Z` / `Cmd+Z` で Undo、`Ctrl+Shift+Z` / `Cmd+Shift+Z` で Redo します。Windows では `Ctrl+Y` でも Redo できます。
- 履歴はひとつの時系列で、workspace 編集、Rename、Move、Copy、Create Folder、Favorite の追加・削除が対象です。
- Refresh または focus 復帰時に外部 filesystem 変更を検出すると、その session の履歴を破棄します。変更がなければ Refresh しても履歴は維持されます。
- 履歴は session 内だけに保持され、アプリの再起動後には引き継がれません。

## アーキテクチャと永続化

- `frontend/`: HTML/CSS、ネイティブ ES Modules。Folder Panel、Working Set、Trail/Shelf、connector、search、preview、drag interaction を描画
- `backend/filesystem/`: 許可ルート、folder browser、一覧、検索、open、名前変更／コピー／移動
- `backend/workspace/`: UI 状態をローカル JSON に原子的に保存
- `backend/server.py`: Python 標準ライブラリだけの localhost HTTP API と静的配信

Windows では `%LOCALAPPDATA%\NodeFileManager\workspace.json`、macOS/その他では `~/.nodefilemanager/workspace.json` を使います。log はそれぞれ同じ user-data directory の `logs/NodeFileManager.log`（rotating、最大 1 MB × 4 世代）です。アプリ本体や `.app` 内には書き込みません。JSON は表示状態だけを保存し、ファイル一覧は毎回ディスクから取得します。詳細は [architecture.md](docs/architecture.md) を参照してください。

AI / design review 用の製品コンテキストと invariants はルートの [`CLAUDE.md`](CLAUDE.md) にまとめています。

## Standalone test build

build dependency は PyInstaller のみです。`python -m pip install -r requirements-build.txt` の後、対象 OS 上で `python scripts/build_standalone.py` を実行します。reviewable な `NodeFileManager.spec` が frontend 全体を含む onedir build を作り、次を生成します（cross compile はしません）。

- Windows x64: `dist/NodeFileManager/NodeFileManager.exe` と `dist/NodeFileManager-windows-x64.zip`
- macOS Intel: `dist/NodeFileManager.app` と `dist/NodeFileManager-macos-x64.zip`

GitHub Actions の **Standalone test builds** は Windows x64 / macOS x64 で tests、build、実 executable の `--no-browser` 起動、`/api/health` の identity と `packaged: true`、narrow quit endpoint による終了を確認し、commit SHA 付き artifact を upload します。Release は作りません。

これらは未署名の内部 test build です。Windows Defender/SmartScreen/企業 EDR が警告または遮断する場合があるため、security policy を弱めず source + Python の fallback を使ってください。macOS Gatekeeper は未署名 app を遮断する場合があります。承認された社内手順（Finder の「開く」など）に従い、Gatekeeper を無効化しないでください。x64 artifact を universal2/arm64 として扱わないでください。

### Standalone 手動確認

1. 対象 OS の x64 ZIP を repository Python 環境外へ展開します。
2. Windows は `NodeFileManager.exe`、macOS は `NodeFileManager.app` をダブルクリックします。
3. browser が開き、health 表示が `packaged` であることを確認します。
4. disposable folder を使って Select Folder、Trail/Shelf展開、Compact Parent、Isolate/Reattach、local search / workspace search、Move、JPG/PNG/PDF preview を確認します。
5. **Quit** を押し、port 8000 が解放されることを確認します。
6. 再起動し Working Set / materialized hierarchy / viewport が復元されることを確認します。

## 社内 Windows PC での手動確認

変異操作は必ず disposable なローカルテストフォルダーで実施してください。複数の子フォルダー、PDF、画像、テキスト／文書ファイルを用意し、展開、ファイルを開く、名前変更、コピー、Move、検索を順に確認します。OS 側でファイルを作成／削除して **Refresh** 後に表示が一致すること、終了・再起動後に Working Set と materialized hierarchy が戻りつつファイル一覧は現在のディスク内容になることも確認します。

社内 PC では Defender/EDR の警告、ネットワークドライブ、OneDrive/SharePoint のポリシー差を記録し、同期領域での変異テストはローカル確認後だけ行ってください。

1. Python 3.14 を導入します（通常起動に tkinter は不要です）。
2. repository 直下の `NodeFileManager.pyw` をダブルクリックし、console window なしでブラウザーが自動表示されることを確認します。console/debug fallback の確認時は `scripts\start.cmd` を使います。
3. 空キャンバス右クリック → **Select Folder** でテストフォルダーを追加します。
4. Trail / Shelf、connector、Working Set、Compact Parent を確認します。
5. Isolate / Reattach と filesystem Move が別の結果になることを disposable folder で確認します。
6. local search / Search Workspace を確認します。
7. toolbar の **Quit** で終了し、再度 `NodeFileManager.pyw` を実行して Working Set、materialized hierarchy、pan、zoom が戻ることを確認します。`start.cmd` の場合は `Ctrl+C` で終了します。
8. 選択済みフォルダーを一時的に移動して再起動し、画面が停止せず復元不能状態を処理できることを確認します。

旧Tk pickerはfallbackコードとして残っていますが、通常UIからは呼び出しません。

## macOS source 手動確認

repository を空白を含む path に置き、Finder で `scripts/NodeFileManager.command` をダブルクリックします。health 成功後だけ browser が開くこと、上記 disposable フォルダーの一連の手順と、Finder の既定アプリで PDF、画像、文書が開くことを確認します。

回帰確認では、空の背景をドラッグすると viewport だけが動き、Folder Panel / Working Set操作では pan しないことを確認します。また、open child panelを保存して終了した後、外部で子フォルダーを削除・追加し、再起動またはRefresh時に現在の階層と一致することを確認します。PDF previewはbrowser native rendererと`#page=N`を使うため、page fragmentの挙動はSafari/Edgeの内蔵PDF viewerに依存し、総page数は表示しません。

## Launcher の port 判定

- port 8000 が空き: server を起動し、identity health 成功後に browser を開きます。
- 正しい NodeFileManager が応答: server は増やさず既存 instance を再利用して browser を開きます。
- 別 process が占有: process を kill せず明確な error と exit code 2 を返します。

## 既知の制限

- 複数タブは未実装です。
- filesystem watcher は未実装ですが、window focus / visibility復帰時と **Refresh** で再読込します。
- Trail / Shelf による hierarchy 自動配置は実装済みですが、非常に深い階層や大量 sibling 向けの折返し・高度なpackingは未調整です。
- 大規模ディレクトリ / 多数Panel時の性能は未調整です。
- filesystem Move / Copy は実データを変更するため、現時点では disposable folder で十分に検証してください。
- 削除は標準ライブラリだけで各 OS のごみ箱へ確実に送る共通手段がないため、永久削除を避けて延期しています。
- 旧 Tk fallback picker は Tk がない環境では使えませんが、通常のアプリ内 picker には影響しません。
