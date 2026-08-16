# アーキテクチャ

## 責務とデータフロー

ブラウザー UI → localhost JSON API → Python ファイルシステム権限、という一方向の境界です。フロントエンドは接続されたDOM folder panel、Kanban-style child columns、preview、選択・group drag・パン・ズームを担当します。filesystem hierarchyのwireは描画しません。

Python は `tkinter.filedialog.askdirectory` を抽象化した picker からのみルートを追加します。picker は固定された `sys.executable -m backend.filesystem.folder_picker_child` を起動し、専用の短命プロセス内で Tk の生成から破棄までを完結させます。子は選択、キャンセル、エラーを JSON で返し、サーバーは終了コードと JSON を検証します。クラッシュ、不正応答、10 分のタイムアウトは API エラーとなり、タイムアウト時には標準ライブラリが子を kill して wait するため、長時間稼働するサーバーに Tk のモーダル状態が残りません。

HTTP サーバーは `ThreadingHTTPServer` です。picker を待つリクエストとは別に health や workspace を処理できます。一方、非ブロッキング lock により picker は全体で一つだけとし、二つ目には `409 picker_already_open` を返します。lock は成功、キャンセル、例外、クラッシュ、タイムアウトのすべてで `finally` により解放します。

`RootRegistry` はセッション中の選択済みルートと発見済み item ID を保持し、一覧・open・変更 API は ID だけを受け取ります。各操作時に実在性と symlink 解決後のルート内包含を再検証します。ブラウザー指定の任意パスや実行コマンドを受け取る API はありません。復元時だけ、以前保存したルートが現在も実在することを検証して再認可します。

一覧は認可済み親を一度だけ厳密に解決し、`os.scandir()` の一回の走査で直下を分類します。直下 item は lexical path と ID だけを安価に登録し、子フォルダー内は展開されるまで読みません。open・変更・次階層の一覧時には、保存済み path を厳密に resolve して認可ルート内であることを再検証します。
ファイルの更新時刻は同じ `DirEntry` の `stat()` から取得します。ファイルごとの metadata I/O は発生し得ますが、子フォルダー内部の走査は行いません。通常のルート選択は短命な server-side folder-browser session と opaque ID を使い、confirm 時にだけ選択中pathを認可します。Tk pickerは通常UIから使用しないfallbackです。

## API

- `GET /api/health`: 稼働確認
- `POST /api/folders/select`: ネイティブ選択とルート認可（キャンセル時は `folder: null`）
- `GET /api/folders/children?id=...`: 認可済みフォルダー直下の `folders` / `files` メタデータ
- `POST /api/files/open`: 認可済み既存ファイルを OS の既定アプリで開く
- `PATCH /api/items/rename`: 同じ親内でファイル／フォルダーを名前変更
- `POST /api/items/copy`, `POST /api/items/move`: 認可済み宛先フォルダーへのコピー／移動
- `GET /api/workspace`: 保存状態と、現時点で利用可能なルート
- `PUT /api/workspace`: 表示状態保存

サーバーは `127.0.0.1` のみに bind し、全リクエストの `Host`、状態変更の `Origin` を検証します。CORS は有効化しません。

## ワークスペース

JSON にはルートパス、フォルダーノード ID/親 ID/表示情報、座標、展開状態、viewport の pan/zoom を保存します。ファイル一覧は保存せず、起動・展開・Refresh 時に実ファイルシステムから取得します。一時ファイルを書いてから置換します。欠損・不正 JSON・利用不能ルートは空状態または部分復元として扱います。

## 次の改善候補

実機利用後、最初に確認された操作上の摩擦を優先します。候補は、大規模フォルダーの遅延読み込み表示、保存エラーの状態表示、キーボード操作、ノード重なり回避です。破壊的ファイル操作を追加する前に認可モデルのハードニングと専用テストが必要です。
