# -*- coding: utf-8 -*-
"""M3: 例外4（数詞ブリッジ）の「Ｎ以上の」「Ｎつ以上の」拡張の単体テスト。

「１つ以上のセンサ」「２以上のセンサ」等の _RANGE_SUFFIXES 付き数量修飾で
導入された核名詞は、「１つのセンサ」（既存の例外4）と同様に裸の「前記N」で
照応できる必要がある。修正前は「以上/以下」を含む前置部がトークン数不一致で
例外4の判定から漏れ、「先行詞がスコープ内に見つかりません」の誤エラーになっていた。
"""
from __future__ import annotations

import pytest

from meisai_checker.patent.anaphora import check_zenshou


def _errors(text):
    issues = check_zenshou({1: text}, {1: []})
    return [i for i in issues if i.get('level') == 'error']


@pytest.mark.parametrize('intro', [
    '１つ以上のセンサ',
    '２以上のセンサ',
    '１個以上のセンサ',
    '５以下のセンサ',
])
def test_range_quantifier_bridge_ok(intro):
    text = f'{intro}を備える検出部と、前記センサの出力値を取得する取得部とを備える、装置。'
    assert _errors(text) == [], text


def test_plural_intro_still_distinct_from_range():
    """「複数の」は従来通り群として扱われ、裸の「前記N」は別警告（回帰ガード）。"""
    text = '複数のセンサを備える検出部と、前記センサの出力値を取得する取得部とを備える、装置。'
    issues = check_zenshou({1: text}, {1: []})
    assert _errors(text) == []
    assert any('群' in i['msg'] for i in issues)
