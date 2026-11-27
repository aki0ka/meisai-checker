# -*- coding: utf-8 -*-
"""段落末尾の句点漏れ検出（段落内に別の「。」があっても検出／見出し行・符号の説明は除外）。"""
from meisai_checker.textcheck.kuten import check_kuten


def _run(desc):
    return check_kuten({'description': desc})


def test_missing_kuten_at_paragraph_end_even_if_earlier_kuten():
    assert len(_run("【０００１】\n本発明は装置に関する。次に構成を示す\n")) == 1


def test_short_sentence_without_kuten_is_flagged():
    assert len(_run("【０００１】\n第一の文である。\n第二の文である\n")) == 1


def test_trailing_heading_not_flagged():
    assert _run("【０００１】\n前の文である。\n実施形態１\n【０００２】\n次の文である。\n") == []


def test_double_heading_not_flagged():
    assert _run("【０００１】\n前の文である。\n図面の簡単な説明\n閉じる\n") == []


def test_fugo_section_not_flagged():
    assert _run("【０００１】\n文である。\n【符号の説明】\n１　装置\n２　部材\n") == []


def test_bracket_heading_terminates_paragraph():
    # 【背景技術】等の隅付き括弧見出しで段落を閉じ、手前の句点漏れを検出する
    d = "【技術分野】\n　【０００１】\n本発明は装置に関する\n【背景技術】\n　【０００２】\n従来は〜である。\n"
    r = _run(d)
    assert len(r) == 1 and '本発明は装置に関する' in r[0]['detail']


def test_bracket_subitems_not_flagged():
    d = "　【０００６】\n　　【特許文献１】　　特開２００３－００００００号公報\n　【０００７】\n　　【図１】　説明図である\n"
    assert _run(d) == []
