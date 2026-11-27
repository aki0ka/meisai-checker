# -*- coding: utf-8 -*-
"""M3：前記Xの直前の連体修飾は、直後が「の＋名詞」でも通知する（2026-11-28）。

「選択された前記領域の一部」は、修飾が前記領域にかかるとも一部にかかるとも読める。
前者なら余剰修飾、後者でも前記が挟まるため部分的に余剰の形になるので、
info で二通りの読みを告知して書き手に考えさせる。
"""
from meisai_checker import analyze

_CLAIM1 = "端末を複数備え、領域を選択する選択部と、表示部と、を備えるシステム。"


def _m3(c2):
    t = (f"【書類名】特許請求の範囲\n【請求項１】\n　{_CLAIM1}\n"
         f"【請求項２】\n　{c2}、請求項１に記載のシステム。\n")
    return [i for i in analyze(t)['issues']['m3'] if i.get('claim') == 2]


def test_plain_pre_modifier_still_detected():
    r = _m3("選択された前記端末を表示する")
    assert len(r) == 1 and r[0]['level'] == 'info'
    assert '絞り込みとして機能しない' in r[0]['msg'] and '二通り' not in r[0]['msg']


def test_pre_modifier_followed_by_no_noun_gives_two_readings_info():
    r = _m3("選択された前記領域の一部を表示する")
    assert len(r) == 1 and r[0]['level'] == 'info'
    assert 'にかかるとも' in r[0]['msg'] and '一部' in r[0]['msg']
