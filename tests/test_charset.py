# -*- coding: utf-8 -*-
"""textcheck/charset.py: JIS X 0208チェックのメインペインジャンプ対応・回帰テスト"""
from meisai_checker.textcheck.charset import check_jis


def test_warn_char_in_claims_has_claim_jump_target():
    """マッピングズレ記号（波ダッシュ等）が請求項中にある場合、claim番号とtarget_textが付与される"""
    sections = {
        'claims': '【請求項１】\nダミー。\n【請求項２】\n計測値が約10〜20の範囲となる装置。\n',
    }
    issues = check_jis(sections)
    assert len(issues) == 1
    iss = issues[0]
    assert iss['claim'] == 2
    assert 'para_id' not in iss
    assert iss['target_text'] == '〜'
    assert 'U+301C' in iss['msg']  # 先頭文字にもコードポイントを併記


def test_warn_char_in_description_has_para_id_jump_target():
    """マッピングズレ記号が明細書本文中にある場合、para_idとtarget_textが付与される"""
    sections = {
        'description': '【技術分野】\n【0001】\nダミー。\n【0002】\n計測範囲は約10〜20°Cである。\n',
    }
    issues = check_jis(sections)
    assert len(issues) == 1
    iss = issues[0]
    assert iss['para_id'] == 'p-0002'
    assert 'claim' not in iss
    assert iss['target_text'] == '〜'


def test_ng_char_gets_jump_target_too():
    """JIS X 0208外文字（NEC特殊文字等）にも同様にジャンプ対象が付与される"""
    sections = {
        'claims': '【請求項１】\n請求項１に記載の装置であって、①更なる特徴を有する。\n',
    }
    issues = check_jis(sections)
    assert len(issues) == 1
    iss = issues[0]
    assert iss['claim'] == 1
    assert iss['target_text'] == '①'


def test_control_char_ff_has_no_target_text():
    """改ページ文字（制御文字）はtarget_textによるテキスト検索ハイライト対象外"""
    sections = {
        'description': '【0001】\n本文\x0c続き\n',
    }
    issues = check_jis(sections)
    assert len(issues) == 1
    assert 'target_text' not in issues[0]
