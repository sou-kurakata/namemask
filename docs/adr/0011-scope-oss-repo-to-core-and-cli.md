# ADR-0011: このリポジトリの範囲をコア＋CLIに限定し、レビューUIとデスクトップアプリを別プロジェクトに分離する

- **Status**: Accepted
- **Date**: 2026-07-30

## Context

旧プロトタイプ（private・`../archive`）には次の3層が同居していた。

1. コア＋CLI: `src/namemask/`（検出パイプライン・`api.py`・`cli.py`・`review.py`）と
   `tests/`（golden corpus 99ケース、recall 97.7% / precision 1.00）
2. ローカルレビューUI: `src/namemask/server/`（FastAPI）と `frontend/`（React + vitest）
3. Windows デスクトップアプリ: `desktop.py`（pywebview）`devserver.py`
   `packaging.py` `namemask.spec` `scripts/*.ps1`（PyInstaller onedir）

OSS 公開（v0.1.0）に際して、どこまでを公開リポジトリに含めるかを決める。
決定の時点で分かっていた事実は次のとおり。

- 2 と 3 は社内運用に密着している。UNC パス上の `clients.csv`、
  情シスによる配布、Windows 前提のスクリプト。外部の利用者にそのまま移植できない。
- CLI 利用者から 2 への到達経路が無い。`namemask serve` は未実装で、
  `cli.py` にサブコマンドが無い。つまり `pip install namemask` した人が
  server を起動する手段が存在しない。
- レビューは 2 が無くても成立する。`review.py` が出力する `--html` は
  外部CDN・外部JSを参照しない自己完結HTML（不変条件11）で、
  人間レビューの要件を単体で満たしている。
- 2 を同居させると恒久的な保守が増える。npm の CI、Node バージョン追従、
  React のメジャー移行、vitest の維持。いずれも `pip install namemask` の
  達成には寄与しない。
- 3 の存在がコアを歪めた実績がある。`paths.py` の `sys.frozen` 分岐は
  PyInstaller のためのものであり、コア単体には不要な複雑さ（ADR-0008）。
- ADR の内訳が範囲を示している。プロトタイプ期に記録した設計判断
  （ADR-001〜007 と ADR-101〜121）の計 28 本のうち、コアに関するものは 9 本
  （ADR-001〜007 と ADR-106 / 107）。残る 19 本は server / UI / desktop
  （pywebview 採用、Host・Origin・token 検証、remask アルゴリズム、
  セッション TTL、UI reducer、exe 名 …）。
- 社内パイロットは v0.1.0 の成果物で行う方針（`CLAUDE.md` §3 D2）。
  つまりデスクトップアプリのコードは捨てるのではなく、別の場所で生かす必要がある。

## Options considered

### (A) 3層すべてを同一の公開リポジトリに置く

- 利点: コードの移動が不要。UI とコアを1コミットで同時に変更できる。
  デスクトップアプリという「完成品」を OSS の主役として見せられる。
- 欠点: Python + Node の二重 CI を初版から背負う。Windows CI・WebView2・
  PyInstaller の保守が公開リポジトリの義務になる。外部利用者に移植できない
  社内運用の前提（UNC パス・情シス配布）が公開コードに残る。
  UI 側の要求でコアを改修する圧力に対して、構造的な歯止めが無い（不変条件12）。

### (B) server だけ同居させ、frontend を外す

- 利点: Node の CI を避けつつ HTTP API を提供できる。
- 欠点: UI のない HTTP API の使い道を説明する負担が増える。
  この API は UI のために作られたもので、単体の設計として正当化されていない。
  server を維持しながら、その唯一の消費者が別リポジトリにあるという
  ねじれた依存が残る。

### (C) コア＋CLI だけを公開し、UI とデスクトップを別リポジトリ `namemask-app`（private）に置き、`namemask` を PyPI 経由で依存させる

- 利点: 公開リポジトリの成果物が `pip install namemask` → `namemask mask` の1本に絞れる。
  CI が Python だけで済む。リポジトリ境界が不変条件12（外部ツールの都合でコアを
  改修しない）を物理的に強制し、アプリ側からコアを直せない。
  社内運用に密着した部分を private に置いたまま、コアだけを公開できる。
- 欠点: コアの変更を UI に反映するには PyPI リリース（またはローカル editable install）
  が要る。2リポジトリの調整コストが発生する。UI 側の機能（`remask`）が OSS 側に無い。

### (D) コアだけを公開し、UI とデスクトップのコードは破棄する

- 利点: 保守対象が最小。
- 欠点: 社内パイロット（`CLAUDE.md` §3 D2）の手段を失う。
  動作実績のある UI を作り直すことになる。破棄する理由が無い。

## Decision

**(C) を採用する。** このリポジトリの範囲は検出エンジン + CLI のみとし、
`frontend/` `src/namemask/server/` `desktop.py` `devserver.py` `packaging.py`
`namemask.spec` `scripts/*.ps1` と対応テスト（`test_server.py` `test_desktop.py`
`test_packaging.py`）は持ち込まない。それらは別リポジトリ `namemask-app`（private）に置き、
`namemask` を PyPI 経由の依存として使う。

判断の根拠は4つ。

1. CLI 利用者から到達できないものを公開リポジトリに置かない。
   `namemask serve` が無い以上、server は `pip install namemask` した人にとって
   デッドコードである。公開物の一部が誰からも到達されないのは設計の誤り。
2. npm CI と Node 追従の保守を初版で背負わない。これは v0.1.0 の目的
   （`pip install namemask` が動くこと）にまったく寄与しない。
3. レビューは依存ゼロの `--html` で満たせる。UI が無いことで失われる
   本質的な能力が無い（`remask` を除く。下記トレードオフ参照）。
4. リポジトリ境界が不変条件12 を物理的に強制する。「UI の都合でコアを
   改修しない」を規律や記憶に頼らず、構造で担保できる。これが (A) との最大の差。

却下理由:

- **(A)**: 歯止めが無いことが決定的。旧プロトタイプで実際にコアが歪んだ
   （`sys.frozen` 分岐）実績があり、同居はその圧力を維持する選択になる。
   加えて、外部利用者に移植できない社内前提のコードを公開する意味が無い。
- **(B)**: UI のない API は正当化できない。API は UI のために作られたもので、
   単体の利用者像を説明できない。「使い道を説明する負担」を初版で背負う理由が無い。
- **(D)**: 動くものを捨てる理由が無い。パイロットの手段も失う。

## Consequences

- このリポジトリに FastAPI / React / PyInstaller のコードを持ち込まない。
  `CLAUDE.md` §1 §4 に範囲として明記し、§3 の判断基準
  （「これは検出エンジン + CLI の要求か、アプリの要求か」）と対応させている。
  アプリ側の要求は `namemask-app` の issue にする。
- `pyproject.toml` の `[project.optional-dependencies]` に `web` / `desktop` extra を
  置かない（同ファイルにコメントで理由を記録）。`ner` / `llm` / `crypto` は
  コアの optional 層なので残る。
- **受け入れたトレードオフ**:
  - `remask`（誤検出の解除・手動追加）が OSS 側に無い。UI 側の機能であり、
    CLI からは `--html` によるレビューまでで、そこから先の対話的な修正はできない。
  - server / UI / desktop の ADR 19本が OSS の資産にならない。
    参照が必要なときは旧フォルダ（`../archive`）を見る。`docs/adr/README.md`
    末尾に「別プロジェクトにある ADR」として一覧だけ残した。
  - コアの変更を UI に反映するには PyPI リリース（または editable install）が要る。
- `paths.py` の `sys.frozen` 分岐の去就はこの ADR では決めない。
  PyInstaller を使うのはアプリ側だが、分岐自体は無害で、同じ `paths.py` を
  アプリ側が使える利点がある。別途決定し、ADR-0008 に追記する。
- 旧フォルダ（`../archive`）を消さない。`frontend/` `server/` `desktop.py` は
  そこにしか存在しない。`namemask-app` の作成は v0.1.0 の公開後に行う。
- **見直し条件**: `namemask serve` の需要が issue で確認できたら、v0.2.0 で
  再統合を検討する。判断基準は根拠1と同じで、「CLI 利用者から到達できる形
  （= `namemask serve` サブコマンドとして実装される）になるか」。
  ならないなら、それは依然としてアプリ側の要求である。
  再統合する場合でも、frontend を同居させるか（根拠2の保守コストを払うか）は
  別途判断し、この ADR を改訂する。
