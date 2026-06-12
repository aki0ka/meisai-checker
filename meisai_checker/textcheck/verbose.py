# -*- coding: utf-8 -*-
"""TC5: 冗長表現チェック（特許ライティングマニュアル第2版 6-1）。

「することができる」「ものである」「を図る」等の不要・冗長な表現を検出する。
スコープ: 明細書本文・請求項
"""

from __future__ import annotations

import re


# (パターン, 説明) のリスト
# 優先度の高い・長いパターンを先に置く
_VERBOSE_PATTERNS = [
    # 「することができる」系
    (re.compile(r'することが可能'), '「することが可能」→「できる」'),
    (re.compile(r'することができる'), '「することができる」→「できる」'),
    (re.compile(r'が実現できる'), '「が実現できる」→「できる」'),
    # 「を含む構成を有〜」は「構成を有〜」より先に置く
    (re.compile(r'を含む構成を有(?:する|している)'), '「を含む構成を有する」→「を含む」'),
    (re.compile(r'構成を有(?:する|している)'), '「構成を有する」→「含む」'),
    (re.compile(r'設けた構成を適用した'), '「設けた構成を適用した」→「設けた」'),
    # 「を図る」
    (re.compile(r'を図る'), '「〜を図る」→「〜する」'),
    # 「ということが分かる」
    (re.compile(r'ということが(?:分かる|わかる)'), '「ということが分かる」→「ことが分かる」'),
    # 「のである」（文末限定）
    (re.compile(r'のである(?=[。、\s]|$)'), '「のである」→削除'),
    # 「ものである」（文末限定）
    (re.compile(r'ものである(?=[。、\s]|$)'), '「ものである」→削除'),
    # 「ものとなる」
    (re.compile(r'ものとなる'), '「ものとなる」→「なる」'),
    # 「することとする」
    (re.compile(r'することとする'), '「することとする」→「する」'),
    # 「差し支えない」
    (re.compile(r'差し支えない'), '「差し支えない」→「よい」'),
    # 「〜てしまう」「〜なってしまう」
    (re.compile(r'(?:して|なって)しまう'), '「してしまう」→「する」'),
    # 「あり得る」
    (re.compile(r'あり得る'), '「あり得る」→「ある」'),
    # 「〜といえる」
    (re.compile(r'といえる'), '「といえる」→削除'),
    # 「〜とは言えない」
    (re.compile(r'とは言えない'), '「とは言えない」→「ではない」'),
    # 「〜て設けられている」（冗長な複合述語）
    (re.compile(r'て設けられている'), '「〜て設けられている」→「設けられている」'),
    # 7-5: 名詞の動詞化（を行う・をする・を実施する）
    # 「行う」は意図的に使う場合もあるため info レベルで提示
    (re.compile(r'\w{1,8}を行う'), '「〜を行う」→「〜する」（名詞の動詞化）'),
    (re.compile(r'\w{1,8}を実施する'), '「〜を実施する」→「〜する」（名詞の動詞化）'),
    (re.compile(r'\w{1,8}をする'), '「〜をする」→「〜する」（名詞の動詞化）'),
    # 7-6: 便利な接尾辞
    # 「〜的に」は一般的な技術表現（局部的に・部分的に等）を多数含むため
    # 「〜的に有利/優れ/困難/不利」等の非標準的な用法のみ検出
    (re.compile(r'[一-鿿゠-ヿ぀-ゟ]{1,8}的に(?:有利|優れ|困難|不利|問題)'),
     '「〜的に有利/困難」等→「〜をできる/できない」等に言い換えを検討（7-6）'),
    # 「〜上の」（仕様上の・コスト上の等）は定訳がなく曖昧になりやすい
    # ただし物理的位置を示す「表面上の」「基板上の」「壁上の」等は除外
    (re.compile(r'[一-鿿゠-ヿ぀-ゟ]{1,8}(?<![面板壁底])上の'),
     '「〜上の」→「〜に基づく」「〜に関する」等への言い換えを検討（7-6）'),
]

_PARA_ID_PAT = re.compile(r'【(\d{4,5})】')
_HEADING_PAT = re.compile(r'^【[^】\d][^】]*】\s*$')
_PARA_NUM_PAT = re.compile(r'【\d{4,5}】')
_CLAIM_NUM_PAT = re.compile(r'【請求項(\d+)】')

# 請求項で権利範囲に影響しうるパターン → 🟡 warning で個別表示
_SCOPE_RISK_PATS = frozenset({
    'することが可能', 'することができる', 'が実現できる',
})


def check_verbose(sections):
    """TC5: 冗長表現チェック。

    請求項:
      - 「することができる」系 → 🟡 warning（権利範囲に影響しうる）、個別表示
      - その他 → 🔵 info、個別表示
    明細書本文:
      - パターン別に件数を集約して 🔵 info 1件ずつ（逐一列挙しない）

    sections: split_sections() の戻り値
    戻り値: issue dict のリスト
    """
    issues = []

    # ── 請求項：個別表示 ──
    claims_text = sections.get("claims", "")
    if claims_text:
        seen: set = set()
        current_claim = None
        for line in claims_text.splitlines():
            stripped = line.strip()
            cm = _CLAIM_NUM_PAT.match(stripped)
            if cm:
                current_claim = int(cm.group(1))
                continue
            if _HEADING_PAT.match(stripped):
                continue
            body = _PARA_NUM_PAT.sub('', stripped).strip()
            if len(body) < 4:
                continue
            for pat, note in _VERBOSE_PATTERNS:
                for match in pat.finditer(body):
                    matched = match.group(0)
                    key = (note, current_claim, matched)
                    if key in seen:
                        continue
                    seen.add(key)
                    is_scope = any(risk in matched for risk in _SCOPE_RISK_PATS)
                    snippet = body[max(0, match.start() - 12):match.end() + 12].strip()
                    issue = {
                        "milestone": "TC5",
                        "level": "warning" if is_scope else "info",
                        "msg": f"冗長な表現があります：「{matched}」— {note}",
                        "detail": snippet,
                    }
                    if current_claim:
                        issue["claim"] = current_claim
                    issues.append(issue)

    # ── 明細書本文：パターン別に件数集約 ──
    desc_text = sections.get("description", "")
    if desc_text:
        counts: dict = {}   # note -> count
        seen_desc: set = set()
        current_para = None
        for line in desc_text.splitlines():
            stripped = line.strip()
            pm = _PARA_ID_PAT.match(stripped)
            if pm:
                current_para = pm.group(1)
                continue
            if _HEADING_PAT.match(stripped):
                continue
            body = _PARA_NUM_PAT.sub('', stripped).strip()
            if len(body) < 4:
                continue
            for pat, note in _VERBOSE_PATTERNS:
                for match in pat.finditer(body):
                    key = (note, current_para, match.group(0))
                    if key in seen_desc:
                        continue
                    seen_desc.add(key)
                    counts[note] = counts.get(note, 0) + 1

        for note, count in sorted(counts.items(), key=lambda x: -x[1]):
            label = note.split('→')[0].strip().strip('「」')
            issues.append({
                "milestone": "TC5",
                "level": "info",
                "msg": f"冗長な表現「{label}」が明細書本文に{count}件あります（{note}）",
            })

    return issues
