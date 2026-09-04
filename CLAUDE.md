# meisai-checker — Claude Code 引き継ぎファイル

## プロジェクト概要

日本語特許明細書・特許願の方式要件を自動チェックするツール。
**完全ローカル動作・無料・OSS（MIT）**

バージョン管理: `git rev-list --count HEAD` をマイナーバージョンに使用。mainへのpushごとにGitHub Actionsが `0.N.0` に自動更新。

- GitHub: https://github.com/aki0ka/meisai-checker
- 作者: 岡田 晃久（弁理士 登録番号14374）
- リリース名: meisai-checker（旧称 patent-checker、2026-04に改名）

---

## 現在の実装状況（2026-05-20 更新）

### 実装済みチェック

| ID | 関数 | 場所 | 内容 |
|----|------|------|------|
| M2 | check_dependency | parser.py | 自己引用・引用先より前に記載（特施規24条の3第4号）・マルチマルチクレーム |
| M3 | check_zenshou | patent/anaphora.py | 前記・当該の照応詞チェック（MeCab使用） |
| M4 | check_fugo | patent/fugo.py | 符号・変数記号と要素名の対応 |
| M5 | check_structure 等 | structure/sections.py 等 | JIS Z 8301準拠・段落番号・句読点・見出し |
| M6 | check_support | patent/support.py | サポート要件（請求項の用語が詳細説明にあるか） |
| M7 | check_ambiguity, check_vague_range, check_nontechnical | patent/ambiguity.py, patent/clarity.py | 係り受け曖昧性・曖昧表現（約・適宜・好ましくは等）・非技術的事項（企業名・販売地域等） |
| M8 | check_docfields | structure/docfields.py | 明細書記録項目・様式第29 |
| M9 | check_gansho | structure/gansho.py | 願書記録項目・様式第26 |
| TC1 | check_brackets | textcheck/brackets.py | 括弧対応の整合性 |
| TC2 | check_repetition | textcheck/repetition.py | 語句・句読点の繰り返し |
| TC3 | check_style | textcheck/style.py | 敬体（です・ます）混入検出 |
| TC4 | check_length | textcheck/length.py | 一文120文字超の警告（特許ライティングマニュアル 1-1） |
| TC5 | check_verbose | textcheck/verbose.py | 冗長表現（することができる・ものである・を行う・仕様上の等）（マニュアル 6-1, 7-5, 7-6） |
| TC6 | check_redundant | textcheck/redundant.py | 意味重複（約〜程度・各〜毎・まず初めに等）・数値範囲の桁揃え（マニュアル 2-3, 6-2） |
| TC7 | check_punctuation | textcheck/punctuation.py | 読点欠落（接続語句・ので・ため等の後）（マニュアル 5-2, 5-3） |
| TC8 | check_deictic | textcheck/deictic.py | こそあど指示代名詞（これ・それ等）（マニュアル 7-3） |
| TC9 | check_sentence_split | textcheck/sentence_split.py | 文中箇条書き・長いかっこ書き（マニュアル 1-3, 1-4） |
| TC10 | check_conjunction | textcheck/conjunction.py | 「及び」「並びに」「又は」「若しくは」の表記統一（ひらがな表記を検出） |
| G1 | check_particles | grammar/particles.py | 同一助詞連続・「の」過剰連鎖（MeCab使用） |

### パッケージ構成

```
meisai_checker/
  __init__.py            ← __version__ = "16.1.0"
  analyzer.py            ← 220行（analyze() + 再エクスポートシム）
  blocks.py              ← build_blocks / _highlight_*（ビューア用）
  cli.py                 ← CLIエントリポイント
  config.py              ← 設定管理
  file_reader.py         ← txt/docx/pdf読み込み
  gui.py                 ← PyWebViewベースのGUI
  html_template.html     ← GUIフロントエンド
  mcp_server.py          ← MCPサーバー（FastMCP）
  parser.py              ← セクション分割・請求項パース・M2依存関係
  preprocessor.py        ← 書式検出・正規化（J-PlatPat/出願書類）
  tokenizer.py           ← fugashi（MeCab）形態素解析
  viewer.py              ← 結果表示ヘルパー
  textcheck/
    kuten.py             ← check_kuten
    charset.py           ← check_jis
    brackets.py          ← check_brackets（TC1）
    repetition.py        ← check_repetition（TC2）
    style.py             ← check_style（TC3）
    length.py            ← check_length（TC4）
    verbose.py           ← check_verbose（TC5）
    redundant.py         ← check_redundant（TC6）
    punctuation.py       ← check_punctuation（TC7）
    deictic.py           ← check_deictic（TC8）
    sentence_split.py    ← check_sentence_split（TC9）
    conjunction.py       ← check_conjunction（TC10）
  structure/
    abstract.py          ← check_abstract
    sections.py          ← check_structure, check_para_nums, check_midashi_numbers
    docfields.py         ← check_docfields（旧 m8_docfields.py）
    gansho.py            ← check_gansho（旧 m9_gansho.py）
  patent/
    anaphora.py          ← check_zenshou, build_noun_groups
    fugo.py              ← check_fugo, classify_fugo, FUGO_EXCLUDE_LIST 等
    title.py             ← check_title
    support.py           ← check_support
    ambiguity.py         ← check_ambiguity（旧 m7_ambiguity.py）
    clarity.py           ← check_vague_range（曖昧表現）, check_nontechnical（非技術的事項）
  grammar/
    particles.py         ← check_particles（G1）
main.py                  ← GUI起動エントリポイント
DESIGN.md                ← アーキテクチャ設計書（2026-04策定）
README.md                ← ユーザー向けドキュメント
.github/ISSUE_TEMPLATE/
  false_detection.md     ← 誤検知・見逃し報告フォーム
```

### テスト基盤

- `tests/fixtures/` (gitignore) に 4 件のサンプル明細書
- `tests/snapshots/` に 65 件の golden JSON（git 追跡対象）

**テスト実行コマンド:**
```bash
# venv（依存ライブラリ一式入り）
/Users/akihisa/Desktop/meisai-checker/.venv/bin/python -m pytest tests/ -q

# ベースライン再作成（analyze() の出力を意図的に変えた後）
/Users/akihisa/Desktop/meisai-checker/.venv/bin/python -m pytest tests/ --update-snapshots
```

---

## 既知の課題・今後の方針

### 検出精度（偽陽性・偽陰性）

- **M個の端末** など「アルファベット＋個」の量化子表現を符号と誤検知する場合がある
- **土台側、範囲内、走査線上** など方位・方角指示文言（側・内・上・下・直下・近傍等）が名詞境界を侵害することがある
- NEologd 導入では根本解決にならない（辞書語彙でなく形態素境界の問題）
- `.github/ISSUE_TEMPLATE/false_detection.md` でユーザーフィードバックを収集し、事例が集まってからルール化する方針

### リファクタリング・実装予定

**詳細は** `.claude/projects/-Users-akihisa-projects-meisai-checker/memory/project_refactoring_roadmap.md` **を参照**
- 優先度別リスト（高・中・低）
- 各項目の規模・ファイル・テスト戦略・依存関係
- 実装順序の推奨案（Phase 1-4）
- 常に最新の進捗を更新

**概要:**

| 優先度 | 作業 | 規模 | 状態 |
|--------|------|------|------|
| 高 | M4 誤検出修正バッチ | 小 | 設計完了 |
| 高 | tokenizer 型分離（指示子/量化子） | 中 | 設計中 |
| 高 | M3 トークンベース化 | 中 | 設計中 |
| 高 | M6 動詞チェック追加 | 小 | 未着手 |
| 中 | analyze() を Issue dataclass 統一 | 中 | 未着手 |
| 中 | CLI サブコマンド化 | 小 | 未着手 |
| 中 | Phase 3: preprocessor.py → normalize/ | 大 | 設計未着手 |
| 低 | Layer 5: argument.py / predicate.py | 大 | 未着手（GiNZA未導入） |

---

## 技術的な注意事項

### MeCab / fugashi
- `tokenizer.py` の `_tokenize()` を使うこと。直接 fugashi を呼ばない

### pywebview（GUI）
- `window.width` が `None` を返すバグあり → config保存時は `isinstance(w, int) and w > 0` で確認済み
- D&D は FileReader API ベース（file.path は使えない）

### FUGO_EXCLUDE_LIST
- `patent/fugo.py` にある除外リスト
- 誤検出防止のために単語を追加してきた経緯あり

### TOON形式
- MCP サーバーの出力フォーマット（JSON比で約30%トークン削減）
- `mcp_server.py` 内で定義

### 文法チェック（Layer 5）について
- `particles.py`（助詞の連続）は実装済み（MeCab のみ）
- `argument.py`（格助詞の項構造）と `predicate.py`（主述不一致）は **GiNZA** が必要
- GiNZA は未導入。導入する場合は `pip install ginza ja-ginza`

---

## 開発環境

- macOS (MacBook Air M2)
- Python 3.12（Desktop venv: `/Users/akihisa/Desktop/meisai-checker/.venv`）
- fugashi + unidic-lite（MeCab）
- pywebview（GUI）
- FastMCP（MCPサーバー）

## よく使うコマンド

```bash
cd ~/projects/meisai_checker

# GUI起動（Desktop venv を使用）
/Users/akihisa/Desktop/meisai-checker/.venv/bin/python main.py

# テスト
/Users/akihisa/Desktop/meisai-checker/.venv/bin/python -m pytest tests/ -q

# push
git push origin main
```

