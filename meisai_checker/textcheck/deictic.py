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


_CLAIM_NUM_PAT = re.compile(r'【請求項(\d+)】')


def check_deictic(sections):
    """TC8: こそあど指示語チェック。

    請求項: 指示先が曖昧になりやすいため個別に 🟡 warning。
    明細書本文: 件数を集約して 🔵 info 1件にまとめる（逐一列挙しない）。

    sections: split_sections() の戻り値
    戻り値: issue dict のリスト
    """
    issues = []

    # ── 請求項：個別に warning ──
    claims_text = sections.get("claims", "")
    if claims_text:
        seen: set = set()
        current_claim = None
        for line in claims_text.splitlines():
            stripped = line.strip()
            m = _CLAIM_NUM_PAT.match(stripped)
            if m:
                current_claim = int(m.group(1))
                continue
            if _HEADING_PAT.match(stripped):
                continue
            body = _PARA_NUM_PAT.sub('', stripped).strip()
            if len(body) < 4:
                continue
            body_filtered = _KORE_NI_YORI_PAT.sub('', body)
            for match in _DEICTIC_PAT.finditer(body_filtered):
                word = match.group(1)
                snippet = body[max(0, match.start() - 10):match.end() + 20].strip()
                key = (current_claim, word, snippet[:20])
                if key in seen:
                    continue
                seen.add(key)
                issue = {
                    "milestone": "TC8",
                    "level": "warning",
                    "msg": (f"指示代名詞「{word}」が請求項で使われています。"
                            f"指示先を「前記X」等で明示してください（7-3）"),
                    "detail": snippet,
                }
                if current_claim:
                    issue["claim"] = current_claim
                issues.append(issue)

    # ── 明細書本文：件数集約で info 1件 ──
    desc_text = sections.get("description", "")
    if desc_text:
        count = 0
        seen_desc: set = set()
        for line in desc_text.splitlines():
            stripped = line.strip()
            if _HEADING_PAT.match(stripped):
                continue
            body = _PARA_NUM_PAT.sub('', stripped).strip()
            if len(body) < 4:
                continue
            body_filtered = _KORE_NI_YORI_PAT.sub('', body)
            for match in _DEICTIC_PAT.finditer(body_filtered):
                word = match.group(1)
                snippet = body[max(0, match.start() - 10):match.end() + 20].strip()
                key = (word, snippet[:20])
                if key in seen_desc:
                    continue
                seen_desc.add(key)
                count += 1
        if count > 0:
            issues.append({
                "milestone": "TC8",
                "level": "info",
                "msg": (f"指示代名詞（これ・それ等）が明細書本文に{count}件あります。"
                        f"必要に応じてエディタで確認してください（7-3）"),
            })

    return issues
