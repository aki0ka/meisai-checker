# -*- coding: utf-8 -*-
"""2026-11-18 実機気づき2件の回帰テスト。

1. 「発報情報である受信情報」が「報情報」に欠けて定義構文infoに出る
   （UniDicが「発」を記号品詞に割るため）。
2. 「前記管理制御盤側」：M3はerrorを出さないのに一覧だけ「先行詞なし」になる不整合
   （「盤側」が一語化し位置接尾辞が単独トークンにならない）。
"""
from __future__ import annotations

from meisai_checker.analyzer import analyze
from meisai_checker.patent.anaphora import check_zenshou
from meisai_checker.tokenizer import _tokenize, _noun_span, _span_to_str


def test_hatsuho_not_split():
    toks = _tokenize('操作情報又は発報情報である受信情報を受信する')
    k = next(i for i, t in enumerate(toks) if t['surf'] == '発')
    assert _span_to_str(_noun_span(toks, k)) == '発報情報'


def test_hatsuho_definition_message_keeps_full_name():
    t = ('複数の子機と管理制御盤とを備え、前記管理制御盤は、'
         '操作情報又は発報情報である受信情報を受信する、監視システム。')
    msgs = [i['msg'] for i in check_zenshou({1: t}, {1: []})]
    assert any('「発報情報である受信情報」' in m for m in msgs)
    assert not any('「報情報' in m for m in msgs)


def test_noun_group_list_agrees_with_m3_for_fused_loc_suffix():
    """M3がerrorを出さない「前記管理制御盤側」を、一覧が「先行詞なし」にしない。"""
    txt = ('【書類名】特許請求の範囲\n【請求項１】\n'
           '管理制御盤と複数の子機とを備え、前記管理制御盤は、保守モードにおいて、'
           '前記管理制御盤側で保守対象として指定された子機から送信された信号を受信する、'
           '監視システム。\n')
    r = analyze(txt)
    g = {x['noun']: x for x in r['noun_groups']}
    assert g['管理制御盤側']['error'] is False
    assert g['管理制御盤側']['refs'][0]['first_claim'] == 1
