# meisai-checker コードレビューレポート

**対象リビジョン**: 2026-07-27 時点の `main` ブランチ  
**調査範囲**: `meisai_checker/` 配下の全 Python ファイル、`mcp_server.py`、`tests/`

---

## 高（致命的バグ）

### H-1 `mcp_server.py` 300行・338行 — `_dump()` に余分な引数 → TypeError

**場所**: `meisai_checker/mcp_server.py` 300行、338行

`_dump()` は `obj` を 1 引数だけ受け取る関数として定義されている（32〜36行）。

```python
# 定義（32〜36行）
try:
    from pytoony import json2toon
    def _dump(obj):
        return json2toon(json.dumps(obj, ensure_ascii=False))
except ImportError:
    def _dump(obj):
        return json.dumps(obj, ensure_ascii=False, indent=2)
```

しかし `patent_check_m8`（300行）と `patent_check_m9`（338行）は 3 引数で呼んでいる。

```python
# 300行（patent_check_m8）
return _dump({...}, ensure_ascii=False, indent=2)   # TypeError

# 338行（patent_check_m9）
return _dump({...}, ensure_ascii=False, indent=2)   # TypeError
```

`pytoony` 導入済み環境では `json2toon` ベースの `_dump` が選ばれ、未導入環境では `json.dumps` ベースが選ばれるが、**どちらも 1 引数のみ**なので、両ツールは呼び出されるたびに必ず TypeError で落ちる。

**修正提案**: 余分な `ensure_ascii=False, indent=2` を削除する。

---

### H-2 `meisai_checker/patent/anaphora.py` 130行 — `pos1` フィールドの誤用

**場所**: `meisai_checker/patent/anaphora.py` 130行

```python
if t['pos1'] == '名詞' and len(t['surf']) >= 2:
```

`_tokenize()` が返すトークン dict において `pos` が品詞のトップレベル（名詞／動詞等）、`pos1`〜`pos3` は下位分類（細分類）にあたる。unidic-lite では `pos1` に入るのは「普通名詞」「固有名詞」などの細分類であり、`pos1 == '名詞'` は**常に False**になる。この関数は名詞の末尾を見つけることができず、常に `None` を返す。

**修正提案**: `t['pos1']` → `t['pos']` に変更する。

---

### H-3 `meisai_checker/analyzer.py` 178〜220行 — 広範な例外抑制

**場所**: `meisai_checker/analyzer.py` 178行、191行、198行、216行

M7・M8・M9・G1 の各チェックブロックが `except Exception: issues = []` で全例外を握りつぶしている。

```python
try:
    from .patent.ambiguity import check_ambiguity
    m7_issues = check_ambiguity(claims) + ...
except Exception:       # ← ImportError・AttributeError・TypeError 等を全て無視
    m7_issues = []
```

MeCab 障害・実装バグ・設定ミスなど実際のエラーが完全に隠蔽され、チェック結果がゼロ件として返るため、デバッグが極めて困難になる。

**修正提案**: `except Exception` を `except ImportError` に絞るか、少なくとも `logging.exception()` でエラーを記録する。本番でも例外を握りつぶすなら、その意図をコメントで明示する。

---

### H-4 `meisai_checker/tokenizer.py` 20行 — インポート時の MeCab 初期化失敗

**場所**: `meisai_checker/tokenizer.py` 20行前後

```python
_tagger = fugashi.GenericTagger(...)   # モジュールトップレベル
```

MeCab / unidic-lite が未インストールの環境でこのモジュールを `import` するだけで RuntimeError が送出される。tokenizer は analyzer.py から無条件にインポートされるため、**パッケージ全体がロード不能**になる。

**修正提案**: `_tagger` の初期化を遅延（`_get_tagger()` のような関数に包んで初回呼び出し時に生成）するか、モジュールレベルを `try/except` で保護して `_tagger = None` にフォールバックし、実際のトークナイズ時に ImportError を再送出する。

---

## 中（動作に影響するバグ・設計問題）

### M-1 `meisai_checker/mcp_server.py` 66行 — `_make_summary()` が m7〜g1 を集計しない

**場所**: `meisai_checker/mcp_server.py` 66行

```python
for mid in ('m2', 'm3', 'm4', 'm5', 'm6'):   # m7/m8/m9/tc/g1 が漏れている
```

`patent_check_summary` の返却値 `summary.error_count` / `warning_count` には m7・m8・m9・tc・g1 のカウントが含まれない。また `patent_check_issues` の `milestone` パラメータも `m2`〜`m6` しか受け付けない（138行）。導入された M7〜G1 チェックが MCP 経由では事実上参照できない。

**修正提案**: `for mid in ('m2', 'm3', 'm4', 'm5', 'm6', 'm7', 'm8', 'm9', 'tc', 'g1')` に拡張し、`_MS_LABELS` と `milestone` のバリデーションも合わせて更新する。

---

### M-2 `meisai_checker/patent/anaphora.py` 541行 — キャッシュ引数の渡し忘れ

**場所**: `meisai_checker/patent/anaphora.py` 541行（前後の文脈と要照合）

412行では `_bare_claims_tokenized(noun, anc_body_toks, claim_defined_nouns=cache)` とキャッシュを渡しているが、別の呼び出しパスの 541行では `_bare_claims_tokenized(noun, anc_body_toks)` とキャッシュを渡していない。結果として同一請求項のトークナイズが重複して走り、パフォーマンスが劣化する。

**修正提案**: 541行の呼び出しに `precomputed_defined=cache` を追加する。

---

### M-3 `meisai_checker/patent/anaphora.py` `build_noun_groups()` 内 — 重複トークナイズ

**場所**: `meisai_checker/patent/anaphora.py` `build_noun_groups()` 関数内のネストループ

```python
for r in ref_hits:
    ...
    _tokenize(claims.get(r['claim'], ''))   # 同じ claim_num が複数 ref_hit に現れるたびに再実行
```

`ref_hits` の中で同一請求項番号が複数出現するたびに `_tokenize()` が走る。`_tokenize()` は MeCab を呼ぶため、請求項数×前記出現数のスケールで無駄なコストが生じる。

**修正提案**: `{claim_num: tokens}` の辞書をループ前に一度作成してキャッシュする。

---

### M-4 `meisai_checker/patent/fugo.py` 714行 — `list.index()` による誤トークン参照

**場所**: `meisai_checker/patent/fugo.py` 714行前後

```python
tokens.index(last_tok, i)
```

`list.index()` は **等値比較（`==`）** で検索するため、同じ表層形・品詞を持つ別のトークンオブジェクトを誤って指すことがある。特に「の」「を」「は」等の高頻度語が繰り返す文では誤マッチが起きやすい。

**修正提案**: オブジェクト同一性（`is`）で探す `next(j for j, t in enumerate(tokens[i:], i) if t is last_tok)` に置き換えるか、インデックスを直接追跡する設計に変更する。

---

### M-5 `meisai_checker/patent/fugo.py` 1108行 — パターン選択ロジックの漏れ

**場所**: `meisai_checker/patent/fugo.py` `_parse_fugo_setsumeisho()` 関数内

```python
if not pairs:
    # Pattern②③ を試みる
```

Pattern①④ で何も取れなかった場合のみ Pattern②③ を試みる排他的な構造になっており、①と②が混在する書き方（例：一部は「符号　要素名」形式、別の箇所は「要素名（符号）」形式）を処理できない。

**修正提案**: `if not pairs:` による排他を廃止し、両パターンを常に試みて結果をマージする。あるいは段落ごとにパターンを独立して適用する。

---

### M-6 `meisai_checker/patent/support.py` 268行 — 動詞ステム除去の脆弱性

**場所**: `meisai_checker/patent/support.py` 268行前後

```python
_find_clause(body, verb[:-1])   # 最後の1文字を削除してステムとする
```

「する → す」「ある → あ」のような単音節語幹や「とする → する」では有効だが、「なる → な」「要する → 要す」など語幹境界が 1 文字除去と一致しない動詞では誤った切り捨てになる。形態素解析の `lemma`（原形）フィールドを使うほうが正確。

**修正提案**: `_tokenize()` で動詞を検出し、`t['lemma']` から語幹を取得する。

---

### M-7 `meisai_checker/grammar/particles.py` 162行 — 品詞名の誤り

**場所**: `meisai_checker/grammar/particles.py` `_is_noun_like()` 関数（162行前後）

```python
if t['pos'] in ('名詞', '代名詞', '形容動詞', ...):
```

unidic-lite では「代名詞」は `名詞` の下位分類（`pos1 == '代名詞'`）であり、トップレベルの `pos` として現れない。「形容動詞」も同様で、unidic では `形状詞` が正しい品詞名。結果として代名詞・形容動詞を名詞類として扱う分岐が**実質的に機能しない**。

**修正提案**: `pos` と `pos1` の両方を確認するか、unidic-lite の実際の品詞体系（`pos == '名詞' and pos1 == '代名詞'`、`pos == '形状詞'`）に合わせてラベルを修正する。

---

### M-8 `meisai_checker/structure/sections.py` — `check_midashi_numbers()` の重複正規表現範囲

**場所**: `meisai_checker/structure/sections.py` `check_midashi_numbers()` 内（341行前後）

```python
re.compile(r'[１-９１-９]')   # 全角範囲が2回重複している
```

文字クラス `[１-９１-９]` は `１-９` の範囲を 2 つ含んでいる。機能的な誤動作は起きないが、半角 `1-9` か全角 `１-９` か、片方のみ意図しているなら誤記である。

**修正提案**: 意図に応じて `[０-９]`（全角のみ）か `[0-90-9]`（半角＋全角）か `[0-9０-９]` に修正する。

---

### M-9 `meisai_checker/patent/clarity.py` 317行 — `AttributeError` の可能性

**場所**: `meisai_checker/patent/clarity.py` 317行

```python
verb = (m_stem or m_wago).group(0)  # type: ignore[union-attr]
```

`_has_change_verb()` が True を返した場合でも、内部の正規表現マッチが `m_stem` も `m_wago` も `None` になるケースが実装上ありえるなら AttributeError が発生する。analyzer.py 側の `except Exception` で握りつぶされるためエラーが表面化しないが、M7 チェック全体が無効化される。

**修正提案**: `(m_stem or m_wago)` の前に明示的な None チェックを追加するか、`_has_change_verb()` の返却値を `re.Match | None` にして呼び出し側で統一的に処理する。

---

## 低（コード品質・軽微な問題）

### L-1 `meisai_checker/tokenizer.py` — `text.find()` による offset の誤算

**場所**: `meisai_checker/tokenizer.py` `_tokenize()` 内

```python
pos = text.find(surf, pos)
```

同一表層形（例：「の」「を」「する」）が直前のトークンよりも前に出現している場合、`find(surf, pos)` は期待したトークンよりも前の出現を指してしまうことがある。これによりハイライト表示やオフセットベースの照合がずれる。

**修正提案**: fugashi の `pos_id` や文字列スライスでオフセットを計算するか、`text.find(surf, pos)` の結果が前回トークン終端より小さい場合を検出して再検索するガードを追加する。

---

### L-2 `meisai_checker/patent/subcombination.py` 649行前後 — ループ内の正規表現コンパイル

**場所**: `meisai_checker/patent/subcombination.py` 649行前後

ループの中で `re.compile(...)` を呼んでいる箇所がある。正規表現コンパイルはコストが高く、モジュール定数にすべき。

**修正提案**: ループの外（モジュールレベル）に `_CLAIM_LIMIT_RE = re.compile(...)` として移動する。

---

### L-3 `meisai_checker/textcheck/redundant.py` 56〜58行 — 冗長なリスト内包表記

**場所**: `meisai_checker/textcheck/redundant.py` 56〜58行

```python
pairs = [(p, n) for p, n in _REDUNDANT_FIXED]   # list(_REDUNDANT_FIXED) と同等
```

アンパックして再パックしているだけで意味がない。

**修正提案**: `pairs = list(_REDUNDANT_FIXED)` に単純化する。

---

### L-4 `meisai_checker/textcheck/redundant.py` 59〜128行 — 段落ループの重複

**場所**: `meisai_checker/textcheck/redundant.py` 59〜93行（固定表現チェック）、96〜128行（数値範囲チェック）

ほぼ同一構造の「段落ごとのイテレーションとパラグラフ ID 取得」ロジックが 2 か所に存在する。

**修正提案**: 共通のジェネレータ関数（例：`_iter_paragraphs(sections)`）に切り出し、2 つのループから呼ぶ。

---

### L-5 `meisai_checker/textcheck/verbose.py` 51行 — `\w` が日本語にマッチする

**場所**: `meisai_checker/textcheck/verbose.py` 51行

```python
re.compile(r'\w{1,8}を行う')
```

Python の `re` では `\w` は Unicode 対応のため、漢字・かな・カタカナにもマッチする。日本語の「処理を行う」「制御を行う」等がヒットする一方、「ABCDEFGHを行う」等の英字が混じった表現も検出する。意図的かどうか不明。

**修正提案**: 意図が「動詞 + を行う」の冗長表現検出であれば `[぀-鿿]{1,8}を行う` のように文字範囲を明示するか、`\w` の意図をコメントで明記する。

---

### L-6 `meisai_checker/blocks.py` 224行前後 — オフセットと実テキストのズレ

**場所**: `meisai_checker/blocks.py` `_highlight_para()` 224行前後

```python
if text[offset:offset+len(key)] != key:
    ...
```

`key = name + fugo` で構成されるが、`name` に序数修飾子（「第一」「上記」等）を含む場合に `core_name` と異なることがあり、offset 位置の文字列と `key` が一致しないケースが生じる。ハイライトのスキップや位置ずれを引き起こす。

**修正提案**: オフセット計算に使うキーを `core_name + fugo` に統一するか、`text.find(key, offset-5)` のように許容誤差を持たせる。

---

### L-7 `tests/` — テストカバレッジの偏り

**場所**: `tests/test_snapshot_analyze.py`

スナップショットテストは `.txt` 入力のみを対象としており、`file_reader.py` の `.docx` / `.pdf` 読み込みパスはテストされていない。また `tests/fixtures/` が `.gitignore` 管理のため、CI 環境ではフィクスチャが存在せず `test_fixtures_present()` が失敗する（CI では常にスキップまたはエラーになる）。

**修正提案**: `.docx` / `.pdf` の最小サンプルをリポジトリに含めるか、`pytest.skip` で明示的に CI をスキップする。また `tests/fixtures/` をバイナリファイルとして Git LFS 管理に移行することも検討する。

---

## まとめ

| 深刻度 | 件数 | 主な内容 |
|--------|------|----------|
| 高     | 4    | TypeError（H-1）、品詞フィールド誤り（H-2）、例外全握りつぶし（H-3）、MeCab 初期化失敗（H-4） |
| 中     | 9    | サマリー集計漏れ（M-1）、キャッシュ渡し漏れ（M-2）、重複トークナイズ（M-3）、index() 誤参照（M-4）、パターン排他ロジック（M-5）、他 |
| 低     | 7    | 正規表現の重複・範囲問題、冗長コード、テストカバレッジ不足 など |

**即対応が必要なもの**: H-1（MCP ツール 2 本が完全に機能しない）、H-2（前記チェックの照応詞末尾検出が全滅）、H-3（M7〜G1 のバグが本番で完全に無視される）。
