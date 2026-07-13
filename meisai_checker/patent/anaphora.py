# -*- coding: utf-8 -*-
"""M3: 前記・当該の照応詞チェック（特許法第36条6項2号関連）。

依存: tokenizer.py（MeCab/fugashi 必須）
"""

from __future__ import annotations
import re

from ..tokenizer import (
    _tokenize,
    _noun_span,
    _span_to_str,
    _collect_defined_nouns,
    _find_dearu_defs,
    _scan_first_seen_as_plural,
    _noun_after_zenshou,
    _found_in_scope,
    _found_in_scope_ex,
    _get_title_noun_start,
    _PAREN_PAT,
    _ZENSHOU_WORDS,
    _TOUGAI_WORDS,
    _QUANT_MODS,
    _LOC_SUFFIXES_BOUNDARY,
    _LEADING_QUANT_PREFIXES,
)

# 従属項引用句パターン（独立導入ではなく依存参照）
# 亜種: に記載の（標準）・記載の（に省略）・に記載される・に記載した・に示した・に係る
_CLAIM_REF_PAT = re.compile(
    r'請求項.{1,25}'
    r'(?:に記載の|に記載される|に記載した|記載の|に示した|に係る)'
    r'.{0,5}'
)

# 「前記/上記/当該/該 + (量化子) + noun」パターン検出用
# 例: 前記各N, 前記複数のN, 上記すべてのN など
_ZENSHOU_QUANT_PRE_PAT = re.compile(
    r'(?:前記|上記|当該|該)(?:各|複数の|すべての|全ての|それぞれの|多数の|少数の)?$'
)

# 請求項前文の候補パターン（"…であって"/"…において" の後）
# 実装では末尾名詞との繰り返しを確認して判定
_PREAMBLE_CANDIDATE_PAT = re.compile(r'(?<!も)(?<!ステップ)(?:であって|において)[、,]')

# 複合位置語（2文字以上）：「基板直下」→「基板」+「直下」のように名詞境界を侵害するケース
_LOC_COMPOUND = ['直下', '近傍', '直上', '直前', '直後', '付近', '周辺', '周囲', '近傍部', '周り']


def _strip_loc_suffix(noun: str) -> str:
    """位置接尾辞を除去した基底名詞を返す。

    例: 「土台側」→「土台」、「範囲内」→「範囲」、「走査線上」→「走査線」
    複合位置語の場合も処理：「基板直下」→「基板」
    MeCabが接尾辞品詞として認識した場合のみ除去する（区間・期間等を誤除去しない）。
    """
    if not noun:
        return noun

    # 複合位置語（2文字以上）を優先チェック
    for loc_compound in _LOC_COMPOUND:
        if noun.endswith(loc_compound):
            return noun[:-len(loc_compound)]

    # 単純な位置接尾辞（1文字）: 助詞「に」を後置した分離位置確認
    # 「noun + に」をトークナイズし、「に」直前が loc_suffix の単独1文字トークンであれば除去。
    # 「区間」「期間」等は「区間に」→[区間(名詞),に]で区間が2文字トークンになるため除去しない。
    # 「土台側」は「土台側に」→[土台,側(1文字),に]で側が単独トークンになるため除去する。
    # 「ノード間」等の「間」は単独で新しい談話参照子を形成しうるため除去対象外。
    for loc_suffix in _LOC_SUFFIXES_BOUNDARY:
        if noun.endswith(loc_suffix):
            toks = _tokenize(noun + 'に')
            if (len(toks) >= 2
                    and toks[-2]['surf'] == loc_suffix
                    and toks[-1]['surf'] == 'に'):
                return noun[:-len(loc_suffix)]
            break  # 末尾文字は一致したが単独トークンでない → 除去しない

    return noun


def get_all_ancestors(num, dep_map, _cache=None, _visiting=None):
    """指定請求項の全祖先（直接・間接の従属元）を再帰的に収集する。

    誤記載等で従属関係に循環がある場合でも無限再帰に陥らないよう、
    探索中の経路（_visiting）を追跡し循環を検出したら打ち切る。
    """
    if _cache is None:
        _cache = {}
    if num in _cache:
        return _cache[num]
    if _visiting is None:
        _visiting = set()
    if num in _visiting:
        return set()
    _visiting = _visiting | {num}
    ancestors = set()
    for d in dep_map.get(num, []):
        ancestors.add(d)
        ancestors |= get_all_ancestors(d, dep_map, _cache, _visiting)
    _cache[num] = ancestors
    return ancestors


def _scope_tokens_for_parent(parent, dep_map, claim_tokens, cache, _scope_cache=None):
    """親請求項1つのフルスコープ（親＋その全祖先）のトークンリストを返す。

    claim_tokens: プリトークナイズ済みの dict[int, list[token]]
    _scope_cache: 親ごとの結果キャッシュ（呼び出し元が渡す）
    """
    if _scope_cache is not None and parent in _scope_cache:
        return _scope_cache[parent]
    anc = get_all_ancestors(parent, dep_map, cache)
    toks = []
    for a in sorted(anc | {parent}):
        toks += claim_tokens.get(a, [])
    if _scope_cache is not None:
        _scope_cache[parent] = toks
    return toks


def _extract_final_noun(tokens):
    """請求項末尾の発明種類名詞を抽出。例：「装置」「システム」「方法」など。"""
    if not tokens:
        return None
    # 末尾から逆順に最初の名詞を探す（助詞や句読点を除外）
    for i in range(len(tokens) - 1, -1, -1):
        t = tokens[i]
        if t['pos1'] == '名詞' and len(t['surf']) >= 2:
            return t['surf']
    return None


def _bare_claims_tokenized(noun, scope_body_items, precomputed_defined=None):
    """nounが照応詞なしで出現する請求項番号のセットを返す。

    scope_body_items: dict[claim_num, (tokens, claim_text)]
    precomputed_defined: dict[claim_num, dict] — _collect_defined_nouns の結果キャッシュ
    """
    found_in = set()
    for claim_num, (body_toks, body_text) in scope_body_items.items():
        if precomputed_defined is not None and claim_num in precomputed_defined:
            defined = precomputed_defined[claim_num]
        else:
            title_start = _get_title_noun_start(body_toks)
            check_toks = body_toks[:title_start] if title_start is not None else body_toks
            defined = _collect_defined_nouns(check_toks)
        if noun not in defined:
            continue
        # noun が請求項引用で導入されている請求項は継承とみなして除外
        is_inherited = False
        idx = 0
        while True:
            pos = body_text.find(noun, idx)
            if pos < 0:
                break
            pre = body_text[max(0, pos - 30):pos]
            if _CLAIM_REF_PAT.search(pre):
                is_inherited = True
                break
            idx = pos + 1
        if is_inherited:
            continue
        found_in.add(claim_num)
    return found_in


def _loc_compound_hint(noun, scope_tokens):
    """nounが複合位置語で終わり、基底名詞がスコープ内に定義されていれば (base, loc) を返す。"""
    for loc in _LOC_COMPOUND:
        if noun.endswith(loc) and len(noun) > len(loc):
            base = noun[:-len(loc)]
            if len(base) >= 2 and _found_in_scope(base, scope_tokens):
                return base, loc
    return None, None


def _uniqueness_warning(num, surf, noun, bare_claims):
    return {
        'claim': num, 'level': 'warning',
        'word': surf, 'noun': noun,
        'msg': (f"請求項{num}：「{surf}{noun}」の先行詞が"
                f"複数の請求項（{sorted(bare_claims)}）に存在します（先行詞重複）。"
                f"各{noun}に固有の名称を付与することを検討してください。"),
    }


def _plural_intro_warning(num, surf, noun):
    """早いものがち戦略：群（複数のN）が先行しているのに裸の「前記N」で照応した場合の警告。"""
    return {
        'claim': num, 'level': 'warning',
        'word': surf, 'noun': noun,
        'msg': (f"請求項{num}：「{noun}」は「複数の{noun}」（群）として先に導入されています。"
                f"裸の「{surf}{noun}」では群中のどの個体を指すか定まらず唯一性が崩れます。"
                f"群全体を指すなら「{surf}複数の{noun}」、"
                f"個体を指すなら「{surf}複数の{noun}のそれぞれ」「{surf}複数の{noun}のうちの少なくとも１つ」、"
                f"または先行詞側に固有名称を付与することを検討してください。"),
    }


def check_zenshou(claims, dep_map):
    """前記・上記・当該・該の先行詞チェック（fugashiトークンベース）。

    スコープ：
      前記・上記 → 同一請求項の前方 ＋ 全祖先請求項
                   多項従属の場合は直接親ごとに独立してスコープを評価し、
                   全ての直接親のスコープで先行詞が見つかる場合のみOKとする
      当該・該   → 同一請求項の前方のみ
    """
    issues = []
    _cache = {}
    _uniqueness_seen = set()  # (claim_num, noun) — 唯一性崩壊警告の重複排除

    # 全請求項をプリトークナイズ（繰り返し tokenize を避ける）
    claim_tokens = {n: _tokenize(b) for n, b in claims.items()}
    # 本文トークン列（前文除外）と本文テキストのペアを構築（唯一性チェック用）
    claim_body_items = {
        n: (claim_tokens[n], b) for n, b in claims.items()
    }

    # _collect_defined_nouns / _find_dearu_defs をプリ計算（ループ内での再計算を避ける）
    # _collect_defined_nouns はタイトル名詞句を除外した範囲で計算（_bare_claims_tokenized と同条件）
    claim_defined_nouns = {}
    for _n, _toks in claim_tokens.items():
        _title_start = _get_title_noun_start(_toks)
        _check_toks = _toks[:_title_start] if _title_start is not None else _toks
        claim_defined_nouns[_n] = _collect_defined_nouns(_check_toks)
    claim_dearu_defs = {
        n: _find_dearu_defs(toks) for n, toks in claim_tokens.items()
    }
    # _scope_tokens_for_parent の結果キャッシュ
    _scope_toks_cache: dict[int, list] = {}

    # 早いものがち戦略：特許請求の範囲全体を文字列順（請求項番号順）に走査し、
    # 各核名詞の初出時の量化子状態（複数のN が先か裸 N が先か）を記録する。
    # noun -> True（複数のN が先行）/ False（裸 N が先行）
    _scope_tokens_all = []
    for _n in sorted(claims.keys()):
        _scope_tokens_all += claim_tokens[_n]
    first_seen_as_plural = _scan_first_seen_as_plural(_scope_tokens_all)
    _plural_intro_seen = set()  # (claim_num, noun) — 群先行警告の重複排除

    for num in sorted(claims.keys()):
        body = claims[num]
        tokens = claim_tokens[num]

        # 「X である Y」定義構文を検出してINFO発行
        for genus_str, named_str, _ in claim_dearu_defs[num]:
            issues.append({
                'claim': num, 'level': 'info',
                'word': named_str, 'noun': named_str,
                'msg': (
                    f"請求項{num}：「{genus_str}である{named_str}」を定義構文として処理しました。"
                    f"「{genus_str}」は型指定（属）として先行詞から除外し、"
                    f"「{named_str}」を先行詞として登録します。"
                ),
            })

        # プリアンブル判定：末尾名詞が繰り返される「であって」「において」のみを判定
        final_noun = _extract_final_noun(tokens)

        # 候補パターンを検出
        m_pre = re.search(_PREAMBLE_CANDIDATE_PAT, body)
        is_preamble = False

        if m_pre and final_noun:
            # 「であって」「において」の直後で末尾名詞が繰り返されるかチェック
            # 末尾付近（末尾200文字以内）でのチェック
            preamble_text = body[:m_pre.end()]
            tail_text = body[-200:]  # 末尾200文字

            # 末尾200文字内で final_noun が出現するかチェック
            if final_noun in tail_text and final_noun in body[m_pre.end():]:
                is_preamble = True

        # 前文に照応詞がある場合は警告（前文はタイプ表現のみにすべき）
        if is_preamble:
            preamble_text = body[:m_pre.end()]
            if any(z in preamble_text for z in _ZENSHOU_WORDS):
                # 従属項の冒頭照応詞は許可（従属項では先行項からの照応が常態）
                # 「請求項1に記載の装置において、前記センサは...」という形式は正当
                direct_parents = dep_map.get(num, [])
                is_dependent = len(direct_parents) > 0

                if not is_dependent:
                    issues.append({
                        'claim': num, 'level': 'warning',
                        'msg': (f"請求項{num}：前文（「であって/において」以前）に照応詞があります。"
                                f"前文はタイプ表現のみにし、要素の導入・参照は本文で行ってください。"
                                f"前文内の先行詞・照応詞はM3チェック対象外です。"),
                    })

        direct_parents = dep_map.get(num, [])
        ancestors = get_all_ancestors(num, dep_map, _cache)
        ancestor_tokens = []
        for a in sorted(ancestors):
            ancestor_tokens += claim_tokens.get(a, [])

        for i, t in enumerate(tokens):
            if t['surf'] not in _ZENSHOU_WORDS:
                continue
            if t['surf'] == '該' and i > 0 and tokens[i-1]['surf'] == '当':
                continue

            noun, noun_start, _noun_end = _noun_after_zenshou(tokens, i)
            if not noun:
                continue

            # 位置接尾辞を除去した基底名詞を取得
            # 例: 「土台側」→「土台」、「範囲内」→「範囲」、「走査線上」→「走査線」
            noun_base = _strip_loc_suffix(noun)
            if noun_base != noun:
                # 位置接尾辞が除去された場合、基底名詞で先行詞照合を行う
                noun = noun_base

            # 「量化子＋の＋前記X」パターン検出（例：「複数の前記端末」）
            # 日本語名詞は数のマーキングがないため常に誤りとは言い切れないが、
            # 群全体か一部かの指示範囲が文脈なしには定まらず曖昧になりやすい。
            if (t['surf'] in _ZENSHOU_WORDS and t['surf'] not in _TOUGAI_WORDS
                    and i >= 2
                    and tokens[i - 1]['surf'] == 'の'
                    and tokens[i - 2]['surf'] in _QUANT_MODS):
                quant = tokens[i - 2]['surf']
                issues.append({
                    'claim': num, 'level': 'warning',
                    'word': t['surf'], 'noun': noun,
                    'msg': (
                        f"請求項{num}：「{quant}の{t['surf']}{noun}」は指す範囲（群全体か一部か）が"
                        f"曖昧になりやすい書き方です。書き換え例："
                        f"「前記{quant}の{noun}」（群参照）／"
                        f"「前記{quant}の{noun}のそれぞれ」（分配参照）／"
                        f"「前記{quant}の{noun}のうちの少なくとも１つ」（部分参照）。"
                    ),
                })

            # 「接頭辞としての各＋前記X」パターン検出（例：「各前記端末」）
            # Russell定冠詞理論では「前記」は単数選択（ι演算子）。その後に「各」で分配をかけるのは矛盾。
            if (t['surf'] in _ZENSHOU_WORDS and t['surf'] not in _TOUGAI_WORDS
                    and i >= 1
                    and tokens[i - 1]['surf'] == '各'
                    and tokens[i - 1].get('pos') == '接頭辞'):
                issues.append({
                    'claim': num, 'level': 'warning',
                    'word': t['surf'], 'noun': noun,
                    'msg': (
                        f"請求項{num}：「各{t['surf']}{noun}」は"
                        f"唯一の個体を定記述で選んだ後に分配をかける論理矛盾です。"
                        f"Russell定冠詞理論では、「前記」（the = ι演算子）で単一の個体を選んだ後、"
                        f"「各」で複数分配をかけるのは不可能です。"
                        f"意図に応じて次のいずれかに書き換えてください："
                        f"「前記複数の{noun}のそれぞれ」（複数の群から分配）、"
                        f"「前記{noun}のそれぞれ」（複数先行詞がある場合）、"
                        f"または先行詞を「複数の{noun}」として導入してください。"
                    ),
                })

            zenshou_end = tokens[i]['end']
            verb_modified = noun_start > zenshou_end  # 「前記AしたB」パターン

            prefix = tokens[:i]  # 同一請求項の前方

            _bridge_src = None
            if t['surf'] in _TOUGAI_WORDS:
                # 当該・該：同一請求項の前方のみ
                found = _found_in_scope(noun, prefix)
                if not found:
                    # ② 束縛変数回収: 「各N」「複数のN」等の分配スコープ内で
                    # 「当該N」が量化変数を受け取るパターンは正常（出力なし）
                    for _qpfx, _ in _LEADING_QUANT_PREFIXES:
                        if _found_in_scope(_qpfx + noun, prefix):
                            found = True
                            break
            else:
                # 前記・上記
                # まず同一請求項の前方で見つかれば常にOK
                _prefix_found, _bridge_src = _found_in_scope_ex(noun, prefix)
                if _prefix_found:
                    if _bridge_src:
                        issues.append({
                            'claim': num, 'level': 'info',
                            'word': t['surf'], 'noun': noun,
                            'msg': (f"請求項{num}：「{t['surf']}{noun}」の先行詞「{_bridge_src}」に"
                                    f"スペルアウト括弧書きが含まれています。"
                                    f"括弧書きを省いた「{_PAREN_PAT.sub('', _bridge_src)}」で"
                                    f"先に導入することを推奨します。"),
                        })
                    if verb_modified:
                        skipped = body[zenshou_end:noun_start]
                        issues.append({
                            'claim': num, 'level': 'info',
                            'word': t['surf'], 'noun': noun,
                            'msg': (f"請求項{num}：「{t['surf']}{skipped}{noun}」は記述照応詞です。"
                                    f"先行詞は「{noun}」として解決しますが、"
                                    f"「{noun}」に固有の名称を与える書き方への切り替えを検討してください。"),
                        })
                    else:
                        if len(direct_parents) > 1:
                            # 多項従属: 各親スコープで独立して唯一性を評価。
                            # 「請求項1又は2に記載の〜」は一方を選べば必ず一意なので、
                            # いずれか1つの親スコープ内で複数定義がある場合のみ警告する。
                            bare = set()
                            for parent in direct_parents:
                                p_ancs = get_all_ancestors(parent, dep_map, _cache) | {parent}
                                p_items = {a: claim_body_items[a] for a in p_ancs if a in claim_body_items}
                                p_bare = _bare_claims_tokenized(noun, p_items, claim_defined_nouns)
                                if len(p_bare) > 1:
                                    bare |= p_bare
                        else:
                            anc_body_toks = {a: claim_body_items[a] for a in ancestors if a in claim_body_items}
                            bare = _bare_claims_tokenized(noun, anc_body_toks, claim_defined_nouns)
                            if noun in _collect_defined_nouns(tokens[:i]):  # i未満なのでプリ計算不可
                                bare.add(num)
                        if len(bare) > 1 and (num, noun) not in _uniqueness_seen:
                            _uniqueness_seen.add((num, noun))
                            issues.append(_uniqueness_warning(num, t['surf'], noun, bare))
                        # 早いものがち：群（複数のN）が先行しているのに裸照応
                        if (first_seen_as_plural.get(noun) is True
                                and (num, noun) not in _plural_intro_seen):
                            _plural_intro_seen.add((num, noun))
                            issues.append(_plural_intro_warning(num, t['surf'], noun))
                    continue
                if len(direct_parents) <= 1:
                    # 単項従属または独立：全祖先を結合してチェック
                    found, _bridge_src = _found_in_scope_ex(noun, ancestor_tokens)
                else:
                    # 多項従属：いずれか一つの直接親のスコープで見つかれば良い
                    # 「請求項1又は2に記載の〜」は一方が適用されるので、
                    # 一方のスコープで見つかれば先行詞として成立する
                    _parent_results = [
                        _found_in_scope_ex(noun, _scope_tokens_for_parent(p, dep_map, claim_tokens, _cache, _scope_toks_cache))
                        for p in direct_parents
                    ]
                    found = any(r[0] for r in _parent_results)
                    _bridge_src = next((r[1] for r in _parent_results if r[1]), None)

            if not found:
                suppressed = False
                if t['surf'] in _TOUGAI_WORDS:
                    for j, tj in enumerate(prefix):
                        if tj['surf'] in ('前記', '上記'):
                            prev_noun, *_ = _noun_after_zenshou(tokens, j)
                            if prev_noun == noun:
                                prev_scope = ancestor_tokens + tokens[:j]
                                if _found_in_scope(noun, prev_scope):
                                    suppressed = True
                                    break
                # 早いものがち戦略：前記/上記で裸の先行詞が見つからないが、
                # 「複数のN」（群）として先に導入されている場合は、
                # 「先行詞なしエラー」ではなく「群先行による唯一性崩れ」警告にする。
                # （群は登録済みであり、欠けているのは原子としての名称だけ）
                # 当該・該はこのルールの対象外（局所スコープのため従来エラーを維持）。
                if (not suppressed and t['surf'] not in _TOUGAI_WORDS
                        and first_seen_as_plural.get(noun) is True):
                    if (num, noun) not in _plural_intro_seen:
                        _plural_intro_seen.add((num, noun))
                        issues.append(_plural_intro_warning(num, t['surf'], noun))
                    suppressed = True

                if not suppressed and t['surf'] in _TOUGAI_WORDS:
                    # ⑤ 先行詞が親請求項に存在 → WARN（前記推奨）
                    if _found_in_scope(noun, ancestor_tokens):
                        issues.append({
                            'claim': num, 'level': 'warning',
                            'word': t['surf'], 'noun': noun,
                            'msg': (
                                f"請求項{num}：「{t['surf']}{noun}」の先行詞は"
                                f"同一請求項内ではなく親請求項に存在します。"
                                f"「当該」のスコープは同一請求項内のみです。"
                                f"「前記{noun}」への変更を検討してください。"
                            ),
                        })
                        suppressed = True
                    # else: ⑤より先行詞が見つからない → suppressedのまま → 下のエラー報告へ

                if not suppressed:
                    if t['surf'] not in _TOUGAI_WORDS and len(direct_parents) > 1:
                        # 多項従属の場合、どの親のスコープでも見つからないことを示す
                        # （いずれか一つで見つかれば先行詞として成立するため）
                        detail = f"（請求項{direct_parents}全ての親スコープで見つかりません）"
                    elif t['surf'] not in _TOUGAI_WORDS:
                        dep_chain = sorted(ancestors)
                        detail = (f"（参照先：同一請求項前方＋従属元{dep_chain}）"
                                  if dep_chain else "")
                    else:
                        detail = "（当該・該のスコープは従属元を含みません）"
                    # 複合位置語ヒント：「前記基板直下」→「基板」が定義済みなら書き換えを提案
                    full_scope = ancestor_tokens + tokens[:i]
                    base, loc = _loc_compound_hint(noun, full_scope)
                    if base:
                        detail += f"。「{base}」は定義済みです。「{t['surf']}{base}の{loc}」と書き換えることを検討してください"
                    issues.append({
                        'claim': num, 'level': 'error',
                        'word': t['surf'], 'noun': noun,
                        'msg': f"請求項{num}：「{t['surf']}{noun}」の先行詞がスコープ内に見つかりません{detail}",
                    })
            elif verb_modified:
                # 先行詞は見つかったが「前記AしたB」パターン（祖先スコープから解決）
                if _bridge_src:
                    issues.append({
                        'claim': num, 'level': 'info',
                        'word': t['surf'], 'noun': noun,
                        'msg': (f"請求項{num}：「{t['surf']}{noun}」の先行詞「{_bridge_src}」に"
                                f"スペルアウト括弧書きが含まれています。"
                                f"括弧書きを省いた「{_PAREN_PAT.sub('', _bridge_src)}」で"
                                f"先に導入することを推奨します。"),
                    })
                skipped = body[zenshou_end:noun_start]
                issues.append({
                    'claim': num, 'level': 'info',
                    'word': t['surf'], 'noun': noun,
                    'msg': (f"請求項{num}：「{t['surf']}{skipped}{noun}」は記述照応詞です。"
                            f"先行詞は「{noun}」として解決しますが、"
                            f"「{noun}」に固有の名称を与える書き方への切り替えを検討してください。"),
                })
            elif t['surf'] not in _TOUGAI_WORDS:
                # 前記/上記・先行詞あり・動詞修飾なし → ブリッジ通知 + 唯一性チェック
                if _bridge_src:
                    issues.append({
                        'claim': num, 'level': 'info',
                        'word': t['surf'], 'noun': noun,
                        'msg': (f"請求項{num}：「{t['surf']}{noun}」の先行詞「{_bridge_src}」に"
                                f"スペルアウト括弧書きが含まれています。"
                                f"括弧書きを省いた「{_PAREN_PAT.sub('', _bridge_src)}」で"
                                f"先に導入することを推奨します。"),
                    })
                if len(direct_parents) > 1:
                    # 多項従属: 各親スコープで独立して唯一性を評価。
                    # 「請求項3又は4に記載の〜」は一方を選べば必ず一意なので、
                    # いずれか1つの親スコープ内で複数定義がある場合のみ警告する。
                    bare = set()
                    for parent in direct_parents:
                        p_ancs = get_all_ancestors(parent, dep_map, _cache) | {parent}
                        p_items = {a: claim_body_items[a] for a in p_ancs if a in claim_body_items}
                        p_bare = _bare_claims_tokenized(noun, p_items, claim_defined_nouns)
                        if len(p_bare) > 1:
                            bare |= p_bare
                else:
                    anc_body_toks = {a: claim_body_items[a] for a in ancestors if a in claim_body_items}
                    bare = _bare_claims_tokenized(noun, anc_body_toks)
                    if noun in _collect_defined_nouns(tokens[:i]):
                        bare.add(num)
                if len(bare) > 1 and (num, noun) not in _uniqueness_seen:
                    _uniqueness_seen.add((num, noun))
                    issues.append(_uniqueness_warning(num, t['surf'], noun, bare))
                # 早いものがち：群（複数のN）が先行しているのに裸照応
                if (first_seen_as_plural.get(noun) is True
                        and (num, noun) not in _plural_intro_seen):
                    _plural_intro_seen.add((num, noun))
                    issues.append(_plural_intro_warning(num, t['surf'], noun))
    return issues


# check_zenshou から参照される旧API互換ラッパー
def extract_noun_phrase_after(text, pos):
    """旧API互換：pos以降の名詞句を (noun, consumed) で返す。"""
    tokens = _tokenize(text[pos:])
    span = _noun_span(tokens, 0)
    noun = _span_to_str(span)
    consumed = len(noun)
    return noun, consumed


def extract_defined_nouns(text):
    """テキスト中の名詞句を収集して {名詞句: list[Occurrence]} を返す。"""
    tokens = _tokenize(text)
    return _collect_defined_nouns(tokens)


def build_noun_groups(claims, dep_map, ref_hits, m3_issues):
    """
    名詞句ごとにグループ化した前記チェック情報を返す。
    各グループ：
    {
      "noun":        "通行人",
      "error":       False,       # いずれかの参照がエラーなら True
      "first_claim": 1,           # 初出請求項番号（先行詞がある最初の請求項）
      "refs": [                   # この名詞句への「前記」出現一覧
        {"claim": 2, "word": "前記", "error": False},
        ...
      ]
    }
    """
    # m3_issueのエラーセット: (claim, noun, word)
    # word を含めることで「前記物体」(正常)と「当該物体」(エラー)を区別する
    error_set = {(i['claim'], i['noun'], i.get('word', '')) for i in m3_issues
                 if i.get('level') == 'error'}
    # 互換用: (claim, noun) のみのセット（wordなしのissueに対応）
    error_set_no_word = {(i['claim'], i['noun']) for i in m3_issues
                         if i.get('level') == 'error' and 'word' not in i}
    info_set = {(i['claim'], i['noun'], i.get('word', '')) for i in m3_issues
                if i.get('level') == 'info'}
    warning_set = {(i['claim'], i.get('noun', ''), i.get('word', '')) for i in m3_issues
                   if i.get('level') == 'warning'}

    # ref_hitsを名詞句でグループ化
    groups = {}  # noun → group dict
    for hit in ref_hits:
        noun = hit['noun']
        if not noun:
            continue
        if noun not in groups:
            groups[noun] = {
                'noun': noun,
                'error': False,
                'first_claim': None,
                'refs': [],
            }
        is_err  = ((hit['claim'], noun, hit['word']) in error_set or
                   (hit['claim'], noun) in error_set_no_word)
        is_info = (hit['claim'], noun, hit['word']) in info_set
        is_warn = (hit['claim'], noun, hit['word']) in warning_set
        groups[noun]['refs'].append({
            'claim': hit['claim'],
            'word':  hit['word'],
            'pos':   hit.get('pos', 0),   # 請求項内文字位置
            'error': is_err,
            'verb_modified': is_info,
            'uniqueness_warning': is_warn,
        })
        if is_err:
            groups[noun]['error'] = True

    # 初出請求項を特定
    def _find_first_in(noun, target_nums):
        candidates = [noun]
        # 位置接尾辞フォールバック:
        # 「収容部内」→「収容部」も候補に追加
        # 「土台側」→「土台」も候補に追加
        # UniDicが複合語を一体化した場合、定義語は基底名詞であり
        # 請求項本文に接尾辞付き版が現れた場合、完全一致検索が失敗するため
        base = _strip_loc_suffix(noun)
        if base != noun and len(base) >= 2:
            candidates.append(base)
        for num in target_nums:
            body = claims.get(num)
            if body is None:
                continue
            for cand in candidates:
                idx = 0
                while True:
                    pos = body.find(cand, idx)
                    if pos < 0:
                        break
                    prefix = body[max(0, pos-2):pos]
                    if prefix not in ('前記', '上記', '当該') and body[max(0,pos-1):pos] != '該':
                        return num
                    idx = pos + 1
        return None

    for noun, g in groups.items():
        # 全refにref個別のfirst_claimを設定する
        # スコープ規則：
        #   前記/上記 → 同一請求項 ＋ 直接・間接の全従属元（get_all_ancestors）
        #   当該/該   → 同一請求項のみ
        #              ただし同一請求項前方に「前記N」（エラーなし）があれば祖先まで拡張
        g['first_claim'] = None  # グループレベルは使わない（UI互換のため後でも設定）
        for r in g['refs']:
            # キャッシュなしで呼び出し（各ref個別に計算）
            ancestors = get_all_ancestors(r['claim'], dep_map)
            if r['word'] in ('当該', '該'):
                # 当該拡張ルール: 同一請求項前方に正常な「前記N」があれば祖先スコープも使用
                claim_tokens = _tokenize(claims.get(r['claim'], ''))
                anc_tokens = []
                for a in sorted(ancestors):
                    anc_tokens += _tokenize(claims.get(a, ''))
                # 同一請求項の前方トークン列で「前記N」を探す
                suppressed_first = None
                for j, tj in enumerate(claim_tokens):
                    if tj['surf'] in ('前記', '上記'):
                        prev_noun, *_ = _noun_after_zenshou(claim_tokens, j)
                        if prev_noun == noun:
                            prev_scope = anc_tokens + claim_tokens[:j]
                            if _found_in_scope(noun, prev_scope):
                                # 「前記N」が正常 → 祖先スコープで先行詞を探せる
                                suppressed_first = _find_first_in(noun, sorted(ancestors | {r['claim']}))
                                break
                if suppressed_first is not None:
                    scope_nums = sorted(ancestors | {r['claim']})
                else:
                    scope_nums = [r['claim']]
            else:
                scope_nums = sorted(ancestors | {r['claim']})
            # エラー行（先行詞なし）はfirst_claim=Noneに固定
            if r['error']:
                r['first_claim'] = None
            else:
                r['first_claim'] = _find_first_in(noun, scope_nums)
        # first_claim=None かつ error=False → 先行詞が見つからなかった → エラーに補正
        for r in g['refs']:
            if not r['error'] and r['first_claim'] is None:
                r['error'] = True
        # グループレベルのfirst_claim: refのfirst_claimの最小値（フォールバック用）
        valid = [r['first_claim'] for r in g['refs'] if r['first_claim'] is not None]
        g['first_claim'] = min(valid) if valid else None

    # 全 (group, ref) をフラット化して請求項昇順→noun名昇順でソートして返す
    for g in groups.values():
        g['refs'].sort(key=lambda r: r['claim'])
    return sorted(groups.values(), key=lambda g: (g['refs'][0]['claim'] if g['refs'] else 0, g['noun']))


# ══════════════════════════════════════════════════════════
# 表記ゆれ警告：「夫々」「其々」「同士」
# ══════════════════════════════════════════════════════════

def check_pronoun_variants(claims: dict[int, str]) -> list[dict]:
    """「夫々」「其々」のような表記ゆれと助詞「の」の省略を警告する。

    問題パターン：
      1. 「前記端末夫々」（「の」なし）→ 「前記…の夫々」を推奨
      2. 「同士」（漢字）→ 「どうし」ひらがなを推奨
    """
    issues = []

    # パターン1: 「前記/上記/当該/該 + ... + [夫其各]々」（「の」なし）
    # または、「複数の」などの限定詞 + ... + 「各々」（「の」なし）
    futatsu_pat = re.compile(
        r'((?:前記|上記|当該|該|複数の|複数個の|多数の|複数).+?)([夫其各]々)(?!の)',
        re.UNICODE | re.DOTALL
    )

    # パターン2: 「同士」（漢字）
    doushi_pat = re.compile(r'同士', re.UNICODE)

    for num in sorted(claims.keys()):
        body = claims[num]

        # パターン1: 「夫々」「其々」の「の」なないケース
        for m in futatsu_pat.finditer(body):
            issues.append({
                'claim': num,
                'level': 'info',
                'check': 'style_pronoun_variants',
                'msg': (
                    f'請求項{num}：「{m.group(0)}」の表記について。'
                    f'「{m.group(2)}」は読みにくいため、ひらがなで「それぞれ」と書くことを推奨します。'
                    f'また、助詞「の」を挟んで「{m.group(1)}…の{m.group(2)}」と表記してください。'
                )
            })

        # パターン2: 「同士」（漢字）
        for m in doushi_pat.finditer(body):
            # 「を同士」「で同士」など、前置詞的な用法を確認
            start = max(0, m.start() - 2)
            context = body[start:m.end() + 2]
            issues.append({
                'claim': num,
                'level': 'info',
                'check': 'style_pronoun_variants',
                'msg': (
                    f'請求項{num}：「同士」について。'
                    f'読みやすくするため、ひらがなで「どうし」と表記することを推奨します。'
                )
            })

    return issues
