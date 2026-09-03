# -*- coding: utf-8 -*-
"""要約書チェック。

特許法施行規則第25条の2に基づく要約書の文字数 (400 字以内) と
必須項目 (【課題】【解決手段】) の存在をチェックする。
"""

from __future__ import annotations

import re


def check_abstract(sections):
    """要約の文字数・必須項目をチェック。"""
    issues = []
    ab = sections.get('abstract', '')
    if not ab:
        issues.append({
            'milestone': 'M5', 'level': 'info',
            'msg': '【要約】／【書類名】要約書 セクションが見つかりません',
        })
        return issues

    # 電子出願ソフトの文字数カウントに合わせる：
    # 【要約】／【書類名】要約書 の書類名見出し行のみ除外し、【課題】【解決手段】等の
    # 本文中の見出しはそのまま文字数に含める（公報上も本文として印刷されるため）。
    lines = ab.splitlines()
    body_start = 1 if lines and re.search(r'【要約】|【書類名】[\s　]*要約書', lines[0]) else 0
    text_only = ''.join(lines[body_start:])
    text_only = re.sub(r'^\s*\(\d+\)', '', text_only)   # (57)等の先頭プレフィックス除去
    text_only = re.sub(r'\s', '', text_only)             # 空白・改行除去
    char_count = len(text_only)

    if char_count > 400:
        issues.append({
            'milestone': 'M5', 'level': 'warning',
            'msg': f'要約が400字を超えています（{char_count}字）',
            'detail': '特許法施行規則第25条の2：要約書は400字以内',
        })
    else:
        issues.append({
            'milestone': 'M5', 'level': 'ok',
            'msg': f'要約文字数：{char_count}字（400字以内）',
        })

    # 必須項目チェック：【課題】【解決手段】
    for item in ('【課題】', '【解決手段】'):
        if item not in ab:
            issues.append({
                'milestone': 'M5', 'level': 'warning',
                'msg': f'要約に{item}がありません',
                'detail': '要約書の記載項目：【課題】【解決手段】',
            })

    return issues
