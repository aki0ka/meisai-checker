# -*- coding: utf-8 -*-
"""TC10: 接続語の表記統一チェック。

「及び」「並びに」「又は」「若しくは」は、特許庁の様式・審査基準および
特許ライティングマニュアルにおいて漢字仮名交じりで表記する。
ひらがな表記（および・ならびに・または・もしくは）が混入している箇所を
検出する。

スコープ: 明細書本文（description）・請求項（claims）・要約（abstract）
対象外: 見出し行
"""

from __future__ import annotations

import re


# ひらがな表記 → 正しい漢字仮名交じり表記
_KANA_CONJUNCTIONS = {
    'および': '及び',
    'ならびに': '並びに',
    'または': '又は',
    'もしくは': '若しくは',
}

_KANA_PAT = re.compile('|'.join(sorted(_KANA_CONJUNCTIONS, key=len, reverse=True)))

_HEADING_PAT = re.compile(r'^【[^】]+】\s*$')
_PARA_NUM_PAT = re.compile(r'^【\d{4,5}】')
_PARA_ID_PAT = re.compile(r'^【(\d{4,5})】')
_CLAIM_NUM_PAT = re.compile(r'^【請求項(\d+)】')


def check_conjunction(sections):
    """TC10: 接続語（及び・並びに・又は・若しくは）の表記統一チェック。

    sections: split_sections() の戻り値
    戻り値: issue dict のリスト
    """
    issues = []

    targets = [
        ("明細書", sections.get("description", "")),
        ("請求項", sections.get("claims", "")),
        ("要約", sections.get("abstract", "")),
    ]

    seen = set()  # 同一表記の重複報告を抑制

    for section_name, text in targets:
        if not text:
            continue
        current_para = None
        current_claim = None
        for line in text.splitlines():
            stripped = line.strip()
            pm = _PARA_ID_PAT.match(stripped)
            if pm:
                current_para = 'p-' + pm.group(1)
            cm = _CLAIM_NUM_PAT.match(stripped)
            if cm:
                current_claim = int(cm.group(1))
            if _HEADING_PAT.match(stripped):
                continue
            body = _PARA_NUM_PAT.sub('', stripped).strip()
            if not body:
                continue

            for m in _KANA_PAT.finditer(body):
                kana = m.group(0)
                correct = _KANA_CONJUNCTIONS[kana]
                anchor = current_claim if current_claim else current_para
                key = (section_name, anchor, kana)
                if key in seen:
                    continue
                seen.add(key)
                issue = {
                    "milestone": "TC10", "level": "warning",
                    "msg": f"接続語「{kana}」はひらがな表記です（{section_name}）："
                           f"「{correct}」に統一してください",
                    "detail": f"「及び」「並びに」「又は」「若しくは」は"
                              f"漢字仮名交じりで表記します：…{body[max(0, m.start() - 10):m.end() + 10]}…",
                }
                if current_claim:
                    issue["claim"] = current_claim
                elif current_para:
                    issue["para_id"] = current_para
                issues.append(issue)

    return issues
