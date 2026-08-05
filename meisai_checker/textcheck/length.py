# -*- coding: utf-8 -*-
"""TC4: 一文の文字数チェック。

明細書の一文（句点「。」区切り）が長すぎる場合に警告する。
特許請求項は意図的に一文が長いため対象外。
明細書本文の段落内テキストのみを対象とする。

デフォルト閾値: 120文字（特許ライティングマニュアル第2版: 産業技術文書の目安100字を特許明細書向けに調整）
"""

from __future__ import annotations

import re


# 一文の最大文字数（これを超えると警告）
# 特許ライティングマニュアル第2版: 産業・技術文書では100文字が目安。
# 特許明細書は専門用語が長いため 120 字をデフォルトとする。
DEFAULT_MAX_CHARS = 120

# 段落番号パターン（本文の先頭から除去する）
_PARA_NUM_PAT = re.compile(r'【(\d{4,5})】(.*?)(?=【\d{4,5}】|【[^０-９0-9\d]|$)', re.DOTALL)

# 見出し行パターン
_HEADING_PAT = re.compile(r'^【[^】\d][^】]*】\s*$')

# 対象セクション: 【発明を実施するための形態】およびその旧式・実施例バリアント
_IMPL_PAT = re.compile(
    r'【(?:発明を実施するための(?:最良の)?形態'
    r'|発明の実施の形態'
    r'|実施(?:形態)?[０-９0-9]*'
    r')】(.*?)(?=\n【[^\d０-９】][^】]*】|\Z)',
    re.DOTALL,
)


def _split_sentences(text):
    """句点「。」で文を分割。段落番号・改行を正規化して返す。"""
    # 段落番号を除去
    text = re.sub(r'【\d{4,5}】', '', text)
    # 連続する空白・改行を単一スペースに
    text = re.sub(r'\s+', ' ', text).strip()
    # 句点で分割（読点は文を分けない）
    sentences = re.split(r'。', text)
    return [s.strip() for s in sentences if s.strip()]


def check_length(sections, max_chars=DEFAULT_MAX_CHARS):
    """TC4: 一文の文字数チェック。

    sections: split_sections() の戻り値
    max_chars: 一文の最大文字数（デフォルト 200）
    戻り値: issue dict のリスト
    """
    issues = []

    # 【発明を実施するための形態】のみを対象とする
    # 符号の説明・図面の説明等は文が長くなる構造のため除外
    raw = sections.get("_raw", "") or sections.get("description", "")
    impl_parts = _IMPL_PAT.findall(raw)
    desc = '\n'.join(impl_parts)
    if not desc:
        return issues

    # 段落ブロックごとにチェック
    for m in _PARA_NUM_PAT.finditer(desc):
        para_id = m.group(1)
        body = m.group(2).strip()
        if not body:
            continue
        # 見出し行のみで構成されるブロックはスキップ
        if _HEADING_PAT.match(body):
            continue

        sentences = _split_sentences(body)
        for sent in sentences:
            n = len(sent)
            if n > max_chars:
                # 前後30文字を抜粋してコンテキストとして表示
                snippet = sent[:30] + "…" + sent[-20:] if n > 50 else sent
                issues.append({
                    "milestone": "TC4", "level": "info",
                    "msg": (f"一文が{n}文字と長くなっています"
                            f"（上限目安：{max_chars}文字）"),
                    "detail": snippet,
                    "para_id": f"p-{para_id}",
                    "target_text": sent,  # GUI: クリック時にこの文をマーカー表示
                })

    return issues
