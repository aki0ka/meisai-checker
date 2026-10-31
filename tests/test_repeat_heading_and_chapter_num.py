# -*- coding: utf-8 -*-
"""願書の見出し重複（発明者複数）と章立て番号の反復誤検知の回帰テスト。"""
from meisai_checker.structure.sections import check_structure
from meisai_checker.textcheck.repetition import check_repetition


def _dup_msgs(text):
    return [i['msg'] for i in check_structure(text) if '重複' in i['msg']]


def test_multiple_inventors_not_duplicate():
    text = ('【発明者】\n【住所又は居所】　東京都\n【氏名】　山田　太郎\n'
            '【発明者】\n【住所又は居所】　大阪府\n【氏名】　鈴木　花子\n'
            '【特許出願人】\n【識別番号】　１２３\n'
            '【技術分野】\n【０００１】\n　本発明は装置に関する。\n')
    assert _dup_msgs(text) == []


def test_real_section_duplicate_still_detected():
    text = ('【技術分野】\n【０００１】\n　本発明は装置に関する。\n'
            '【技術分野】\n【０００２】\n　本発明は装置に関する。\n')
    assert any('技術分野' in m for m in _dup_msgs(text))


def _rep_msgs(body):
    sections = {'description': f'【０００１】\n　{body}\n'}
    return [i['msg'] for i in check_repetition(sections) if '直接繰り返' in i['msg']]


def test_chapter_number_not_repetition():
    assert _rep_msgs('１－１－１．情報処理装置の構成') == []


def test_word_repetition_still_detected():
    assert any('センサセンサ' in m for m in _rep_msgs('センサセンサが検出する。'))
