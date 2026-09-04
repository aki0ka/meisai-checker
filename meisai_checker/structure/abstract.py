# -*- coding: utf-8 -*-
"""要約書チェック。

特許法施行規則第25条の2に基づく要約書の文字数 (400 字以内) と
必須項目 (【課題】【解決手段】) の存在をチェックする。
"""

from __future__ import annotations

import re


# 要約欄の見出し行（文字数に算入しない）。
# 公報形式の「(57)【要約】」「(57)【要約】（修正有）」も見出しとして扱う。
_ABSTRACT_HEAD_PAT = re.compile(
    r'^(?:\(\d+\))?[\s　]*(?:【書類名】[\s　]*要約書|【要約】)'
    r'(?:[\s　]*（修正有）)?')
# 【選択図】は要約欄の外（文字数に算入しない）
_SENTAKUZU_PAT = re.compile(r'^【選択図】')
# 公報のページ番号行（000002 等）は本文ではない
_PAGENUM_PAT = re.compile(r'^\d{4,}$')


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
    #   除外 … 【書類名】要約書・【要約】の見出し、【選択図】以降
    #   算入 … 【課題】【解決手段】等の本文中の見出し
    #          （公報上も要約欄の本文として印刷されるため）
    body = []
    for line in ab.splitlines():
        s = line.strip()
        if _SENTAKUZU_PAT.match(s):
            break                                    # 【選択図】以降は要約欄外
        if _PAGENUM_PAT.match(s):
            continue                                 # 公報のページ番号行
        s = _ABSTRACT_HEAD_PAT.sub('', s, count=1)   # 見出し自体は算入しない
        body.append(s)
    text_only = ''.join(body)
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
