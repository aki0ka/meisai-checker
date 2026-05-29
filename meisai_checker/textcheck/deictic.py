# -*- coding: utf-8 -*-
"""TC8: こそあど指示語チェック（特許ライティングマニュアル第2版 7-3）。

「これ」「それ」「あれ」「どれ」等の指示代名詞が何を指すか不明確な場合を検出する。
「この」「その」等の連体詞（名詞修飾）は対象外。

スコープ: 明細書本文・請求項
"""

from __future__ import annotations

import re


# 指示代名詞 + 助詞のパターン
# 連体詞「この/その/あの」は別語であり対象外
# 「これにより」は特許定型の効果記載なので除外
_DEICTIC_PAT = re.compile(
    r'(これら?|それら?|あれ|どれ|こちら|そちら|あちら|どちら)'
    r'[はをがにでのもよりとへ]'
)
_KORE_NI_YORI_PAT = re.compile(r'これにより')

_PARA_ID_PAT = re.compile(r'【(\d{4,5})】')
_HEADING_PAT = re.compile(r'^【[^】\d][^】]*】\s*$')
_PARA_NUM_PAT = re.compile(r'【\d{4,5}】')


def check_deictic(sections):
    """TC8: こそあど指示語チェック。

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

            # 「これにより」は効果記載の定型句なので除外
            body_filtered = _KORE_NI_YORI_PAT.sub('', body)
            for match in _DEICTIC_PAT.finditer(body_filtered):
                word = match.group(1)
                snippet = body[max(0, match.start() - 10):match.end() + 20].strip()
                key = (current_para, word, snippet[:20])
                if key in seen:
                    continue
                seen.add(key)
                issue = {
                    "milestone": "TC8",
                    "level": "info",
                    "msg": (f"指示代名詞「{word}」が使われています"
                            f"—何を指すか明示してください（7-3）"),
                    "detail": snippet,
                }
                if current_para:
                    issue["para_id"] = current_para
                issues.append(issue)

    return issues
