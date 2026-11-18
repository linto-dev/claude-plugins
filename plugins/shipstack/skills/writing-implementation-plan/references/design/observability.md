# 観測の設計の決まり

新しい入口（HTTP・キュー・cron・Workflow・DO の alarm・webhook・MCP のツール）、外への呼び出し、AI の呼び出し、ブラウザのエラー、通知を足すか変えるときに読む。

## 目次

決めること・決めないこと / 道具と設定 / 処理の単位ごとに 1 つのイベント / 語彙と重さ / 記録しないもの / つなぐ ID / AI の呼び出し / ブラウザのエラー / 知らせる / SLO / 調べる・長く残す・守る / 計画に書くこと / CLAUDE.md に足す候補 / 依頼主に確かめること / 確認の問い

## 決めること・決めないこと

- 決めること: イベントと属性、語彙と重さ、記録しないもの、つなぐ ID、AI とブラウザの観測、知らせる条件、SLO、長く残すものの置き場
- 決めないこと: 個人情報の分類と保存の期間（データ）、Err の `kind` の名前（領域）、Err と例外の型（コード）、監査の中身と事故の対応（セキュリティ）、製品の選び方（技術の既定値）

## 道具と設定

- Cloudflare の中で完結させる: Workers Logs・Traces・Issues、AI Gateway、Web Analytics、手元は Local Explorer。外の観測サービス（Sentry、Langfuse など）、OpenTelemetry の SDK と外への書き出し、Tail Workers は使わない。
- サンプリングしない（先頭で決める方式しか無く、エラーも同じ割合で消える）。ログとトレースは 7 日で消える前提で設計する（今の値は公式のドキュメントで確かめる）。
- Worker の `observability` は全項目を書く: `enabled`、`redact_query_string`、`issues.enabled`、`logs.invocation_logs` を true、`logs` と `traces` の `head_sampling_rate` を 1、`traces.enabled` を true。書かない項目はデプロイで既定に戻る。プレビューは `issues.enabled: false`。IaC の型に無いキーは型を広げて渡し、デプロイの後に有効なままかを確かめる。

## 処理の単位ごとに 1 つのイベント

- 単位: HTTP の 1 リクエスト、キューの 1 メッセージ（batch ではない）、cron の 1 回、Workflow の 1 ステップ、DO の 1 回の alarm、webhook の 1 回の受け取り、MCP のツールの 1 回の呼び出し。
- 入口の最上位の境界が、単位ごとに属性の多いイベントを 1 つ組み立て、成功も失敗も最後に 1 回だけ出す。`main: true` を付ける。
- 外への呼び出しは 1 回ごとのイベントにせず、回数と時間を単位のイベントに載せる（1 回ごとの流れは Traces の自動のスパンで見る）。AI だけは `ai.call` を 1 回ごとに出す。
- 出口の関数は 2 つ（例: `packages/telemetry`）: `emit(重さ, 出来事, 属性)` と、`{ set, end(outcome, errorType?) }` を返す `startUnit(出来事, 基本の属性, now)`。境界は `finally` で `end` を呼ぶ。ユースケースはテレメトリを呼ばず、載せる値を返り値で返す。`console` にはオブジェクトを渡す。
- 時間は I/O の後で測る（Workers の時計は I/O が無いと進まない）。
- `outcome`: `ok`（info）、`rejected` = ドメインの Err（info。`error.type` に Err の `kind`）、`failed` = 想定外の例外・5xx（error）。

| 単位 | 属性（OpenTelemetry の名前があればそれ、無ければ `app.`） |
| --- | --- |
| すべて | `main`、`event`、`outcome`、`duration_ms`、`error.type`、`exception.type`、`request.id`、`tenant.id`、`user.id`、`service.version`（git の SHA）、`deployment.environment.name`、`app.d1.query_count`、外部サービスごとの回数と時間、テナントごとの機能の切り替えの値 |
| HTTP | `http.request.method`、`http.route`（実際の path ではない）、`http.response.status_code` |
| キュー | `messaging.destination.name`、`messaging.message.id`、`app.queue.attempts`、`app.queue.dwell_ms`、`app.queue.result`（`ack` / `retry`） |
| cron・Workflow | 予定の時刻と処理・失敗の件数。Workflow の名前・インスタンスの ID・ステップの名前 |
| webhook | 相手の名前、相手のイベントの ID、種類、重複か、署名の検証の結果 |
| MCP | ツールの名前、ツールの結果（`ok` / `invalid_args` / `denied` / `error`。`outcome` とは別のキー）。引数は載せない |

## 語彙と重さ

- 出来事の名前と属性のキーを 1 つの型のファイルで決める。語彙に無いキーと個人情報の型（`Sensitive`）は型エラーにする。値は文字列・数・真偽値だけ。語彙に合うかのテストは書かない。
- JSDoc に意味と、その失敗が利用者に見えるか（一次対応の Claude が急ぎを決める）を書く。監査の記録の出来事の名前も同じファイルでそろえる。
- 名前: ドット区切り、各部分は snake_case、単位は後ろ（`_ms`）。1 つの概念にキーは 1 つ。名前に ID や変わる値を入れない。

| 重さ | 場面 | どうなるか |
| --- | --- | --- |
| error | 想定外の例外。利用者に見える失敗。請求や利用量の記録の欠け。再試行を使い切った。見回りが見つけた滞り | Workers Issues → Claude の一次対応 → Discord |
| warn | 自動で戻る一時的な失敗（再試行の 1 回ごと）。縮退して動いた | 記録だけ |
| info | 単位の記録（`ok` と `rejected`） | 記録だけ |

- ドメインの Err を error にしない。迷ったら error にする。
- 再試行する失敗は試すたびに warn、使い切ったときだけ error。キューの `retry` の単位は warn にし、最後の試行の失敗だけ error（`end` に重さを上書きする引数を持たせる）。外部の LLM のタイムアウトも同じ扱い。
- `message` は語彙だけで作る（`<event>: <error.type>`）。Issues は `message` の違いで分かれる。

## 記録しないもの

ログは Claude（Anthropic）と社内の Discord に渡る前提で扱う。

- 値は ID・数・真偽値・決まった値の一覧だけ。名前、連絡先、住所、本文（問い合わせ・会話・文字起こし・AI のプロンプトと応答）、アップロードしたファイルの名前、URL のクエリを載せない。
- 例外のメッセージとスタックは、消し込みの関数（トークン、API キー、メールアドレス、長い 16 進と base64）に通してから `exception.*` に載せる。外部のライブラリと SQL の例外のメッセージをそのまま載せない。
- 個人情報を URL・path・ヘッダー（DO への呼び出しを含む）に入れない（トレースとログに残る）。
- 外部の識別子（外部サービスの利用者 ID、電話番号）もそのハッシュも使わず、内部の ID でつなぐ。
- D1 の SQL には値を `?` で渡す。
- Workflow の状態に個人情報を含むなら `default_retention` で短くする（重複を拒む期間も短くなる）。

## つなぐ ID

- `request.id` をすべてのイベントに載せ、キューのメッセージ・Workflow の引数・outbox の行で運んで受け手のイベントに載せる（トレースは Queue と Workflow をまたがない前提）。
- 最上位の境界でトレースの ID を、エラーの応答と `x-trace-id` に入れる。画面のエラーには問い合わせ用の参照コードを出す。
- webhook は受け取ったところで新しい ID を作り、相手のイベントの ID も載せる。
- 複数の手順の AI の処理は、全体の ID を各 `ai.call` に載せ、最後に全体の結果を 1 つのイベントにする。

## AI の呼び出し

- すべて AI Gateway を通す。アプリと環境ごとに 1 つ。プレビューは 1 つを共有し、メタデータの `env` で分ける。
- 本番は `cf-aig-collect-log-payload: false`（本文を残さない。正本は D1）。Workers AI のバインディングで本文だけを切れるかは公式のドキュメントで確かめ、それまで個人情報を扱う機能は `gateway.collectLog: false`。
- メタデータは ID だけ（リクエスト、テナント、機能、プロンプトの版、環境。数の上限は公式のドキュメントで確かめる）。
- 応答の `cf-aig-log-id` を D1 の出力の行と `ai.call` に残す。
- 再試行は 1 か所。キューや Workflow が再試行するなら `cf-aig-max-attempts: 1`。
- キャッシュ、Guardrails、DLP、Evaluations、Log classification、gateway の Logpush と OpenTelemetry の書き出しは使わない。自分の鍵なら `byok_only` を有効にする。
- `ai.call` の属性: `gen_ai.provider.name`、`gen_ai.request.model`、`gen_ai.usage.input_tokens` / `output_tokens`、`duration_ms`、`app.ai.ttft_ms`、`app.ai.feature`、`app.ai.prompt_version`、`app.ai.output_id`、`app.ai.validation`（`ok` / `parse_failed` / `domain_invalid`）、`app.aig.log_id`、`app.ai.cost_micro_usd`、`app.ai.price_version`。再試行と使わなかった結果も 1 回と数える。
- 費用はトークン数と単価の表の版で残す。単価の表は D1 に追記だけで置き、表に無いモデルを使う変更は CI で止める。
- 利用者の反応（評価、作り直し、直したか）は出力の ID と一緒に D1 に置く。
- gateway の支出の上限を遮断器にする（gateway ごとの月、テナントごとの日）。

## ブラウザのエラー

- 自分の受け口（例: `POST /api/client-errors`）で受ける。エラー境界・`window.onerror`・`unhandledrejection` を、1 ページ 5 件まで・重複なし・自分のオリジンのフレームだけ・文字列と 4 桁以上の数字を伏せて、`sendBeacon`（`text/plain`）で送る。
- 受け口は常に 204、大きさと IP ごとの回数（DO で数える）を制限し、もう一度消し込む。
- error の行にはこちらが決めた値（出来事、画面の種類、捕まえ方）だけ。送り手の値（メッセージ、フレーム）は warn の行に分ける（誰でも Issue を増やせないように）。
- 表示の速さは Web Analytics（CSP に `static.cloudflareinsights.com`）。主な 2〜3 の道筋は `ui.flow.started` / `completed` / `failed` を同じ ID で出す。

## 知らせる

- 知らせるのは、利用者に見える症状と、直し方の決まった既知の問題（DLQ、outbox の滞り、cron の停止、外から見えない）だけ。自然に戻ったものと CPU などの原因の候補は知らせない。
- Worker ごとに Issues の Automations を 2 つ（A1: 発生が 1 回を超えた、A2: 24 時間止んでいた Issue の再発）作り、送り先を Claude Code の routine にする（Discord に直接送らない）。
- cron と死活は Cloudflare の外で見る。healthchecks.io の ping は cron が最後まで動いたときだけ送る。`/health` は D1 に `SELECT 1` を流してから 200。
- DLQ は見回りの cron で `metrics()` の `backlogCount` が 1 以上なら error。outbox は最も古い未配信の行が決めた時間を超えたら error。
- 割合や件数の条件は Monitors（ベータ。今の状態を確かめる）。結果の行が無いと鳴らないので、0 件は見張れない。
- プロダクトの運用の事実（アカウント、Worker、主な道筋、通知の相手）は `docs/ops/oncall.md` に置く。

## SLO

- SLI は主な道筋（1〜3）の単位のイベント（`main: true`）の成功の割合。悪い: `failed`・5xx・決めた時間を超えた応答。良い: `ok` と `rejected`。窓は 30 日。
- 知らせるのは「直近 1 時間の失敗の割合 × 次の 4 時間の見込み件数 ≧ 残りの枠」かつ「直近 1 時間に 10 件以上、失敗 2 件以上」のときだけ。それ以外は週ごとのまとめ。
- 毎日の cron で `slo_daily(date, sli, good, total)` を D1 に書き、13 か月残す。

## 調べる・長く残す・守る

- 本番の分布を問い合わせてから、タイムアウト・ページの大きさ・一度に処理する件数を決める。
- デプロイの後は `service.version` で分けて前の版と比べる。テナントごとの機能の切り替えは D1 に置く（割合での段階的な公開はしない）。
- 本番を調べる AI は Cloudflare API の MCP サーバーに OAuth の読み取りの権限だけでつなぐ。一時的な詳しいログは許可したテナントだけに出し、分かったら消す。
- 7 日より長く要るもの: 監査と AI の出力は D1（期間は業務で決める）。自分で決めた数は Analytics Engine、ログは Logpush で R2（要るときだけ）。
- Biome の `suspicious/noConsole` を error にし、出口の関数だけを例外にする。
- 段階: 開発中と本番はすべて。保守だけの段階は Issues の一次対応・死活・healthchecks.io・Budget alerts と、月ごとの SLO のまとめ。イベントと記録しないものの決まりはどの段階でも守る。

## 計画に書くこと

- 「従う決まり」: このフェーズに当たる上の決まりを、今のリポジトリの名前で写す（例: 「`queue.message` は 1 メッセージに 1 回。`retry` は warn、最後の試行の失敗だけ error」）。
- 「約束」: 出来事の名前、通知と SLO が頼る属性のキーと型、AI なら D1 に残す列。
- 「作り方」: 出す境界、どの Err を `rejected` にするか、何回目から error か、運ぶ ID、AI なら gateway のヘッダー、見回りと ping、新しい Worker の `observability`、`docs/ops/` に足す行。
- 「テスト」: 通知になるログを組み立てる関数（消し込み、ブラウザのエラーの 2 行）の単体テスト。通知と SLO が頼るイベントが出ることを既存の統合テストで 1 か所。
- 「完了の条件」: 手元で入口を 1 回呼び、Local Explorer でイベントが 1 件だけ出て属性がそろうことを確かめる問い合わせ。
- 計画の README: 「開始前に人がすること」に Automations の接続、healthchecks.io の check、gateway と支出の上限。「決めたこと」に既定から外れる判断（サンプリング、外への書き出し、本文を残す）。
- 機能の PR の「マージの後に行うこと」: 本番で意図どおりかを `service.version` で分けて確かめる問い合わせ、Issues と `redact_query_string` が有効なままかの確認。

## CLAUDE.md に足す候補

- ログは出口の関数（`emit` / `startUnit`）だけで出す。`console` を直接使わない。
- 属性と出来事は語彙の型にあるものだけ。足すときは JSDoc に意味を書く。
- 値は ID・数・真偽値・決まった値だけ。本文・名前・URL のクエリを入れない。例外は消し込んでから載せる。
- ドメインの Err は error にしない。再試行は使い切ったときだけ error。`message` に自由な文を入れない。
- AI の呼び出しは AI Gateway を通し、本番は `cf-aig-collect-log-payload: false`。

## 依頼主に確かめること

- 主な道筋（1〜3）と、可用性や応答の時間の数字を約束するか（約束するなら月ごとに報告する）。
- 対応する時間帯と、急ぐものの範囲（データの欠け、請求の誤りなど）。
- 監査の記録と AI の出力を残す期間。
- AI の費用の上限（月、テナントごとの日）。
- 依頼主との取り決め（受託なら契約）や法令が、記録の長い保存や外への書き出しを求めるか。個人情報を除いたログが一次対応で Anthropic に渡ってよいか。

## 確認の問い

- 新しい入口ごとに、イベントを出す境界、出来事の名前、通知と SLO が頼る属性が計画書にあるか。
- どの Err を `rejected` にし、再試行の何回目から error にするかが決まっているか。
- その機能で扱う個人情報と本文が、属性・URL・ヘッダー・例外のメッセージのどこにも出ない形になっているか。
- 非同期に渡す先（キュー・Workflow・outbox）へ `request.id` を運ぶ形が書いてあるか。
- AI の呼び出しの gateway のヘッダー（本文、メタデータ、再試行の回数）と、D1 の出力の行に残す列が決まっているか。
- 新しい cron・キュー・outbox が止まったり滞ったりしたとき、知らせる仕組みがあるか。
- 新しい Worker の `observability` の設定と Automations の接続が、計画のどこかにあるか。
- 主な道筋が変わるとき、SLI の数え方と `docs/ops/oncall.md` が直るか。
- 通知と SLO が頼るイベントが出ることを確かめるテストがあるか。
- 本番で意図どおりかを確かめる問い合わせが「マージの後に行うこと」にあるか。
- 本番の分布を見ずに決めた値（タイムアウト、件数）を、見立てと書いているか。
