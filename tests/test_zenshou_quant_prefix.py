# -*- coding: utf-8 -*-
"""M3: 照応詞の直前に量化修飾語を置く書き方（「複数の前記X」型）の検出テスト。

Zenn記事「Claudeと特許明細書チェッカーを作った」で件数を示した
「複数の前記」「各前記」「それぞれの前記」に加え、その表記違い
（各々・夫々）と助数詞つき（複数個の・２つの）も同じ扱いにする。
"""
from __future__ import annotations

import pytest

from meisai_checker.patent.anaphora import check_zenshou

_TEMPLATE = '複数の端末を管理する管理部と、{}に通知する通知部とを備える、装置。'


def _quant_msgs(phrase):
    issues = check_zenshou({1: _TEMPLATE.format(phrase)}, {1: []})
    return [i['msg'] for i in issues
            if '曖昧になりやすい' in i['msg'] or '論理矛盾' in i['msg']
            or '何を一つずつ指しているか' in i['msg']]


@pytest.mark.parametrize('phrase', [
    '複数の前記端末',
    '各前記端末',
    'それぞれの前記端末',
    '各々の前記端末',
    '夫々の前記端末',        # MeCabは「夫」＋「々」に分割する
    'おのおのの前記端末',
    '複数個の前記端末',      # 「複数」＋「個」の2トークン
    '多数個の前記端末',
    '２つの前記端末',        # 数詞＋助数詞
    '2個の前記端末',
    '三つの前記端末',
    '数個の前記端末',
    '全ての前記端末',
    '一部の前記端末',
])
def test_quant_prefix_detected(phrase):
    assert _quant_msgs(phrase), phrase


@pytest.mark.parametrize('phrase', [
    '前記端末',              # 素の照応詞
    '前記複数の端末',        # 正しい語順（量化子が照応詞の後ろ）
    '制御部の前記端末',      # 量化子ではない「Nの」
    '総数の前記端末',        # 語中に「数」を含むが量化子ではない
])
def test_quant_prefix_not_detected(phrase):
    assert _quant_msgs(phrase) == [], phrase


@pytest.mark.parametrize('phrase', [
    'それぞれの前記端末',
    '各々の前記端末',
    '夫々の前記端末',
    'おのおのの前記端末',
])
def test_distrib_quant_prefix_points_out_ambiguity_only(phrase):
    """それぞれ・各々等は分配演算子であり、必ず「何を一つずつ見るか」という
    ドメインを要する。前置で単独に置かれると、そのドメインが（a）名詞自身の
    複数性なのか（b）別の先行する複数物なのかが文面から特定できず、
    名詞が単数導入の場合は明確性要件リスクにもなる。これは書き換え先を
    一つに断定できる問題ではないため、単一の書き換え例は提示せず、
    問題の所在（ドメイン不明）の指摘のみに留める（2026-10-06ユーザー指摘で
    「前記Xのそれぞれ」という単一の書き換え先を断定する旧版から変更）。
    """
    msgs = _quant_msgs(phrase)
    assert msgs, phrase
    assert any('何を一つずつ指しているか' in m for m in msgs), phrase
    # 旧版のような単一の書き換え先の断定（「のように後置してください」等）は含めない
    assert not any('後置してください' in m for m in msgs), phrase
