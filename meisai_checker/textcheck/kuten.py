# -*- coding: utf-8 -*-
"""句点 (「。」) の有無チェック。

【発明の詳細な説明】の各段落について、末尾が句点で終わっているかを検査する。
段落番号【XXXX】単位でブロック化し、ブロック内の最後の非空行を「文末」とみなす。
【符号の説明】セクション内は句点不要として除外する。
"""

from __future__ import annotations

import re


# 句点不要とみなす行のパターン
_KUTEN_EXEMPT_PATS = [
    re.compile(r'^【'),                          # 【セクション名】【段落番号】等
    re.compile(r'^[０-９\d]+[．.]'),             # 「１．構成」等の章番号
    re.compile(r'^（[０-９\d一二三四五六七八九十あいうえおかきくけこ]+）'),  # （１）（あ）等
    re.compile(r'^[一二三四五六七八九十]+[、．]'), # 「一、」「二．」等
    re.compile(r'^[(（][０-９\d]+[)）]'),         # (1) （１） 等
    re.compile(r'^[・•]'),                       # 箇条書き
    re.compile(r'[＝=＋\-×÷≠≒≦≧∈∉∞√∫∑∂]'),   # 数式・化学式行
    re.compile(r'^[A-Za-zＡ-Ｚａ-ｚ０-９\d]+\s*[＝=]'),  # 変数定義式
]


def _is_kuten_exempt(line):
    """句点なしを許容する行か判定。"""
    s = line.strip()
    if not s or len(s) <= 1:
        return True
    for pat in _KUTEN_EXEMPT_PATS:
        if pat.search(s):
            return True
    return False


_HEADING_MAX_LEN = 40
_SENTENCE_END_RE = re.compile(
    r'(である|であり|する|した|される|された|れる|られる|ある|いる|なる|ない|できる|'
    r'ます|ました|です|でした|った|いた|んだ|いう|おり)$')


def _is_heading_like(line, prev):
    """段落末尾に置かれた見出し行（句点なし・短い・直前行が文末で閉じている）か判定。"""
    if len(line) > _HEADING_MAX_LEN or '。' in line or '、' in line:
        return False
    if _SENTENCE_END_RE.search(line):  # 用言終止形は見出しでなく文末の句点漏れ
        return False
    if prev.endswith(('。', '」', '）', ')')) or _is_kuten_exempt(prev):
        return True
    # 見出しが2行連続する場合（例：「図面の簡単な説明」＋UI行「閉じる」）
    return (len(prev) <= _HEADING_MAX_LEN and '。' not in prev and '、' not in prev
            and not _SENTENCE_END_RE.search(prev))


def check_kuten(sections):
    """詳細説明・請求の範囲で句点なしの文末を検出。"""
    issues = []
    # 対象: 発明の詳細な説明のみ（請求項は parse_claims で個別チェック済み）
    for sec_key in ('description',):
        text = sections.get(sec_key, '')
        if not text:
            continue
        lines = text.splitlines()
        # 段落ブロックを構築: 【XXXX】で区切られた段落内の末尾行を確認
        para_start = None
        para_lines = []
        in_fugo_section = False  # 符号の説明セクション内は句点不要

        def flush_para(plines, start_lineno):
            """段落末尾の句点チェック。段落全体を1文として扱う。"""
            # 末尾の見出し行（句点を打たない章・節タイトル）を除いた最後の本文行を探す
            body = [l.strip() for l in plines if l.strip()]
            while len(body) > 1 and _is_heading_like(body[-1], body[-2]):
                body.pop()
            if not body:
                return None
            last = body[-1]
            if _is_kuten_exempt(last):
                return None
            if last.endswith(('。', '」', '）', ')')):
                return None
            return {
                'milestone': 'M5', 'level': 'info',
                'msg': f'句点「。」で終わっていない段落があります',
                'detail': f'行{start_lineno}付近：{last[:40]}',
            }

        para_pat = re.compile(r'^【(\d{4,5})】')
        _fugo_heading = re.compile(r'^【符号の説明】')
        _next_heading = re.compile(r'^【[^０-９0-9][^】]*】')  # 次の見出し（段落番号以外）
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # 符号の説明セクションの開始を検出
            if _fugo_heading.match(stripped):
                if para_lines:
                    if not in_fugo_section:
                        iss = flush_para(para_lines, para_start)
                        if iss:
                            issues.append(iss)
                    para_lines = []
                in_fugo_section = True
                para_start = None
                continue
            # 符号の説明の後に別の見出しが来たら通常モードに戻る
            if in_fugo_section and _next_heading.match(stripped):
                in_fugo_section = False
            if _next_heading.match(stripped):
                # 【背景技術】【図１】【化１】等、段落番号以外の隅付き括弧行は段落の区切り
                if para_lines and not in_fugo_section:
                    iss = flush_para(para_lines, para_start)
                    if iss:
                        issues.append(iss)
                para_lines = []
                para_start = None
            elif para_pat.match(stripped):
                if para_lines and not in_fugo_section:
                    iss = flush_para(para_lines, para_start)
                    if iss:
                        issues.append(iss)
                if not in_fugo_section:
                    para_start = i
                    para_lines = [line]
                else:
                    para_start = None
                    para_lines = []
            elif para_start is not None and not in_fugo_section:
                para_lines.append(line)
        if para_lines and not in_fugo_section:
            iss = flush_para(para_lines, para_start)
            if iss:
                issues.append(iss)

    return issues
