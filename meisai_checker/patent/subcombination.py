# -*- coding: utf-8 -*-
"""M2b: サブコンビネーションへの限定による明確性違反チェック（特許法36条6項2号）

従属クレームが親クレームの「コンビネーション（複数要素の組み合わせ）」のうち
一部の要素だけを「において」形式で限定し、残りの要素に言及しないケースを検出する。

■ 内部構成と外部構成の区別
  - 内部構成: クレームに記載された装置・方法そのものの構成要素
              例: 「圧縮部と展開部とを有する装置」→ 圧縮部・展開部が内部構成
  - 外部構成: クレームの構成要素が連携・接続する外部エンティティ
              例: 「外部サーバーと通信する手段」→ 外部サーバーは外部構成

  本チェックは内部構成要素のコンビネーションに対するサブセット限定のみを対象とし、
  外部構成への言及は誤検知防止のため除外する。

■ 検出パターン
  親クレーム: 「AとBとを有する装置」
  従属クレーム: 「請求項Nに記載の装置において、前記Aは〜装置。」
  → BへのB言及なしにAのみを限定 → warning

■ 除外ケース
  - 従属クレームがAとBの両方を前記で参照している場合
  - 親クレームに内部コンビネーション要素が1個以下の場合
  - マルチクレーム（複数請求項への従属）は対象外
  - 従属クレームが限定述語（は・が＋述語）なしに単に要素を参照している場合
"""
from __future__ import annotations

import re
from typing import Any

from ..parser import KIND_INDEPENDENT
from ..tokenizer import (
    _is_formal_noun_tok,
    _is_noun_tok,
    _noun_after_zenshou,
    _noun_span,
    _span_to_str,
    _tokenize,
)

# ══════════════════════════════════════════════════════════
# 定数
# ══════════════════════════════════════════════════════════

# コンビネーション動詞の基本形（内部構成要素列の末尾に来る動詞）
# surf が活用形になることがあるため base フィールドでマッチングする
_COMBO_VERB_BASES = frozenset({
    '有する', '備える', '含む', '具備する', '具える',
})

# 外部構成を示す動詞語幹（これらのサ変動詞の直前の「と」は外部構成接続子）
_EXTERNAL_VERB_BASES = frozenset({
    '通信', '接続', '連携', '連動', '協調', '相互作用',
    '送信', '受信', '入力', '出力', '取得', '提供',
    '接触', '連結', '結合', '統合', '送受信', '交換',
    '接合', '嵌合', '係合', '当接', '係止',
})

# 限定述語の助詞（「前記Aは〜」のように述語構造を示す）
_LIMITING_PARTICLES = frozenset({'は', 'が'})

# 他装置の内部構成を示すサ変動詞語幹（「を保有し」「を搭載し」等）
# 「を[語幹]し/する」パターンでも内部構成記述として検出する
_SAHEN_INTERNAL_NOUNS = frozenset({
    '保有', '搭載', '内蔵', '格納', '収容', '収納', '実装', '内包',
})


# ══════════════════════════════════════════════════════════
# 内部ヘルパー
# ══════════════════════════════════════════════════════════

def _get_segment_head_noun(toks: list[dict]) -> str:
    """トークン列から末尾の主名詞（ヘッド名詞）を抽出する。

    日本語は主要部が末尾に来る（head-final）ため、
    セグメント末尾の連続名詞ブロックがその要素の主名詞となる。

    例:
      「監視空間に敷設されたサンプリング管」→ 「サンプリング管」
      「検煙部」（分解トークン: 検・煙・部）→ 「検煙部」
      「第一センサ」→ 「第一センサ」（接頭辞も含む）

    アルゴリズム:
      1. 後ろから走査して最初の名詞トークンを見つける（1文字でも対象）
      2. そのトークンの前に連続する名詞トークンがあれば先頭まで遡る
      3. 先頭位置から _noun_span で前方に名詞句を収集して返す
      4. _noun_span が2文字未満しか返せない場合はフォールバックで結合
    """
    n = len(toks)
    for i in range(n - 1, -1, -1):
        t = toks[i]
        if not (_is_noun_tok(t) and not _is_formal_noun_tok(t)):
            continue

        # 名詞ブロックの先頭まで遡る（接頭辞・接尾辞・名詞を含む連続ブロック）
        span_start = i
        while span_start > 0:
            prev = toks[span_start - 1]
            if _is_noun_tok(prev) and not _is_formal_noun_tok(prev):
                span_start -= 1
            else:
                break

        # span_start から前方に名詞句を取得
        span = _noun_span(toks, span_start)
        s = _span_to_str(span)
        if len(s) >= 2:
            return s

        # _noun_span が取れない場合のフォールバック: span_start から i までを結合
        raw = ''.join(tok['surf'] for tok in toks[span_start:i + 1])
        if len(raw) >= 2:
            return raw

    return ''


def _is_external_connector(toks: list[dict], to_idx: int) -> bool:
    """「と」トークン（to_idx）が外部構成の接続子かどうかを判定する。

    外部構成の「と」は装置の内部構成要素どうしを列挙するのではなく、
    装置が外部エンティティと連携・通信等する関係を示す。

    判定条件（いずれかを満たすと外部構成と判断）:
      (A) 「と」の直後（読点スキップ後）が動詞 → 「外部装置と通信する」
      (B) 「と」の直後がサ変動詞語幹（外部動詞リスト内）
          → 「外部装置と通信」のような名詞止め
      (C) 「と」の直前がサ変動詞語幹（外部動詞リスト内）
          → 「通信と接続」のような外部動詞の列挙
      (D) 「と」の直後が「の」+名詞 で、その名詞が外部動詞語幹
          → 「外部サーバーとの接続」
    """
    n = len(toks)
    j = to_idx + 1

    # 読点スキップ
    while j < n and toks[j]['surf'] in ('、', ',', '，'):
        j += 1

    if j >= n:
        return False

    next_t = toks[j]

    # (A) 直後が動詞
    if next_t['pos'] == '動詞':
        return True

    # (B) 直後が外部動詞語幹（サ変可能名詞）
    # ただし「と出力部と」のように後続に名詞・接尾辞が続く複合語の場合は除外
    # 例: 「出力部」→ 出力(サ変可能)+部(名詞) → 複合語 → 内部構成要素
    if (next_t['pos'] == '名詞'
            and next_t.get('pos2') == 'サ変可能'
            and next_t['surf'] in _EXTERNAL_VERB_BASES):
        k = j + 1
        if k < n and toks[k]['pos'] in ('名詞', '接尾辞'):
            pass  # 複合語（出力部・通信手段等）→ 外部ではない
        else:
            return True

    # (C) 直前が外部動詞語幹
    if to_idx > 0:
        prev_t = toks[to_idx - 1]
        if (prev_t['pos'] == '名詞'
                and prev_t.get('pos2') == 'サ変可能'
                and prev_t['surf'] in _EXTERNAL_VERB_BASES):
            return True

    # (D) 直後が「の」で、「の」の次が外部動詞語幹
    if next_t['surf'] == 'の' and j + 1 < n:
        after_no = toks[j + 1]
        if (after_no['pos'] == '名詞'
                and after_no.get('pos2') == 'サ変可能'
                and after_no['surf'] in _EXTERNAL_VERB_BASES):
            return True

    return False


def _find_combo_pos(toks: list[dict]) -> int:
    """コンビネーション動詞「を有する/備える/含む」の「を」の位置を返す。

    活用形（備えた・含んだ等）も検出するため surf ではなく base フィールドでマッチする。
    「からなる」は「から」の位置を返す。見つからない場合は -1。
    """
    n = len(toks)
    for i in range(n - 1):
        if toks[i]['surf'] == 'を':
            # base フィールドでコンビネーション動詞を確認（活用形に対応）
            next_base = toks[i + 1].get('base', toks[i + 1]['surf'])
            if next_base in _COMBO_VERB_BASES:
                return i
        if toks[i]['surf'] == 'から' and toks[i + 1]['surf'] in ('なる', 'なっ', 'なり'):
            return i
    return -1



# ══════════════════════════════════════════════════════════
# 公開 API
# ══════════════════════════════════════════════════════════

def extract_combination_elements(parent_text: str) -> list[str]:
    """親クレームから「内部構成」のコンビネーション要素（主名詞）を抽出する。

    対象パターン:
      「[A]と（、）[B]と（、）...（を有する）」
      「[A]および[B]を備える」
      「[A]ならびに[B]を含む」

    外部構成（「外部装置と通信する」等）は除外する。

    Returns:
        内部構成要素の主名詞リスト。2個未満の場合は空リストを返す。
    """
    toks = _tokenize(parent_text)
    n = len(toks)

    # コンビネーション動詞の「を」の位置
    combo_pos = _find_combo_pos(toks)
    if combo_pos < 0:
        return []

    # 走査範囲: 先頭から「を有する/備える/…」の直前まで
    # （ユーザー定義: を有する/備える でつながれた全要素は内部構成）
    preamble_end = combo_pos

    # 前提部のトークン列を走査して内部構成要素を収集
    elements: list[str] = []
    seg_start = 0  # 現在のセグメント開始位置

    i = 0
    while i < preamble_end:
        t = toks[i]

        # ── 「および」「ならびに」「並びに」→ 内部構成の接続詞（確実） ──
        if t['surf'] in ('および', 'ならびに', '並びに'):
            seg_toks = toks[seg_start:i]
            head = _get_segment_head_noun(seg_toks)
            if head and len(head) >= 2:
                elements.append(head)
            seg_start = i + 1

        # ── 「と」（助詞）→ 内部/外部を判定 ──
        elif t['surf'] == 'と' and t['pos'] == '助詞':

            # 外部構成の「と」はスキップ
            if _is_external_connector(toks, i):
                # 外部接続子のためセグメントをリセット
                seg_start = i + 1
                while seg_start < preamble_end and toks[seg_start]['surf'] in ('、', ','):
                    seg_start += 1
                i = seg_start
                continue

            # 「と」の直後（読点スキップ後）を確認
            j = i + 1
            while j < preamble_end and toks[j]['surf'] in ('、', ',', '，'):
                j += 1

            if j < preamble_end:
                next_t = toks[j]

                # 直後が名詞 → 内部構成の列挙「と」
                if _is_noun_tok(next_t) and not _is_formal_noun_tok(next_t):
                    seg_toks = toks[seg_start:i]
                    head = _get_segment_head_noun(seg_toks)
                    if head and len(head) >= 2:
                        elements.append(head)
                    seg_start = j  # 読点をスキップした次の名詞から開始
                    i = j
                    continue

                # 直後が「を」→「とを有する」パターン（最後の要素の区切り）
                elif next_t['surf'] == 'を':
                    seg_toks = toks[seg_start:i]
                    head = _get_segment_head_noun(seg_toks)
                    if head and len(head) >= 2:
                        elements.append(head)
                    seg_start = i + 1

        i += 1

    # 最後のセグメント（combo_pos の直前まで）
    last_seg = toks[seg_start:preamble_end]
    last_head = _get_segment_head_noun(last_seg)
    if last_head and len(last_head) >= 2 and last_head not in elements:
        elements.append(last_head)

    # 重複除去（順序保持）
    seen: set[str] = set()
    unique: list[str] = []
    for e in elements:
        if e not in seen:
            seen.add(e)
            unique.append(e)

    return unique if len(unique) >= 2 else []


def extract_zenshou_nouns(dep_text: str) -> list[str]:
    """従属クレームから「前記/上記」で参照されている名詞句リストを返す。"""
    toks = _tokenize(dep_text)
    nouns: list[str] = []
    for i, t in enumerate(toks):
        if t['surf'] not in ('前記', '上記'):
            continue
        noun, _, _ = _noun_after_zenshou(toks, i)
        if noun and len(noun) >= 2:
            nouns.append(noun)
    return nouns


def noun_matches(combo_elem: str, ref_noun: str) -> bool:
    """コンビネーション要素名と参照名詞が一致するか判定する。

    - 完全一致
    - ref_noun の末尾が combo_elem と一致（修飾語付き参照の場合）
      例: combo_elem=「サンプリング管」, ref=「高感度サンプリング管」→ 一致
    - combo_elem の末尾が ref_noun と一致（略称の場合）
      例: combo_elem=「高感度サンプリング管」, ref=「サンプリング管」→ 一致
    """
    if combo_elem == ref_noun:
        return True
    if len(combo_elem) >= 3 and ref_noun.endswith(combo_elem):
        return True
    if len(ref_noun) >= 3 and combo_elem.endswith(ref_noun):
        return True
    return False


def has_selective_limitation(dep_text: str, mentioned_elems: list[str]) -> bool:
    """従属クレームが mentioned_elems の要素を述語で「限定」しているか判定する。

    「前記Xは、〜」「前記Xが〜」のように助詞「は」「が」が続く場合を
    「限定」とみなす。単なる「前記X」の経由・使用は限定ではない。
    """
    toks = _tokenize(dep_text)
    n = len(toks)

    for i, t in enumerate(toks):
        if t['surf'] not in ('前記', '上記'):
            continue
        noun, _, noun_end_char = _noun_after_zenshou(toks, i)
        if not noun:
            continue
        if not any(noun_matches(elem, noun) for elem in mentioned_elems):
            continue

        # 名詞句終端の文字位置以降のトークンを検索
        j = i + 1
        while j < n and toks[j]['end'] <= noun_end_char:
            j += 1

        # 接尾辞・接頭辞はスキップ
        while j < n and toks[j]['pos'] in ('接尾辞', '接頭辞'):
            j += 1

        # 「は」「が」が続けば限定述語あり
        if j < n and toks[j]['surf'] in _LIMITING_PARTICLES:
            return True

    return False


# ══════════════════════════════════════════════════════════
# M2c: 独立項における他装置記述（パターンA/D・C）
# ══════════════════════════════════════════════════════════

def _extract_main_subject(body: str) -> str:
    """請求項末尾の発明主体（名詞句）を抽出する。

    日本語特許独立項は末尾に発明主体の名詞句が来る（head-final）ため、
    _get_segment_head_noun でトークン列末尾の名詞群を取得する。
    """
    toks = _tokenize(body)
    return _get_segment_head_noun(toks)


def _find_other_device_internals(
    body: str,
    main_subj: str,
    internal_components: list[str],
) -> list[str]:
    """「前記X（は|が）〜を有し/備え」パターンで X が発明主体・内部構成要素でない箇所を返す。

    内部構成要素（extract_combination_elements で抽出済み）に含まれる要素は
    誤検知防止のため除外する。
    """
    toks = _tokenize(body)
    n = len(toks)
    hits: list[str] = []

    for i, t in enumerate(toks):
        if t['surf'] not in ('前記', '上記'):
            continue

        noun, _, noun_end_char = _noun_after_zenshou(toks, i)
        if not noun or len(noun) < 2:
            continue

        # 発明主体 → スキップ
        if noun_matches(main_subj, noun):
            continue

        # 内部構成要素 → スキップ
        if any(noun_matches(comp, noun) for comp in internal_components):
            continue

        # 名詞句終端後のトークンへ進む
        j = i + 1
        while j < n and toks[j]['end'] <= noun_end_char:
            j += 1
        while j < n and toks[j]['pos'] in ('接尾辞', '接頭辞'):
            j += 1

        if j >= n or toks[j]['surf'] not in ('は', 'が'):
            continue

        particle = toks[j]['surf']

        # 「が」は関係節・条件節でも使われるため係り受けなしには役割を確定できない。
        # 「は」は主節の主語マーカーとして使われることがほとんどのため文末まで走査する。
        # 「が」の場合は読点（、）または条件節マーカーで走査を打ち切る（短距離限定）。
        # ただし「前記Xが、〜を有する」のように「が」直後の読点はスタイル上の句読点のため
        # スキップして走査を継続する。
        _CONDITIONAL_MARKERS = frozenset({'場合', 'とき', 'であれば', 'ならば', 'なら', '際'})

        k = j + 1
        # 「が」直後の読点はスタイル上のものとしてスキップ
        if particle == 'が' and k < n and toks[k]['surf'] in ('、', '，'):
            k += 1
        found = False
        while k < n and toks[k]['surf'] not in ('。', '．'):
            surf = toks[k]['surf']
            if particle == 'が' and (surf in ('、', '，') or surf in _CONDITIONAL_MARKERS):
                break
            if surf == 'を' and k + 1 < n:
                next_tok = toks[k + 1]
                next_base = next_tok.get('base', next_tok['surf'])
                matched = next_base in _COMBO_VERB_BASES
                if not matched and next_tok['surf'] in _SAHEN_INTERNAL_NOUNS:
                    matched = True
                if matched:
                    found = True
                    break
            k += 1
        if found and noun not in hits:
            hits.append(noun)

    return hits


def check_other_device_internals(
    claims: dict[int, str],
    kinds: dict[int, str],
) -> list[dict[str, Any]]:
    """M2c-A: 独立項において発明主体以外の装置の内部構成を記述している場合に警告する。

    パターンA/D（審査基準第II部第2章第3節4.2）:
      「前記サーバBは、データベースとクエリ処理部とを有し」のように
      発明主体でも内部構成要素でもない装置の内部構成が記述されている場合、
      その記述が発明主体の構造・機能を特定しなければ明確性違反となる。
    """
    issues: list[dict] = []

    for num in sorted(claims.keys()):
        if kinds.get(num) != KIND_INDEPENDENT:
            continue

        body = claims[num]
        main_subj = _extract_main_subject(body)
        if not main_subj or len(main_subj) < 2:
            continue

        internal_components = extract_combination_elements(body)
        hits = _find_other_device_internals(body, main_subj, internal_components)

        for other_device in hits:
            issues.append({
                'claim': num,
                'level': 'warning',
                'check': 'subcombination_other_internals',
                'msg': (
                    f'請求項{num}：発明主体「{main_subj}」でも内部構成要素でもない'
                    f'「{other_device}」の内部構成（を有し/備え）が記述されています。'
                    f'この記述が「{main_subj}」の構造・機能を特定しない場合、'
                    f'明確性要件違反となります'
                    f'（特許法36条6項2号・審査基準第II部第2章第3節4.2）。'
                ),
            })

    return issues


# 用途限定のみのパターン（パターンC）
_PURPOSE_ONLY_PAT = re.compile(
    r'(?:からなる|を含む|により構成される|で構成される|から構成される)'
    r'(?:システム|ネットワーク|装置群|環境|プラットフォーム)'
    r'(?:に用いられる|に使用される|のための|に適用される'
    r'|において用いられる|において使用される)',
    re.UNICODE,
)


def check_purpose_only(
    claims: dict[int, str],
    kinds: dict[int, str],
) -> list[dict[str, Any]]:
    """M2c-C: 独立項において用途限定のみの他サブコンビネーション参照を検出する。

    パターンC（審査基準第II部第2章第3節4.2）:
      「スマートフォンとサーバとからなるシステムに用いられる装置」のように
      他のサブコンビネーション群への参照が用途限定にとどまり、
      発明主体の構造・機能を何ら特定しない場合に警告する。
    """
    issues: list[dict] = []

    for num in sorted(claims.keys()):
        if kinds.get(num) != KIND_INDEPENDENT:
            continue

        body = claims[num]
        for m in _PURPOSE_ONLY_PAT.finditer(body):
            matched = m.group(0)
            issues.append({
                'claim': num,
                'level': 'warning',
                'check': 'subcombination_purpose_only',
                'msg': (
                    f'請求項{num}：「{matched}」は用途限定のみの記載です。'
                    f'発明主体の構造・機能を何ら特定しない場合、'
                    f'明確性要件違反となります'
                    f'（特許法36条6項2号・審査基準第II部第2章第3節4.2）。'
                ),
            })

    return issues


# ══════════════════════════════════════════════════════════
# メインチェック関数
# ══════════════════════════════════════════════════════════

def check_subcombination(
    claims: dict[int, str],
    dep_map: dict[int, list[int]],
    kinds: dict[int, str],
) -> list[dict[str, Any]]:
    """M2b: サブコンビネーションへの限定による明確性違反を検出する。

    Args:
        claims:  {請求項番号: 本文テキスト}
        dep_map: {請求項番号: [従属先番号, ...]}
        kinds:   {請求項番号: 種別文字列}

    Returns:
        issues のリスト。各要素は dict:
            claim  : 請求項番号 (int)
            level  : 'warning'
            check  : 'subcombination'
            msg    : メッセージ (str)
    """
    issues: list[dict] = []

    for num in sorted(claims.keys()):
        # 独立項はスキップ
        if kinds.get(num) == KIND_INDEPENDENT:
            continue

        # 単項従属のみ対象（マルチクレームは複雑すぎるため除外）
        deps = dep_map.get(num, [])
        if len(deps) != 1:
            continue

        parent_num = deps[0]
        parent_body = claims.get(parent_num, '')
        dep_body = claims[num]

        # 従属クレームが「において」「であって」の限定形を持つかチェック
        if 'において' not in dep_body and 'であって' not in dep_body:
            continue

        # 親クレームから内部コンビネーション要素を抽出
        combo_elements = extract_combination_elements(parent_body)
        if len(combo_elements) < 2:
            continue

        # 従属クレームで「前記/上記」により参照されている名詞句を取得
        referenced = extract_zenshou_nouns(dep_body)
        if not referenced:
            continue

        # コンビネーション要素を「言及あり」「言及なし」に分類
        mentioned: list[str] = []
        not_mentioned: list[str] = []

        for elem in combo_elements:
            if any(noun_matches(elem, ref) for ref in referenced):
                mentioned.append(elem)
            else:
                not_mentioned.append(elem)

        # 一部のみが言及されている場合に警告候補
        if not mentioned or not not_mentioned:
            continue

        # さらに「言及あり」要素が述語で限定されているかを確認
        # （単なる経由参照ではなく、実質的に要素を限定している場合のみ警告）
        if not has_selective_limitation(dep_body, mentioned):
            continue

        combo_str = '・'.join(f'「{e}」' for e in combo_elements)
        mentioned_str = '・'.join(f'「{e}」' for e in mentioned)
        not_mentioned_str = '・'.join(f'「{e}」' for e in not_mentioned)

        issues.append({
            'claim': num,
            'level': 'warning',
            'check': 'subcombination',
            'msg': (
                f'請求項{num}：請求項{parent_num}の内部構成要素{combo_str}のうち'
                f'{mentioned_str}のみを限定し、'
                f'{not_mentioned_str}への言及がありません。'
                f'サブコンビネーションへの限定は明確性要件'
                f'（特許法36条6項2号）に違反する可能性があります。'
                f'残りの要素についても前記を用いて明示的に言及するか、'
                f'限定の意図を明確にしてください。'
            ),
        })

    return issues
