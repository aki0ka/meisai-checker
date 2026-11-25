# -*- coding: utf-8 -*-
"""TC11: 表記ゆれ（同一文書内の混在）チェック。"""
from __future__ import annotations

import json

import pytest

from meisai_checker.textcheck.variant_pairs import check_variant_pairs, load_pairs


def _check(desc='', claims='', pairs=None):
    sections = {'description': desc, 'claims': claims, 'abstract': ''}
    return check_variant_pairs(sections, pairs=pairs or load_pairs(user_path=None))


def _labels(issues):
    return [i['msg'] for i in issues]


def test_mix_detected_across_sections():
    issues = _check(
        desc='【０００１】\n予め設定する。',
        claims='【請求項１】\nあらかじめ設定する装置。')
    assert len(issues) == 1
    assert '予め／あらかじめ' in issues[0]['msg']


def test_single_variant_not_flagged():
    assert _check(desc='【０００１】\n予め設定する。予め取得する。') == []


def test_minority_variant_is_flagged_when_no_recommend():
    issues = _check(desc='【０００１】\n例えば設定する。\n【０００２】\n例えば取得する。\n'
                         '【０００３】\nたとえば決める。')
    assert len(issues) == 1
    assert issues[0]['para_id'] == 'p-０００３'
    assert 'たとえば' in issues[0]['detail']


def test_recommend_flags_non_recommended():
    issues = _check(desc='【０００１】\nただし、Aとする。\n【０００２】\n但し、Bとする。\n'
                         '【０００３】\n但し、Cとする。')
    assert issues
    assert all('但し' in i['detail'] for i in issues)
    assert 'ただし' in issues[0]['msg']


def test_nado_ignores_douto_and_kinto():
    # 「同等」「均等」は接尾辞の「等」ではない
    assert _check(desc='【０００１】\n同等の値を、均等に配置するなど行う。') == []


def test_nado_mix_detected():
    issues = _check(desc='【０００１】\nセンサ等を備える。\n【０００２】\nカメラなどを備える。')
    assert len(issues) == 1
    assert 'など／等' in issues[0]['msg']


def test_shitagatte_ignores_verb_ni_shitagatte():
    assert _check(desc='【０００１】\nしたがって動作する。\n'
                       '【０００２】\n指示に従って動作する。') == []


def test_shitagatte_conjunction_mix():
    issues = _check(desc='【０００１】\nしたがって動作する。\n【０００２】\nＡである。従って、Ｂとなる。')
    assert issues


def test_kumiawase_mix():
    issues = _check(desc='【０００１】\n組合せを選ぶ。\n【０００２】\n組み合わせを選ぶ。')
    assert len(issues) == 1


def test_claim_anchor():
    issues = _check(claims='【請求項１】\n予めＡする。\n【請求項２】\nあらかじめＢする。',
                    pairs=[p for p in load_pairs(user_path=None)
                           if p['id'] == 'arakajime'])
    assert issues[0]['claim'] == 1   # 推奨は「あらかじめ」なので「予め」側を指摘
    assert 'あらかじめ' in issues[0]['msg']


def test_expected_pairs_loaded():
    ids = [p['id'] for p in load_pairs(user_path=None)]
    assert 'okonau' in ids          # 保留していた行う／行なうも混在指摘として有効
    assert 'kakaru' in ids          # soft として有効


def test_user_override(tmp_path):
    up = tmp_path / 'variant_pairs.json'
    up.write_text(json.dumps({'pairs': [
        {'id': 'arakajime', 'enabled': False},
        {'id': 'custom', 'label': 'ユーザ定義', 'variants': [{'text': '装置'}, {'text': '機器'}]},
    ]}), encoding='utf-8')
    pairs = load_pairs(user_path=str(up))
    ids = [p['id'] for p in pairs]
    assert 'arakajime' not in ids and 'custom' in ids
    issues = _check(desc='【０００１】\n装置を使う。\n【０００２】\n機器を使う。', pairs=pairs)
    assert len(issues) == 1


def test_uketsuke_okurigana_mix():
    issues = _check(desc='【０００１】\n要求を受け付ける。\n【０００２】\n要求を受付ける。')
    assert len(issues) == 1
    assert '受け付ける／受付ける' in issues[0]['msg']


def test_uketsuke_noun_alone_not_counted():
    assert _check(desc='【０００１】\n受付部が要求を受け付ける。') == []


def test_okonau_mix_flagged_without_recommend():
    issues = _check(desc='【０００１】\n処理を行う。\n【０００２】\n処理を行う。\n【０００３】\n処理を行なう。')
    assert len(issues) == 1
    assert issues[0]['para_id'] == 'p-０００３' and '行なう' in issues[0]['detail']
    assert '推奨' not in issues[0]['msg']


def test_okonau_single_variant_not_flagged():
    assert _check(desc='【０００１】\n処理を行なう。\n【０００２】\n結果を行なう。') == []


def test_arawasu_mix_flagged():
    issues = _check(desc='【０００１】\n値を表す。\n【０００２】\n値を表わす。\n【０００３】\n値を表す。')
    assert len(issues) == 1 and '表わす' in issues[0]['detail']


def test_arawareru_mix_flagged():
    assert len(_check(desc='【０００１】\n図形が現れる。\n【０００２】\n図形が現われる。')) == 1


@pytest.mark.parametrize('text,hit', [
    ('但し、Aとする。', '但し'),
    ('A且つBとする。', '且つ'),
    ('或いはCとする。', '或いは'),
    ('処理の為に実行する。', '為に'),
    ('次の様な構成とする。', '様な'),
    ('実行出来る。', '出来る'),
    ('値が無い場合', '無い'),
    ('取り付けて頂く。', 'て頂'),
    ('説明して下さい。', 'て下さ'),
])
def test_deprecated_single_detected(text, hit):
    issues = _check(desc='【０００１】\n' + text)
    assert any(hit in i['msg'] and i['level'] == 'info' for i in issues), issues


@pytest.mark.parametrize('text', [
    '行為に基づいて実行する。',       # 「行為に」は「為に」ではない
    '同様な構成とする。',            # 「同様な」
    '有無を判定する。',
    '出来事を記録する。',
    '予め設定する。',                # 予めは単独では指摘しない
])
def test_deprecated_not_detected(text):
    assert _check(desc='【０００１】\n' + text) == [], text


def test_okuri_noun_mix_with_recommend():
    issues = _check(desc='【０００１】\n取付けを行う。\n【０００２】\n取り付けを行う。')
    assert len(issues) == 1 and '取り付け' in issues[0]['detail']
    assert '取付け' in issues[0]['msg']


def test_okuri_verb_form_not_counted():
    assert _check(desc='【０００１】\n取付けを行う。\n【０００２】\n部品を取り付ける。') == []


def test_kumiawase_verb_not_counted():
    assert _check(desc='【０００１】\n組合せを選ぶ。\n【０００２】\nＡとＢを組み合わせる。') == []


def test_soft_pair_is_info_with_softer_message():
    issues = _check(desc='【０００１】\n発明に係る装置。\n【０００２】\n時間にかかる装置。')
    assert len(issues) == 1
    assert issues[0]['level'] == 'info'
    assert '使い分け' in issues[0]['msg'] and '統一' not in issues[0]['msg']


def test_nado_tou_is_soft():
    issues = _check(desc='【０００１】\nセンサ等を備える。\n【０００２】\nカメラなどを備える。')
    assert len(issues) == 1 and issues[0]['level'] == 'info'


def test_strong_pair_is_warning():
    issues = _check(desc='【０００１】\n予め設定する。\n【０００２】\nあらかじめ設定する。')
    assert issues and issues[0]['level'] == 'warning'
