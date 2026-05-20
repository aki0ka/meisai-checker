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
    (re.compile(r'[一-鿿゠-ヿ぀-ゟ]{1,8}上の'),
     '「〜上の」→「〜に基づく」「〜に関する」等への言い換えを検討（7-6）'),
]

_PARA_ID_PAT = re.compile(r'【(\d{4,5})】')
_HEADING_PAT = re.compile(r'^【[^】\d][^】]*】\s*$')
_PARA_NUM_PAT = re.compile(r'【\d{4,5}】')


def check_verbose(sections):
    """TC5: 冗長表現チェック。

    sections: split_sections() の戻り値
    戻り値: issue dict のリスト
    """
    issues = []
    seen = set()

    targets = [
        sections.get("description", ""),
        sections.get("claims", ""),
    ]

    for text in targets:
        if not text:
            continue

        current_para = None
        for line in text.splitlines():
            stripped = line.strip()
            m = _PARA_ID_PAT.match(stripped)
            if m:
                current_para = 'p-' + m.group(1)

            if _HEADING_PAT.match(stripped):
                continue

            body = _PARA_NUM_PAT.sub('', stripped).strip()
            if len(body) < 4:
                continue

            for pat, note in _VERBOSE_PATTERNS:
                for match in pat.finditer(body):
                    snippet = body[max(0, match.start() - 12):match.end() + 12].strip()
                    key = (note, current_para, match.group(0))
                    if key in seen:
                        continue
                    seen.add(key)
                    issue = {
                        "milestone": "TC5",
                        "level": "info",
                        "msg": f"冗長な表現があります：「{match.group(0)}」— {note}",
                        "detail": snippet,
                    }
                    if current_para:
                        issue["para_id"] = current_para
                    issues.append(issue)

    return issues
