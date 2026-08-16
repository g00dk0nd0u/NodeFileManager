# NodeFileManager

NodeFileManager は、実フォルダーを自由配置できるノードとして閲覧する Windows 向けローカルアプリです。Blender Node Editor の暗い、広い、直接操作できるワークスペースを参考にしつつ、ファイル管理に不要なソケット等は持ちません。

## 必要環境と起動

- Python 3.14（`tkinter` を含むこと）
- Microsoft Edge などのブラウザー
- Node.js、npm、ビルド、CDN、外部 Python パッケージは不要

`scripts\start.cmd` をダブルクリックします。バックエンドの準備後に <http://127.0.0.1:8000/> が自動で開きます。終了はコマンド画面で `Ctrl+C` です。

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

Windows では `%LOCALAPPDATA%\NodeFileManager\workspace.json`、その他では `~/.nodefilemanager/workspace.json` を使います。JSON は表示状態だけを保存し、ファイル一覧は毎回ディスクから取得します。詳細は [architecture.md](docs/architecture.md) を参照してください。

## 社内 Windows PC での手動確認

変異操作は必ず disposable なローカルテストフォルダーで実施してください。複数の子フォルダー、PDF、画像、テキスト／文書ファイルを用意し、展開、ファイルを開く、名前変更、コピー、Move、別ノードへのドラッグ移動（Alt でコピー）を順に確認します。OS 側でファイルを作成／削除して **Refresh** 後に表示が一致すること、終了・再起動後に配置と展開が戻りつつファイル一覧は現在のディスク内容になることも確認します。

社内 PC では Defender/EDR の警告、ネットワークドライブ、OneDrive/SharePoint のポリシー差を記録し、同期領域での変異テストはローカル確認後だけ行ってください。

1. Python 3.14 を導入し、`py -3.14 -m tkinter` で Tk ダイアログが開くことを確認します。
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

## macOS picker 回帰確認

macOS では `python3 -m backend.server` で起動し、上記 disposable フォルダーの一連の手順と、Finder の既定アプリで PDF、画像、文書が開くことを確認します。

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

## 既知の制限

ファイル監視、検索、undo/redo、複数タブ、高度な自動配置は未実装です。削除は標準ライブラリだけで各 OS のごみ箱へ確実に送る共通手段がないため、永久削除を避けて延期しています。Tk がない Python では選択できませんが、UI に明示的なエラーを表示します。picker は一時的な topmost parent を使う best-effort 実装であり、OS や desktop window manager によっては常に最前面になる保証はありません。同時に複数プロセスを起動する運用や巨大ディレクトリの性能は未調整です。
