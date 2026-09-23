# -*- coding: utf-8 -*-
"""M3: 「前記Xの各々」の先行詞Xが単数で導入されている場合の検出。

「前記Xの各々」「前記Xのそれぞれ」は、Xが「複数のX」等で導入されていなくても
先行詞が見つかるため OK になり、単数導入のXに分配をかける誤りを見逃していた。

- Xが数を示さず導入 → warning
- Xが分配の中で導入（「複数の筐体のそれぞれに収容されたX」）→ info
  （複数かどうかは述語の意味次第で、「収容された」なら筐体ごとに別のX、
   「検査する」なら１つのXでもよい。字面からは決まらない）
"""
from __future__ import annotations

from meisai_checker.patent.anaphora import check_zenshou


def _post_distrib(text):
    issues = check_zenshou({1: text}, {1: []})
    return [i for i in issues if '後置の分配' in i['msg'] or '分配の中で導入' in i['msg']]


def test_bare_intro_warning():
    text = '検査装置を有し、前記検査装置の各々は、電磁波検知装置である、検査システム。'
    found = _post_distrib(text)
    assert [i['level'] for i in found] == ['warning']


def test_dependent_intro_info():
    for pred in ('に収容された', 'を検査する'):
        text = (f'複数の筐体のそれぞれ{pred}検査装置を有し、'
                '前記検査装置の各々は、電磁波検知装置である、検査システム。')
        found = _post_distrib(text)
        assert [i['level'] for i in found] == ['info'], pred


def test_quantified_intro_ok():
    for intro, ref in (('２つの検査装置', '前記２つの検査装置のそれぞれ'),
                       ('１つ以上の端末', '前記１つ以上の端末のそれぞれ'),
                       ('一対の電極', '前記電極の各々')):
        text = f'{intro}を有し、{ref}は、部材である、システム。'
        assert _post_distrib(text) == [], intro


def test_floating_quantifier_ok():
    """後置の数量詞で数を宣言していれば対象外（特許7873165で発見）。"""
    text = ('組み合わせを、１以上含むパターンを出力し、'
            '前記組み合わせのそれぞれに対する結果を生成する、装置。')
    assert _post_distrib(text) == []


def test_coordination_ok():
    text = ('第１検出部と、第２検出部と、を有し、'
            '前記第１検出部および前記第２検出部のそれぞれは、センサである、装置。')
    assert _post_distrib(text) == []


def test_multiple_bare_intro_ok():
    """裸で複数回導入された名詞への「前記Xのそれぞれ」は分配参照として正当。"""
    text = ('光を検出する検出部と、音を検出する検出部と、を有し、'
            '前記検出部のそれぞれは、センサである、装置。')
    assert _post_distrib(text) == []
