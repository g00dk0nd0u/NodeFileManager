# NodeFileManager

NodeFileManager は、実際のファイルシステムをグラフィカルなワークスペースで扱うための Windows 向けプロジェクトです。現在は製品機能を持たない、アーキテクチャ確認用の最小基盤です。

## 必要環境

- Python 3.14
- Microsoft Edge などのブラウザー

**Node.js、npm、pnpm、yarn は不要です。** 外部 Python パッケージも使用しません。

## 起動

1. Python 3.14 を社内 Software Center から導入します。
2. リポジトリの `scripts\start.cmd` をダブルクリックするか、コマンドプロンプトから実行します。
3. ブラウザーで <http://127.0.0.1:8000/> を開きます。
4. 終了するにはサーバーのウィンドウで `Ctrl+C` を押します。

`start.cmd` は `py -3.14` を優先し、利用できない場合は `python` を試します。パッケージのインストールやビルドは行いません。

## アーキテクチャ

- `frontend/`: HTML5、CSS、ネイティブ ES Modules のみで構成する UI
- `backend/`: Python 標準ライブラリによる localhost 専用 HTTP/JSON API、将来のファイルシステム処理と SQLite 永続化
- `scripts/`: Windows 用起動スクリプト
- `docs/`: コンセプト、責務分離、ロードマップ
- `tests/`: 将来のバックエンド／フロントエンドテスト

詳細は [architecture.md](docs/architecture.md) を参照してください。

## 現在の状態

サーバーは静的フロントエンドと `GET /api/health` のみを提供します。ファイルの走査・変更、ノード表示・編集、ワークスペース保存は未実装であり、Phase 0 にも着手していません。
