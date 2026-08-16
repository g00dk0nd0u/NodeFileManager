# アーキテクチャ

## 責務とデータフロー

ブラウザー UI → localhost JSON API → Python ファイルシステム権限、という一方向の境界です。フロントエンドは DOM フォルダーノード、SVG エッジ、選択・ドラッグ・パン・ズームを担当します。座標変換は `viewport.js`、初回の子配置は `layout.js` に分離しています。

Python は `tkinter.filedialog.askdirectory` を抽象化した picker からのみルートを追加します。picker は固定された `sys.executable -m backend.filesystem.folder_picker_child` を起動し、専用の短命プロセス内で Tk の生成から破棄までを完結させます。子は選択、キャンセル、エラーを JSON で返し、サーバーは終了コードと JSON を検証します。クラッシュ、不正応答、10 分のタイムアウトは API エラーとなり、タイムアウト時には標準ライブラリが子を kill して wait するため、長時間稼働するサーバーに Tk のモーダル状態が残りません。

HTTP サーバーは `ThreadingHTTPServer` です。picker を待つリクエストとは別に health や workspace を処理できます。一方、非ブロッキング lock により picker は全体で一つだけとし、二つ目には `409 picker_already_open` を返します。lock は成功、キャンセル、例外、クラッシュ、タイムアウトのすべてで `finally` により解放します。

`RootRegistry` はセッション中の選択済みルートと発見済み ID を保持し、children API は ID だけを受け取ります。ブラウザー指定の任意パスを読む API はありません。復元時だけ、以前保存したルートが現在も実在することを検証して再認可します。

## API

- `GET /api/health`: 稼働確認
- `POST /api/folders/select`: ネイティブ選択とルート認可（キャンセル時は `folder: null`）
- `GET /api/folders/children?id=...`: 認可・発見済みフォルダー直下のディレクトリ
- `GET /api/workspace`: 保存状態と、現時点で利用可能なルート
- `PUT /api/workspace`: 表示状態保存

サーバーは `127.0.0.1` のみに bind し、全リクエストの `Host`、状態変更の `Origin` を検証します。CORS は有効化しません。

## ワークスペース

JSON にはルートパス、ノード ID/親 ID/表示情報、座標、展開状態、viewport の pan/zoom を保存します。実ファイル階層とは独立しており、ユーザーファイルは変更しません。一時ファイルを書いてから置換します。欠損・不正 JSON・利用不能ルートは空状態または部分復元として扱います。

## 次の改善候補

実機利用後、最初に確認された操作上の摩擦を優先します。候補は、大規模フォルダーの遅延読み込み表示、保存エラーの状態表示、キーボード操作、ノード重なり回避です。破壊的ファイル操作を追加する前に認可モデルのハードニングと専用テストが必要です。
