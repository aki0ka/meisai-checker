# -*- coding: utf-8 -*-
"""M3: 唯一性崩壊警告の請求項内版（同一請求項内での同名詞の複数回裸定義）。

同一請求項内で同じ名詞が照応詞なしで複数回導入され、その後の「前記N」に
どちらを指すか特定できる情報（修飾節・分配マーカー）が伴っていない場合、
先行詞重複としてwarningを出す。既存の「先行詞重複」（複数請求項版）とは
別に、同一請求項内で完結するケースをカバーする。
"""
from __future__ import annotations

from meisai_checker.patent.anaphora import check_zenshou


def _issues(claims_text, dep_map=None):
    claims = {int(k): v for k, v in claims_text.items()}
    if dep_map is None:
        dep_map = {n: [] for n in claims}
    return check_zenshou(claims, dep_map)


def _warnings(claims_text, dep_map=None):
    return [i for i in _issues(claims_text, dep_map) if i.get('level') == 'warning']


def test_same_claim_bare_duplicate_is_warning():
    """推定手段と測定手段がそれぞれ独立に「弾力」を裸名詞で導入し、
    後続の「前記弾力」がどちらを指すか特定できないケース（実機で確認された偽陰性）。"""
    text = (
        '捏ね機により作られる生地の弾力を推定する推定手段と、'
        '前記捏ね機により実際に作られた生地の弾力を測定する測定手段と、'
        '前記弾力を示す文字列を表示する表示手段と、'
        'を有する測定結果表示機。'
    )
    warnings = [w for w in _warnings({1: text}) if w.get('noun') == '弾力']
    assert len(warnings) == 1
    assert '同一請求項内に2箇所存在' in warnings[0]['msg']


def test_same_claim_duplicate_disambiguated_by_modifier_clause_is_ok():
    """直前の修飾節（動詞由来）が別の前記/当該Xでどのインスタンスかを
    特定している場合は、複数回裸定義があっても曖昧ではない。"""
    text = (
        '第１光源からの光を透過させて、直線偏光の第１偏光面を回転させる第１媒体と、'
        '第２光源からの光を透過させて、直線偏光の第２偏光面を回転させる第２媒体と、'
        '前記第１媒体を透過した前記直線偏光の前記第１偏光面を検出する第１検出部と、'
        '前記第２媒体を透過した前記直線偏光の前記第２偏光面を検出する第２検出部と、'
        'を備える、光学装置。'
    )
    warnings = [w for w in _warnings({1: text}) if w.get('noun') == '直線偏光']
    assert warnings == []


def test_same_claim_duplicate_with_distributive_marker_is_ok():
    """「それぞれ」による分配参照は、曖昧参照ではなく意図的な集合参照。"""
    text = (
        '第１検出部の検出結果から光学ノイズを除去する第１除去部と、'
        '第２検出部の検出結果から光学ノイズを除去する第２除去部と、'
        '前記光学ノイズがそれぞれ除去された第１結果および第２結果を用いて差を計測する計測部と、'
        'を備える、計測装置。'
    )
    warnings = [w for w in _warnings({1: text}) if w.get('noun') == '光学ノイズ']
    assert warnings == []
