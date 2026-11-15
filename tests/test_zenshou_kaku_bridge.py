# -*- coding: utf-8 -*-
"""M3: 「前記各X」検出漏れの修正の単体テスト。

「各前記X」（各が前記の直前）には専用の検出ルール（分配するドメインが先行詞側に無い）があるが、
逆順の「前記各X」を検出する専用ルールが無く、noun="各X"（「各」込み）の
字面一致だけに頼っていたため、Xが「複数のX」等で正しく群導入されていても
「前記各X」が「先行詞がスコープ内に見つかりません」という誤エラーに
なっていた（特許7900541・7919105・7917958・7919028等で発見）。

さらにこの誤エラーは、後続の「当該X」束縛変数回収（②、「各Xについて、
当該X」で本来正常に動くはずのパターン）まで連鎖的に壊していた
（特許7917958で発見）。
"""
from __future__ import annotations

from meisai_checker.patent.anaphora import check_zenshou


def _errors(text, dep_map=None):
    issues = check_zenshou({1: text}, dep_map or {1: []})
    return [i for i in issues if i.get('level') == 'error']


def test_zenshou_kaku_bridge_plural_intro_ok():
    """「複数のX」で群導入済みなら「前記各X」はエラーにならない。"""
    text = ('複数のセンサを備える検出部と、'
            '前記各センサの出力値を取得する取得部とを備える、装置。')
    assert _errors(text) == []


def test_zenshou_kaku_bridge_bare_intro_ok():
    """裸のXで導入済みでも「前記各X」はエラーにならない（回帰確認）。"""
    text = 'センサを備える検出部と、前記各センサの出力値を取得する取得部とを備える、装置。'
    assert _errors(text) == []


def test_zenshou_kaku_bridge_no_intro_still_error():
    """Xが一度も導入されていなければ「前記各X」は従来通りエラー（過剰抑制の回帰ガード）。"""
    text = '検出部を備える装置であって、前記各センサの出力値を取得する取得部とを備える、装置。'
    errors = _errors(text)
    assert len(errors) == 1
    assert errors[0]['noun'] == '各センサ'


def test_zenshou_kaku_bridge_cross_claim():
    """従属請求項をまたいだ群導入でも「前記各X」が解決できる（特許7919028型）。"""
    dep_map = {1: [], 2: [1]}
    claims = {
        1: '複数のセンサを備える検出部を備える、装置。',
        2: '前記各センサの出力値を取得する取得部を備える、請求項1に記載の装置。',
    }
    issues = check_zenshou(claims, dep_map)
    assert [i for i in issues if i.get('level') == 'error'] == []


def test_zenshou_kaku_bridge_toukei_cascade_ok():
    """「前記各Xについて、当該X」のカスケードも解決する（特許7917958型）。"""
    text = ('複数のセンサを備える検出部と、'
            '前記各センサについて、当該センサの出力値を取得する取得部とを備える、装置。')
    assert _errors(text) == []


def test_kaku_zenshou_order_unaffected():
    """語順が逆の「各前記X」は今回の修正対象外（回帰ガード：別ルールのまま）。"""
    text = '各前記端末は通信する、装置。'
    errors = _errors(text)
    assert len(errors) == 1
    assert errors[0]['noun'] == '端末'


def test_kaku_zenshou_message_has_no_unfounded_assertion():
    """「各前記X」の文言は、根拠を示せない理論名・「論理矛盾」の言い切りを含まず、
    先行詞を「複数のN」として導入し直す案を最初に示す。"""
    from meisai_checker.patent.anaphora import check_zenshou
    iss = check_zenshou({1: '複数の端末を備え、各前記端末は通信する、装置。'}, {1: []})
    msgs = [i['msg'] for i in iss if '各前記端末' in i['msg']]
    assert len(msgs) == 1
    m = msgs[0]
    assert 'Russell' not in m and '論理矛盾' not in m and 'ι演算子' not in m
    assert m.index('先行詞を「複数の端末」として導入する') < m.index('前記複数の端末のそれぞれ')
