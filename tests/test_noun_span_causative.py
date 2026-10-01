# -*- coding: utf-8 -*-
"""M6: サ変名詞＋使役「させる」構文の語幹が先行詞/技術用語として登録されない問題。

「Xを回転又は揺動させるY」のように、使役の助動詞「せる」で終わる動詞句の
語幹（回転・揺動等）は、既存の「サ変語幹＋する」収束処理（_noun_span）が
「するの直後が実質名詞以外なら除外しない」という設計のところ、実際には
「するの直後が実質名詞以外なら全て除外する」という逆の判定になっていたため、
使役の助動詞「せる」が直後に来るケース（実質名詞ではない）も除外されていた。

「回転する部材」のように plain な「する」が実質名詞に直接続く場合は、部材
自身が回転するという一体の概念なので語幹（回転）を独立登録しないのが正しい。
一方「回転させる軸」は使役であり、軸は回転"させる"側（原因側）で、回転その
ものとは別概念なので語幹（回転）を独立した技術用語として登録すべきである。
"""
from __future__ import annotations

from meisai_checker.analyzer import analyze
from meisai_checker.patent.support import extract_nouns_for_support
from meisai_checker.tokenizer import _collect_defined_nouns, _tokenize


def _defined(text):
    return set(_collect_defined_nouns(_tokenize(text)).keys())


def test_causative_stem_is_registered_even_with_coordination():
    nouns = _defined('多面鏡を回転又は揺動させる軸を備える。')
    assert '回転' in nouns
    assert '揺動' in nouns


def test_causative_stem_is_registered_without_coordination():
    assert '回転' in _defined('回転させる軸を備える。')
    assert '揺動' in _defined('揺動させる軸を備える。')


def test_plain_suru_modifying_real_noun_still_excluded():
    """「回転する部材」の「回転」は従来通り独立登録しない（回帰防止・M3用）。"""
    assert '回転' not in _defined('回転する部材を備える。')


def test_m6_extracts_sahen_stem_even_when_adjacent_to_real_noun():
    """M6専用: 「揺動する部材」「回転させる軸」の揺動/回転は、直後が実質名詞
    であってもM6のチェック対象語句として抽出する（_defined とは逆の挙動）。"""
    assert '揺動' in extract_nouns_for_support('部材が回転又は揺動する軸を備える。')
    assert '揺動' in extract_nouns_for_support('揺動する部材を備える、装置。')


def test_m6_catches_claim_verb_not_supported_by_description():
    """クレームに「揺動する部材」とあり、本文に「回転する部材」しかない場合、
    名詞「部材」は一致するが動作「揺動」は本文のどこにも現れないため、
    サポート要件違反として検出されるべき（名詞のみの一致判定では見逃す）。"""
    text = (
        '【書類名】明細書\n'
        '【発明の名称】テスト装置\n'
        '【特許請求の範囲】\n'
        '【請求項１】\n'
        '揺動する部材を備える、装置。\n'
        '【発明の詳細な説明】\n'
        '【技術分野】\n'
        '【0001】\n'
        '本発明はテスト装置に関する。\n'
        '【発明を実施するための形態】\n'
        '【0002】\n'
        '装置は、回転する部材を有する。\n'
        '【実施例】\n'
        '【0003】\n'
        '実施例説明。\n'
    )
    result = analyze(text)
    msgs = [i['msg'] for i in result['issues']['m6']]
    assert any('揺動' in m for m in msgs)
