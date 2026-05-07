# -*- coding: utf-8 -*-
"""M7b: 明確性要件違反の追加パターン（特許法36条6項2号・審査基準第II部第2章第3節）

(5) 範囲を曖昧にし得る表現（「約」「適宜」「好ましくは」等）
(2e) 非技術的事項の記載（販売地域・販売元・価格等）
"""
from __future__ import annotations

import re
from typing import Any

from ..parser import KIND_INDEPENDENT


# ══════════════════════════════════════════════════════════
# (5) 範囲を曖昧にし得る表現
# ══════════════════════════════════════════════════════════

# (キーワード, カテゴリラベル, 補足メッセージ)
_VAGUE_KEYWORDS: list[tuple[str, str, str]] = [
    # 裁量的表現
    ('適宜',         '裁量的表現', '条件または基準値を明示してください。'),
    ('必要に応じて', '裁量的表現', '条件を具体的に記載してください。'),
    ('場合によっては', '裁量的表現', '条件を具体的に記載してください。'),
    # 好適表現
    ('好ましくは',   '好適表現', '必須要件として記載するか、従属項に移してください。'),
    ('望ましくは',   '好適表現', '必須要件として記載するか、従属項に移してください。'),
    ('なるべく',     '好適表現', '発明の範囲が不確定になります。'),
    ('できるだけ',   '好適表現', '発明の範囲が不確定になります。'),
]

# 数値近似表現（「約10mm」「50℃程度」等）
_NUMERIC_APPROX_PAT = re.compile(
    r'(?:約|おおむね|ほぼ|略)\s*\d'           # 「約10」「おおむね50」
    r'|\d[\d.]*\s*'
    r'(?:mm|cm|m|nm|μm|kg|g|℃|°C|Hz|MHz|GHz|kHz|%|MPa|Pa|W|V|mA|A|N)?'
    r'\s*(?:程度|ほど|前後|くらい)',
    re.UNICODE,
)

_VAGUE_CITE = '（特許法36条6項2号・審査基準第II部第2章第3節(5)）'


def check_vague_range(
    claims: dict[int, str],
    kinds: dict[int, str],
) -> list[dict[str, Any]]:
    """(5) 発明の範囲を曖昧にし得る表現を請求項から検出する。

    独立項: warning（発明特定事項として直接問題）
    従属項: info（独立項ほど厳格ではないが記録）
    """
    issues: list[dict] = []

    for num in sorted(claims.keys()):
        body = claims[num]
        is_independent = kinds.get(num) == KIND_INDEPENDENT
        level = 'warning' if is_independent else 'info'

        for keyword, label, hint in _VAGUE_KEYWORDS:
            if keyword in body:
                issues.append({
                    'claim': num,
                    'level': level,
                    'check': 'clarity_vague_range',
                    'msg': (
                        f'請求項{num}：{label}「{keyword}」が発明特定事項に含まれています。'
                        f'{hint}'
                        f'{_VAGUE_CITE}'
                    ),
                })

        for m in _NUMERIC_APPROX_PAT.finditer(body):
            matched = m.group(0).strip()
            issues.append({
                'claim': num,
                'level': level,
                'check': 'clarity_vague_range',
                'msg': (
                    f'請求項{num}：「{matched}」は数値範囲を曖昧にします。'
                    f'具体的な数値または数値範囲（〇〇以上〇〇以下）で記載してください。'
                    f'{_VAGUE_CITE}'
                ),
            })

    return issues


# ══════════════════════════════════════════════════════════
# (2e) 非技術的事項の記載
# ══════════════════════════════════════════════════════════

# (正規表現, カテゴリラベル, 補足メッセージ)
_NONTECHNICAL_PATS: list[tuple[re.Pattern, str, str]] = [
    # 企業名・製造者名
    (
        re.compile(
            r'(?:株式会社|有限会社|合同会社|合資会社)[^\s、。]{1,20}'
            r'|[^\s、。]{2,10}社(?:製|製造|の製品)',
            re.UNICODE,
        ),
        '企業名・製造者名',
        '企業名・製造者名による限定は非技術的事項です。技術的特徴（仕様・構造・機能）で記載してください。',
    ),
    # 価格
    (
        re.compile(r'\d[\d,]*\s*円', re.UNICODE),
        '価格',
        '価格による限定は非技術的事項です。',
    ),
    # 販売地域・流通地域
    (
        re.compile(
            r'(?:日本|海外|国内|アジア|欧米|北米|欧州|中国|米国|EU)'
            r'[^\s、。]{0,6}'
            r'(?:で|において|にて)(?:販売|流通|製造|輸出|輸入|市販)(?:され|する|した)',
            re.UNICODE,
        ),
        '販売地域',
        '販売地域・流通地域による限定は非技術的事項です（審査基準第II部第2章第3節(2)e）。',
    ),
    # 市販品
    (
        re.compile(r'市販(?:の|品|されている|品の)', re.UNICODE),
        '流通状態',
        '「市販の」等の流通状態による限定は非技術的事項となる可能性があります。',
    ),
]

_NONTECHNICAL_CITE = '（特許法36条6項2号）'


def check_nontechnical(claims: dict[int, str]) -> list[dict[str, Any]]:
    """(2e) 請求項中の非技術的事項（販売地域・企業名・価格等）を検出する。"""
    issues: list[dict] = []

    for num in sorted(claims.keys()):
        body = claims[num]
        for pat, label, hint in _NONTECHNICAL_PATS:
            for m in pat.finditer(body):
                matched = m.group(0)
                issues.append({
                    'claim': num,
                    'level': 'warning',
                    'check': 'clarity_nontechnical',
                    'msg': (
                        f'請求項{num}：{label}「{matched}」が含まれています。'
                        f'{hint}'
                        f'{_NONTECHNICAL_CITE}'
                    ),
                })

    return issues
