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
    _scan_first_seen_as_plural,
    _noun_after_zenshou,
    _found_in_scope,
    _found_in_scope_ex,
    _PAREN_PAT,
    _ZENSHOU_WORDS,
    _TOUGAI_WORDS,
    _QUANT_MODS,
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

# 請求項前文（"…であって"/"…において" 以前）の終端を検出
_PREAMBLE_END_PAT = re.compile(r'であって[、,]|において[、,]')

# 複合位置語（2文字以上）：「基板直下」→「基板」+「直下」のように名詞境界を侵害するケース
_LOC_COMPOUND = ['直下', '近傍', '直上', '直前', '直後', '付近', '周辺', '周囲', '近傍部', '周り']


def get_all_ancestors(num, dep_map, _cache=None):
    """指定請求項の全祖先（直接・間接の従属元）を再帰的に収集する"""
    if _cache is None:
        _cache = {}
    if num in _cache:
        return _cache[num]
    ancestors = set()
    for d in dep_map.get(num, []):
        ancestors.add(d)
        ancestors |= get_all_ancestors(d, dep_map, _cache)
    _cache[num] = ancestors
    return ancestors


def _scope_tokens_for_parent(parent, dep_map, claims, cache):
    """親請求項1つのフルスコープ（親＋その全祖先）のトークンリストを返す。"""
    anc = get_all_ancestors(parent, dep_map, cache)
    toks = []
    for a in sorted(anc | {parent}):
        toks += _tokenize(claims.get(a, ''))
    return toks


def _body_tokens(tokens, body_text):
    """前文（であって/において以前）を除いた本文トークン列を返す。前文なしは全トークン。"""
    m = _PREAMBLE_END_PAT.search(body_text)
    if not m:
        return tokens
    end_pos = m.end()
    return [t for t in tokens if t['start'] >= end_pos]


def _bare_claims_tokenized(noun, scope_body_items):
    """nounが本文（前文除外）に照応詞なしで出現する請求項番号のセットを返す。

    scope_body_items: dict[claim_num, (body_tokens, body_text)]
    - _collect_defined_nouns が照応詞直後をスキップするため、照応詞付き出現は除外される。
    - noun が1回でも「請求項Nに記載の〜」形式で出現する請求項は「継承」とみなし除外。
      （末尾の発明種類表現「ことを特徴とするX」等で再出現しても独立定義として扱わない）
    """
    found_in = set()
    for claim_num, (body_toks, body_text) in scope_body_items.items():
        defined = _collect_defined_nouns(body_toks)
        if defined.get(noun, 0) == 0:
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
                f"複数の請求項（{sorted(bare_claims)}）に存在します（唯一性の崩壊）。"
                f"各{noun}に固有の名称（例：「第1{noun}」「第2{noun}」）を付与することを検討してください。"),
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
                f"または先行詞側に「第1{noun}」「第2{noun}」等の固有名称を付与することを検討してください。"),
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
        n: (_body_tokens(claim_tokens[n], b), b) for n, b in claims.items()
    }

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

        # 前文に照応詞がある場合は警告（前文はタイプ表現のみにすべき）
        # 「するステップにおいて」等の従属節は除外（lookbehind で ステップ を除く）
        m_pre = re.search(r'であって[、,]|(?<!ステップ)において[、,]', body)
        if m_pre:
            preamble_text = body[:m_pre.end()]
            if any(z in preamble_text for z in _ZENSHOU_WORDS):
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
            if not noun or len(noun) < 2:
                continue

            # 「量化子＋の＋前記X」パターン検出（例：「複数の前記端末」）
            # ιで唯一選択した後に複数をかけるのは論理矛盾。「前記複数のX」等に書き換えるべき。
            if (t['surf'] in _ZENSHOU_WORDS and t['surf'] not in _TOUGAI_WORDS
                    and i >= 2
                    and tokens[i - 1]['surf'] == 'の'
                    and tokens[i - 2]['surf'] in _QUANT_MODS):
                quant = tokens[i - 2]['surf']
                issues.append({
                    'claim': num, 'level': 'warning',
                    'word': t['surf'], 'noun': noun,
                    'msg': (
                        f"請求項{num}：「{quant}の{t['surf']}{noun}」は"
                        f"唯一の個体を定記述で選んだ後に量化をかける形です。"
                        f"先行詞が「{quant}の{noun}」（集合）として導入されている場合は論理矛盾です。"
                        f"意図に応じて次のいずれかに書き換えてください："
                        f"「前記{quant}の{noun}」（群全体）、"
                        f"「前記{quant}の{noun}のそれぞれ」（分配）、"
                        f"「前記{quant}の{noun}のうちの少なくとも１つ」（部分）。"
                        f"先行詞が裸名詞タイプとして導入されている場合でも、"
                        f"先行詞側に「{quant}の{noun}」を明示する書き方が安全です。"
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
                                p_bare = _bare_claims_tokenized(noun, p_items)
                                if len(p_bare) > 1:
                                    bare |= p_bare
                        else:
                            scope_body_toks = {a: claim_body_items[a] for a in ancestors | {num} if a in claim_body_items}
                            bare = _bare_claims_tokenized(noun, scope_body_toks)
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
                    # 多項従属：全ての直接親のスコープそれぞれで見つかる必要がある
                    _parent_results = [
                        _found_in_scope_ex(noun, _scope_tokens_for_parent(p, dep_map, claims, _cache))
                        for p in direct_parents
                    ]
                    found = all(r[0] for r in _parent_results)
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

                if not suppressed:
                    if t['surf'] not in _TOUGAI_WORDS and len(direct_parents) > 1:
                        # 多項従属の場合、どの親で見つからないかを示す
                        missing = [p for p in direct_parents
                                   if not _found_in_scope(noun,
                                       _scope_tokens_for_parent(p, dep_map, claims, _cache))]
                        detail = f"（請求項{missing}に従属する場合にスコープ外）"
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
                scope_body_toks = {a: claim_body_items[a] for a in ancestors | {num} if a in claim_body_items}
                bare = _bare_claims_tokenized(noun, scope_body_toks)
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
    """テキスト中の名詞句を収集して {名詞句: 登録回数} を返す。"""
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
        if len(noun) < 2:
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
        from ..tokenizer import _LOC_SUFFIXES
        candidates = [noun]
        # 位置接尾辞フォールバック:
        # 「収容部内」→「収容部」も候補に追加
        # UniDicが「部内」を複合名詞として一体化した場合、定義語は「収容部」であり
        # 請求項本文に「収容部内」という語句は現れないため完全一致検索が失敗する
        if noun and noun[-1] in _LOC_SUFFIXES and len(noun) > 2:
            base = noun[:-1]
            if len(base) >= 2:
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
