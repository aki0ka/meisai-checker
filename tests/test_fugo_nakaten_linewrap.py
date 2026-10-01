# -*- coding: utf-8 -*-
"""M4: 中点（・）を含む複合名詞が改行で分断されても1語として認識されるか。

PDF/Word由来のテキストでは、レイアウト上の行折り返しが単語境界と無関係に
入ることがある。中点は見た目が区切り文字に似ているため、そこで改行された
テキスト（例：「教育・\nスキルデータベース」）が「教育」と「スキル
データベース」という別々の要素名に分断され、同じ符号に複数の要素名が
対応しているという誤検知（M4）を引き起こしていた。
"""
from __future__ import annotations

from meisai_checker.patent.fugo import _extract_elements_tokens, _names_equivalent


def test_nakaten_compound_split_across_linebreak_is_joined():
    text = '記憶部は、教育・\nスキルデータベース１３３を備える。'
    drawing_pairs, _ = _extract_elements_tokens(text)
    names = [name for name, fugo, *_ in drawing_pairs if fugo == '１３３']
    assert names == ['教育・スキルデータベース']


def test_nakaten_compound_same_line_still_works():
    text = '記憶部は、教育・スキルデータベース１３３を備える。'
    drawing_pairs, _ = _extract_elements_tokens(text)
    names = [name for name, fugo, *_ in drawing_pairs if fugo == '１３３']
    assert names == ['教育・スキルデータベース']


def test_names_equivalent_rejects_dropped_nakaten_prefix():
    """「教育・スキルデータベース」(本文) に対し「スキルデータベース」
    (符号の説明、中点以前が脱落) は内容語の欠落であり不一致として扱う。"""
    assert _names_equivalent('スキルデータベース', '教育・スキルデータベース') is False


def test_names_equivalent_allows_known_modifier_prefix_diff():
    """量化/序列修飾語の有無だけの差異は一致として扱う。"""
    assert _names_equivalent('センサ', '第１のセンサ') is True
    assert _names_equivalent('センサ', '複数のセンサ') is True
    assert _names_equivalent('センサ', '一方のセンサ') is True
