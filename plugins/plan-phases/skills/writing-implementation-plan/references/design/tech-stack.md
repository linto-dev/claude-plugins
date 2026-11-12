# 技術の既定値

計画が新しい技術・ライブラリ・Cloudflare の機能・依存を足すとき、または既存の選び方から外れるときに読む。

## 目次

- 決めること・決めないこと / 依存の足し方 / 実行基盤 / データベース / ファイル・キャッシュ・状態 / 非同期処理と定期処理 / API / 認証 / フロントエンド / その他の Cloudflare の機能
- インフラのコード化 / CI/CD と検査 / テスト / 監視と運用 / 使わないもの / 見直す時期 / 計画に書くこと / CLAUDE.md に足す候補 / 依頼主に確かめること / 確認の問い

## 決めること・決めないこと

- 決める: 層ごとに使うものと使わないもの、選び分けの基準、依存の足し方、設計を変える製品の制約
- 決めない: 冪等・順序・互換性（データ）、表と列の変え方（テーブル）、検証と Result の書き方（コード）、秘密の値と認証の細部（セキュリティ）、テストの層（テスト）、記録と通知（観測）、分け方（領域）
- 版と製品の上限の値はここに書かない。npm と公式のドキュメントで今の値を確かめる

## 依存の足し方

- Cloudflare と TypeScript にそろえ、workerd でローカルに再現できるものを優先する。書き方はリポジトリに既にあるものに合わせる
- 各節で決めた道具を別のものに変えない。前提（国内保管、SSO、DB への直接の接続、利用者の数）が外れて変えるなら、既定値から外れる決定にする
- 汎用の小さな道具（日付・配列・文字列）は足さず、自前で書く。特定の用途の部品（例: PDF）は、既存の依存・自前の部品と重ならないときだけ足す
- 足す前に npm で今の版、保守の状況、既知の脆弱性を確かめ、修正済みの正式版を入れる。ベータ・RC と、出て 1〜2 か月の major は入れない。npm の `latest` がベータのことがあるので版を指定する
- 外部の依存は pnpm の catalog に集め、同じ系列は同じ版にそろえる。better-auth・alchemy・e2e はキャレット無しで固定する
- Cloudflare のベータの機能は、この文書が決めたものだけにし、止まっても業務が止まらない形にする

## 実行基盤

- Workers の Paid を使う。画面（SPA）と API を 1 つの Worker に載せ（Static Assets と `@cloudflare/vite-plugin`）、同じオリジンにして CORS を開けない
- compatibility date を明示して固定する（alchemy の既定値に任せない）
- CPU の上限を超える処理やネイティブのバイナリは Workers に載らない。Queue か Workflow で区切れなければ、既定値から外れる決定にする
- Worker を分けるのは、セキュリティの境界、要る上限（`limits.cpu_ms` は Worker 全体に効く）、API の利用者が複数、DO が中心、強い権限の運用処理、のどれかのときだけ。Service Binding でつなぎ、内部用は `workers_dev: false` と RPC entrypoint で閉じる
- 分ける線は契約だけを共有する所に引き、分けた Worker 同士で同期の呼び出しを連鎖させない。D1 を共有したまま分けても負荷と障害は分かれない（重い取り込みは Queue で絞る）

## データベース

- D1 を既定にし、対象ごとに順番を守る所だけ Durable Objects を足す
- PostgreSQL（Hyperdrive 経由）は次のどれかのときだけ
  1. 国内保管の保証が要る（D1・DO・R2 には日本を指定する管轄が無い）
  2. RLS や DB のロールが要件にある。または BI ツールなど Cloudflare の外から DB に直接つなぐ
  3. 分けられない 1 つの DB が数年で D1 の上限を超える（先に R2 への退避・テナントごとの DB・DO を比べる）
  4. 拡張や、主 DB での重い分析が要る
  5. 依頼主がインフラを指定している、または既存の PostgreSQL がある
- 設計を変える D1 の制約
  - 1 つの DB は読み書きを 1 件ずつ処理する。重い集計は、あらかじめ集計した表にする
  - `BEGIN` が無い。読んで判断して書くことは、`batch()` と条件付きの SQL（例: `UPDATE … WHERE version = ?`）か、DO の `transactionSync()` で書く
  - 1 文のバインド変数、UNION の数、LIKE のバイト数、結果の大きさに上限がある。日本語の部分一致は `instr()` で書く
  - 置き場所は作るときにしか選べない。`primaryLocationHint: "apac"` を付けて作る
  - Time Travel は DB 全体を戻す。RLS、ロール、外部からの接続、ICU、拡張は無い
  - export の間は他のクエリが止まるので、業務時間の外に置く。読み取りの複製を判断に使わない
- D1 のままで済む形: 採番は 1 文の `INSERT … SELECT COALESCE(MAX(…), 0) + 1`、ジョブの取り出しは Queues か 1 文の `UPDATE … RETURNING`
- DO は対象ごとに 1 つ作り（採番、在庫、予約枠、状態遷移）、SQLite 版にする。全体で 1 つの DO や時刻をキーにした DO に書き込みを集めない。対象をまたぐ検索は D1 への写しで行う
- 1 つのアプリで複数のテナントを持つなら、DB を分けるかを決める（復元が DB 全体に効き、RLS が無いので絞り込みの不具合が漏えいになる）。共有するなら `tenant_id` を複合索引の先頭に置き、アダプタで必ず条件を付ける

SQL とマイグレーション

- ORM を使わない。アダプタに SQL を書いて `env.DB.prepare(sql).bind(...)` で実行し、行は列を読む関数と `parse` で型にする（`all<T>()` で型を付けない）
- 値を SQL につなげない。`SELECT *` と、列を省いた `INSERT` を使わない。SQL は表の持ち主のアダプタに置く
- 可変の長さの一覧（IN、複数行の INSERT）は `json_each(?)` で 1 つの値として渡す
- 型を確かめたいときだけ、Kysely を SQL の組み立てだけに使う。`kysely-d1` は使わない
- マイグレーションは手書きの SQL を番号順に足し、コミットしたものは書き換えない。適用は `wrangler d1 migrations apply`（alchemy の `migrationsDir`）だけにする。ファイル名と先頭に表の持ち主を書く。`PRAGMA foreign_keys` は書かない
- PostgreSQL では Hyperdrive のキャッシュが書き込みで消えない。認証・権限・書いた直後の読み取りには、キャッシュを切った設定を使う

## ファイル・キャッシュ・状態

- ファイルは R2 に置き、ブラウザから署名付き URL（aws4fetch で署名）で直接 PUT させる。公開バケットに個人情報を置かず、保持の方針ごとにバケットを分ける。バージョニングが無いので、上書きしないキーにする
- KV は設定とキャッシュだけに使い、状態は D1 か DO に置く
- 大きなファイルをメモリに読まない。R2 から分けて読み、Queue か Workflow で区切る

## 非同期処理と定期処理

- 既定は同期。非同期にするのは、実行時間の上限、外部の速度制限、量の山、利用者を待たせたくない、のどれかのときだけ
- 時刻で起動: Cron（UTC）。起動だけにし、処理は Queue か Workflow に渡す
- 1 件ずつ独立に再試行: Queues。DLQ を必ず付ける。1 つの queue に consumer は 1 つ（複数の受け手には受け手ごとの queue）
- 段が複数で、待ち・順序・人の承認がある: 1 つの Workflow で指揮し、consumer を連鎖させない。名前はアカウント全体で一意なので stage を付ける
- 対象ごとのタイマー: DO の alarm
- 大きな本文は R2 に置き、キーを送る
- 利用者の操作を非同期にしたら、処理中・完了・失敗を保存して画面に出す

## API

- Hono を外枠にし、`/api/auth/*`（Better Auth）、`/rpc/*`（oRPC）、`/api/v1/*`（公開の REST。要るときだけ `@orpc/openapi`）、`/webhooks/*`、`/mcp`、`/.well-known/*` に分ける。すべて `run_worker_first` に並べる
- 業務の API は oRPC で契約を先に書く（`packages/contract`、依存は `@orpc/contract` と zod だけ）。エラーは型付きエラーにし、`ORPCError` に文字列を投げない。POST で呼ぶ
- Hono RPC は、自前の SPA だけが使う 20 本ほどまでの短命な試作で、MCP と外部への公開が無いときだけ
- zod は境界だけで使い、配列に `.max()` を付ける
- MCP は `@modelcontextprotocol/server` の `createMcpHandler` をリクエストごとに作り、Streamable HTTP だけにする（`McpAgent` と SSE は使わない）。`maxRequestBodySize`・`maxToolInputElements`・`expectedResource` を明示する

## 認証

- 既定は Better Auth（`database: env.DB`）。社員だけの社内ツールは Cloudflare Access（`Cf-Access-Jwt-Assertion` の JWT を自分で確かめる）。SSO・SCIM が求められるなら（依頼主や販売先の要件） WorkOS か Auth0
- Better Auth のスキーマは CLI（`--adapter kysely`）で SQL を出し、マイグレーションに足す（`/migrate` は使わない）。版を上げるときは、差分のマイグレーションを同じコミットに入れる
- Workers では `ipAddressHeaders: ["cf-connecting-ip"]` と `rateLimit` の `storage: "database"` を必ず書く。KV を `secondaryStorage` にしない
- パスワードを持たないログインを優先する
- MCP の認可も Better Auth で行い、クライアントの登録は CIMD にする（DCR を止める）。利用者の DB を持たない MCP 専用のサーバーは `@cloudflare/workers-oauth-provider`

## フロントエンド

- ログイン後の画面: Vite・React・TanStack Router の SPA。OGP が要る URL だけ HTMLRewriter で meta を差し込む
- 公開のコンテンツ: Astro の静的サイトを別の Worker にする
- 公開で URL ごとに動的で、検索での見え方が売上に効く: TanStack Start（SSR は要るルートだけ）
- 部品: TanStack Query・Form・Table、shadcn/ui（Base UI）と Tailwind CSS、Recharts。日付の計算は、日本時間だけなら自前、他のタイムゾーンなら date-fns
- Query は `staleTime: 30_000`、`refetchOnWindowFocus: false` にし、行ごとに query を呼ばない（D1 の読み取りを抑える）

## その他の Cloudflare の機能

- 使う: Email Service（認証メールと通知。送信の部分を差し替えられる形にする）、Turnstile（公開のフォームとログイン）、Images、Browser Run（帳票の PDF）
- Rate Limiting バインディングは近似値。厳密に止めるなら DO か WAF にする
- AI の呼び出しは AI Gateway を通し、本番で本文を記録しない
- Secrets Store、Flagship、Containers、K2 は既定では使わない

## インフラのコード化

- 既定は alchemy（`packages/infra/alchemy.run.ts`、stage は `dev`・`pr-<n>`・`prod`）。Worker が 1 つ、PR ごとの環境が要らない、運用をほかの人やチームに引き継ぐ、のどれかなら wrangler.jsonc だけにする
- 本番の D1 と R2 は `delete: false` にし、prod は CI からだけデプロイする
- Worker Previews では Workflow を共有し、Queue を consume できず、Cron と Service Binding が本番を向く

## CI/CD と検査

- GitHub Actions。アクションは commit SHA で固定し、`permissions: { contents: read }` にし、`pull_request_target` を使わない
- Cloudflare のトークンは用途ごとに分け、Cloudflare のアカウントをプロダクト（受託なら依頼主）ごとに分ける
- 検査は Biome（`biome ci`）、Knip、dependency-cruiser（層と境界）、`tsc`。規則を緩めない。dependency-cruiser に規則を足したら、違反を置いて発火を確かめる
- TypeScript は、型検査にネイティブ版を、ツール用に前の major を並べる（dependency-cruiser が対応するまで）
- Turborepo と pnpm。内部パッケージはビルドせず、`exports` で `src/*.ts` を指す。pnpm の設定は `pnpm-workspace.yaml` に書き、`minimumReleaseAge` を明示する
- コミットのフックは使わない

## テスト

- Vitest と `@cloudflare/vitest-plugin`（`cloudflareTest()` は統合の project だけ）、fast-check、Testing Library と jsdom
- プラグインは `nodejs_compat` を自動で足す。本番の設定にあるかを確かめる
- 偽のタイマーは R2・KV の模擬に効かない
- E2E は `e2e`（TesterArmy）で記録を再生する。本物の資格情報を使わない

## 監視と運用

- Workers Logs・Issues・Traces を使い、外の観測サービス（Sentry など）は既定で入れない
- `observability.issues.enabled` を設定に書く（書かないとデプロイで戻る）
- cron とバックアップの最後に healthchecks.io へ ping を送る。バックアップは Time Travel と R2 への毎日の export

## 使わないもの

- Next.js（新規）、Pages、Turso、PostgreSQL を既定にすること
- D1 での ORM と drizzle-kit、`kysely-d1`、Better Auth の `/migrate`
- Hono RPC を既定にすること、tRPC、ts-rest
- KV に状態を置くこと
- ESLint・Prettier、Jest、Cypress、MSW、Storybook、lefthook・husky
- ベータ・RC の major、cf CLI

## 見直す時期

計画を書くときに次が起きていたら見直し、変えるなら「決めたこと」に書く。

- alchemy・Hono・oRPC の次の major が正式版になった（oRPC は通信形式が変わる）
- dependency-cruiser が TypeScript の新しい major に、Dependabot が pnpm の新しい major に対応した
- D1 の読み取りの複製、Email Service の送信が GA になった

## 計画に書くこと

- README の「決めたこと」: 依存を足すたびに 1 行書く（比べた案に「自前で書く」と既存の依存を入れ、技術と業務の理由を書く）
- README の「決めたこと」: 既定値から外れる選択は「既定値から外れる」と書き、外れた前提と比べた既定値を書く（ADR の候補。ADR にするかは決定と学びの記録が決める）
- README の「開始前に人がすること」: Cloudflare のアカウントとトークン、秘密の値、メールの DNS、Access のポリシー
- 「前提」: npm で確かめた版、公式のドキュメントで確かめた上限の値と URL
- 「変更するファイル」: `package.json`・catalog・lockfile、IaC の定義、`run_worker_first`
- 「約束」: バインディングの名前
- 「作り方」: パッケージ名と版、設定の値（例: DLQ）
- 「テスト」: 製品の上限を超える件数のテスト（例: バインド変数の上限より多い一覧）
- 「push の後の確認」: ローカルで再現できない機能
- 「従う決まり」に写す例: 可変の長さの一覧は `json_each(?)` で 1 つの値として渡す

## CLAUDE.md に足す候補

- 依存は計画書に書いたものだけを、catalog に版を固定して足す
- D1 の SQL は `prepare().bind()` で書き、`all<T>()` で型を付けない。可変の長さの一覧は `json_each(?)` で渡す
- マイグレーションは手書きの SQL を新しい番号で足し、コミットしたものを書き換えない

## 依頼主に確かめること

- 国内保管の保証が要るか
- BI ツールなどが DB に直接つなぐか、DB の機能で権限を分ける要件があるか。指定のインフラや既存の DB があるか
- 使う人は社員だけか。SSO や SCIM が求められるか
- 数年で溜まるデータの量
- 作った後の運用を誰が持つか（ほかの人やチームに引き継ぐか）
- 公開のページの検索での見え方が売上に効くか
- メールを送るドメインの DNS を誰が設定するか

## 確認の問い

- 足す依存ごとに、重ならない理由と比べた案が「決めたこと」にあり、計画書に版が書かれているか
- 既定値から外れる選択に、外れた前提が書かれているか
- DB の選択が、D1 と PostgreSQL を分ける条件で説明されているか
- 読んで判断して書く処理の原子性が、`batch()` か DO で保たれているか
- 行の数で増えるバインド変数が、上限を超える件数で試されるか
- 重い集計や取り込みが、同じ D1 の他の処理を待たせないか
- DO のキーが対象ごとで、書き込みが 1 つのオブジェクトに集まらないか
- 非同期の仕組みの選び方が用途に合い、失敗が DLQ か画面の状態で見えるか
- Worker を分けるなら条件のどれに当たり、1 つの変更が複数の Worker にまたがらないか
- 新しい API の形（oRPC・REST・MCP・webhook）が使う側に合い、パスが `run_worker_first` にあるか
- 認証の方式が使う人（社員・取引先・一般）に合うか
- 画面の作り方が画面の性質（ログイン後・公開・検索）に合うか
- preview で本番を向く機能や、ローカルで再現できない機能の確かめ方が書かれているか
- IaC の変更が、本番のデータを消す操作や PR からの本番の変更を許していないか
- CI や静的検査の規則を緩めていないか
