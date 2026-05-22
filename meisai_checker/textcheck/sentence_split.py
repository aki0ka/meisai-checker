# -*- coding: utf-8 -*-
"""TC9: 短文化ヒントチェック（特許ライティングマニュアル第2版 1-3/1-4）。

1-3: 文中箇条書き — 一文の中に（１）（２）等の箇条書きが埋め込まれている
1-4: 長いかっこ書き — かっこ内が長く（40文字超）、次の文に切り出せる可能性がある

スコープ: 明細書本文
"""

from __future__ import annotations

import re


# 1-3: 文中に複数の箇条番号が含まれる（半角・全角数字、括弧形式）
# （１）〜、（２）〜 または (1)〜、(2)〜 形式
_INLINE_ENUM_PAT = re.compile(
    r'[（(][０-９0-9１-９1-9]+[）)][^。]{2,}'   # 最初の番号付き要素
    r'(?:[、，,][（(][０-９0-9１-９1-9]+[）)][^。]{2,}){1,}'  # 続く番号付き要素
)

# 1-4: 長いかっこ書き（40文字超）
# 全角かっこ・半角かっこ両対応
_LONG_PAREN_PAT = re.compile(r'[（(]([^）)\n]{40,})[）)]')

_PARA_ID_PAT = re.compile(r'【(\d{4,5})】')
_HEADING_PAT = re.compile(r'^【[^】\d][^】]*】\s*$')
_PARA_NUM_PAT = re.compile(r'【\d{4,5}】')
# 対象セクション: 発明を実施するための形態（とそのバリアント）
_IMPL_PAT = re.compile(
    r'【(?:発明を実施するための(?:最良の)?形態'
    r'|発明の実施の形態'
    r'|実施(?:形態)?[０-９0-9]*'
    r')】(.*?)(?=\n【[^\d０-９】][^】]*】|\Z)',
    re.DOTALL,
)


def check_sentence_split(sections):
    """TC9: 短文化ヒントチェック（1-3 文中箇条書き / 1-4 長いかっこ書き）。

    sections: split_sections() の戻り値
    戻り値: issue dict のリスト
    """
    issues = []
    seen = set()

    raw = sections.get("_raw", "") or sections.get("description", "")

    # 発明を実施するための形態のみを対象とする
    impl_parts = _IMPL_PAT.findall(raw)
    if not impl_parts:
        return issues
    desc = '\n'.join(impl_parts)

    current_para = None
    for line in desc.splitlines():
        stripped = line.strip()
        m = _PARA_ID_PAT.match(stripped)
        if m:
            current_para = 'p-' + m.group(1)

        if _HEADING_PAT.match(stripped):
            continue

        body = _PARA_NUM_PAT.sub('', stripped).strip()
        if len(body) < 10:
            continue

        # 1-3: 文中箇条書き
        for match in _INLINE_ENUM_PAT.finditer(body):
            snippet = match.group(0)[:60].strip()
            key = ('1-3', current_para, snippet[:20])
            if key in seen:
                continue
            seen.add(key)
            issue = {
                "milestone": "TC9",
                "level": "info",
                "msg": "文中に箇条書きが埋め込まれています—「以下の〇つがある。（１）〜」の形式への分割を検討（1-3）",
                "detail": snippet,
            }
            if current_para:
                issue["para_id"] = current_para
            issues.append(issue)

        # 1-4: 長いかっこ書き
        for match in _LONG_PAREN_PAT.finditer(body):
            inner = match.group(1)
            snippet = match.group(0)[:60].strip()
            key = ('1-4', current_para, snippet[:20])
            if key in seen:
                continue
            seen.add(key)
            issue = {
                "milestone": "TC9",
                "level": "info",
                "msg": (f"かっこ内が{len(inner)}文字と長くなっています"
                        f"—次の文に切り出すことを検討（1-4）"),
                "detail": snippet,
            }
            if current_para:
                issue["para_id"] = current_para
            issues.append(issue)

    return issues
