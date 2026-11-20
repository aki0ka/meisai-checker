# -*- coding: utf-8 -*-
"""多項従属請求項でも「前記X」直前の後付け修飾節のinfoを出す（各親スコープで先行詞が一意な場合）。"""
from meisai_checker.patent.anaphora import check_zenshou

_BASE = '素材Ａと、素材Ｂと、素材Ｃと、容器Ｄと、部品Ｅとを備える方法。'
_BODY = ('請求項１又は２に記載の方法であって、前記素材Ａを、前記素材Ｂである前記素材Ｃと、'
         '前記容器Ｄに含まれる前記部品Ｅとに分離する、方法。')


def test_multidep_pre_modifier_info():
    iss = check_zenshou({1: _BASE, 2: _BASE, 3: _BODY}, {1: [], 2: [], 3: [1, 2]})
    msgs = [i['msg'] for i in iss if i['level'] == 'info']
    assert any('「前記素材Ｂである前記素材Ｃ」' in m for m in msgs)
    assert any('「前記容器Ｄに含まれる前記部品Ｅ」' in m for m in msgs)
    assert not any(i['level'] == 'error' for i in iss)
