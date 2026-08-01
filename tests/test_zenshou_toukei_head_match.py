# -*- coding: utf-8 -*-
"""M3: 「当該」③ 主要部一致（修飾語脱落）ERROR の単体テスト。

「所定のN」等の限定詞（_LIMITERS）付きで導入された先行詞を、当該・該で
限定詞を落とした核名詞（主要部）のみで参照するのは、候補数を問わず
曖昧性が確定するためERROR（project_toukei_checker_design③）。
「前記」側の同じ限定詞ブリッジ（既存の偽陽性抑制策）は変更しない。
"""
from __future__ import annotations

from meisai_checker.patent.anaphora import check_zenshou


def _issues(claims_text, dep_map=None):
    claims = {int(k): v for k, v in claims_text.items()}
    if dep_map is None:
        dep_map = {n: [] for n in claims}
    return check_zenshou(claims, dep_map)


def _errors(claims_text, dep_map=None):
    return [i for i in _issues(claims_text, dep_map) if i.get('level') == 'error']


def test_toukei_head_only_match_is_error():
    text = ('所定の分岐画像を生成する生成部と、'
            '当該分岐画像を表示する表示部とを備える、画像処理装置。')
    errors = _errors({1: text})
    assert len(errors) == 1
    assert errors[0]['noun'] == '分岐画像'
    assert '所定の分岐画像' in errors[0]['msg']


def test_zenshou_head_only_match_still_ok():
    """前記側の限定詞ブリッジ（既存の偽陽性抑制策）は変更しない回帰ガード。"""
    text = ('所定の分岐画像を生成する生成部と、'
            '前記分岐画像を表示する表示部とを備える、画像処理装置。')
    assert _errors({1: text}) == []


def test_toukei_bound_variable_recovery_still_ok():
    """②束縛変数回収（各Nの分配）は引き続き正常（回帰ガード）。"""
    text = ('複数の記憶情報を記憶する記憶部と、'
            '前記複数の記憶情報における各記憶情報について、'
            '当該記憶情報の抽象度を示す情報を生成する生成部とを備える、装置。')
    assert _errors({1: text}) == []


def test_toukei_numeral_bridge_out_of_scope():
    """例外4（数詞ブリッジ「１つのN」）は③の対象外のまま（現行仕様の固定化）。"""
    text = ('１つのセンサを備える検出部と、'
            '当該センサの出力値を取得する取得部とを備える、装置。')
    assert _errors({1: text}) == []


def test_toukei_ordinal_modifier_generic_error_not_head_match():
    """他方の等（_ORDINAL_MODS）はそもそも例外3対象外。従来通り一般ERRORになる
    （③専用メッセージ「主要部のみと一致します」ではないことを確認）。
    """
    text = ('他方のセンサの出力値を取得する取得部と、'
            '当該センサの状態を判定する判定部とを備える、装置。')
    errors = _errors({1: text})
    assert len(errors) == 1
    assert '主要部のみと一致します' not in errors[0]['msg']
