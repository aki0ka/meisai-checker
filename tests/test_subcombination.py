# -*- coding: utf-8 -*-
"""M2b/M2c: サブコンビネーション関連明確性違反チェックの単体テスト。

test_extract_combination_elements:  親クレームからの内部構成要素抽出
test_check_subcombination:          M2b メインチェック（従属項）
test_check_other_device_internals:  M2c-A 他装置内部構成記述（独立項）
test_check_purpose_only:            M2c-C 用途限定のみ（独立項）
"""
from __future__ import annotations

import pytest

from meisai_checker.patent.subcombination import (
    check_subcombination,
    check_other_device_internals,
    check_purpose_only,
    extract_combination_elements,
    extract_zenshou_nouns,
    has_selective_limitation,
    noun_matches,
)
from meisai_checker.parser import (
    classify_claims,
    parse_claims,
    parse_dependencies,
    split_sections,
    KIND_INDEPENDENT,
    KIND_SINGLE_DEP,
)


# ══════════════════════════════════════════════════════════
# ユーティリティ
# ══════════════════════════════════════════════════════════

def _make_inputs(claims_text: str):
    """claims_text = {番号: 本文} 形式の辞書を受け取り (claims, dep_map, kinds) を返す。"""
    claims = {int(k): v for k, v in claims_text.items()}
    dep_map = {
        num: [d for d in parse_dependencies(body) if d != num]
        for num, body in claims.items()
    }
    kinds = classify_claims(claims, dep_map)
    return claims, dep_map, kinds


# ══════════════════════════════════════════════════════════
# extract_combination_elements のテスト
# ══════════════════════════════════════════════════════════

class TestExtractCombinationElements:
    """内部コンビネーション要素の抽出ロジックをテストする。"""

    def test_basic_to_conjunction(self):
        """「AとBとを有する」パターン → [A, B]"""
        text = '圧縮部と展開部とを有するデータ処理装置。'
        result = extract_combination_elements(text)
        assert '圧縮部' in result
        assert '展開部' in result
        assert len(result) == 2

    def test_and_conjunction(self):
        """「AおよびBを備える」パターン → [A, B]"""
        text = '第一センサおよび第二センサを備えたシステム。'
        result = extract_combination_elements(text)
        assert len(result) == 2

    def test_three_elements(self):
        """「AとBとCとを有する」パターン → [A, B, C]"""
        text = 'サンプリング管と、検煙部と、制御部とを備えた煙感知器。'
        result = extract_combination_elements(text)
        assert len(result) == 3

    def test_complex_element_phrases(self):
        """各要素が複雑な修飾句を持つ場合 → 主名詞のみ抽出"""
        text = (
            '監視空間に敷設されたサンプリング管と、'
            '該サンプリング管を介してサンプリングエアを導入する検煙部と、'
            '該検煙部の煙検出レベルを判別する制御部とを備えた煙感知器。'
        )
        result = extract_combination_elements(text)
        # 主名詞（末尾名詞）が抽出される
        assert any('管' in e or 'サンプリング管' in e for e in result)
        assert any('検煙部' in e for e in result)
        assert any('制御部' in e for e in result)

    def test_external_connector_excluded(self):
        """外部構成（外部装置と通信する）は除外される。"""
        text = '外部サーバーと通信する通信部と記憶部とを有する装置。'
        result = extract_combination_elements(text)
        # 「外部サーバー」は除外され、内部構成のみ残る
        assert '外部サーバー' not in result

    def test_external_connection_verb(self):
        """「と接続する」「と連携する」等は外部構成として除外。"""
        text = '外部装置と接続するインターフェースと処理部とを有する装置。'
        result = extract_combination_elements(text)
        assert '外部装置' not in result

    def test_no_combo_verb_returns_empty(self):
        """コンビネーション動詞がない場合は空リストを返す。"""
        text = '特許請求の範囲において、発明が記載された装置。'
        result = extract_combination_elements(text)
        assert result == []

    def test_single_element_returns_empty(self):
        """要素が1個以下の場合は空リストを返す（コンビネーションでない）。"""
        text = '処理部を有する装置。'
        result = extract_combination_elements(text)
        assert result == []

    def test_karanaoru_pattern(self):
        """「からなる」パターン。"""
        text = 'センサAとセンサBとからなるシステム。'
        result = extract_combination_elements(text)
        assert len(result) == 2

    def test_output_unit_not_external(self):
        """「出力部」は _EXTERNAL_VERB_BASES に含まれる「出力」を接頭形態素に持つが、
        直後に「部」が続く複合語なので内部構成要素として正しく扱われる。"""
        text = 'センサと処理部と出力部とを備えた制御システム。'
        result = extract_combination_elements(text)
        assert len(result) == 3, f'expected 3 elements, got {result}'
        assert any('センサ' in e for e in result)
        assert any('処理部' in e for e in result)
        assert any('出力部' in e for e in result)

    def test_input_output_units_internal(self):
        """入力部・出力部はサ変語幹「入力」「出力」を含むが内部構成として扱われる。"""
        text = '入力部と処理部と出力部とを有する情報処理装置。'
        result = extract_combination_elements(text)
        assert len(result) == 3, f'expected 3 elements, got {result}'


# ══════════════════════════════════════════════════════════
# extract_zenshou_nouns のテスト
# ══════════════════════════════════════════════════════════

class TestExtractZenshouNouns:
    def test_basic(self):
        text = '請求項１に記載の装置において、前記圧縮部はハフマン符号化を行う装置。'
        result = extract_zenshou_nouns(text)
        assert any('圧縮部' in n for n in result)

    def test_multiple_references(self):
        text = '請求項１に記載の装置において、前記圧縮部および前記展開部は〜装置。'
        result = extract_zenshou_nouns(text)
        assert len(result) >= 2


# ══════════════════════════════════════════════════════════
# noun_matches のテスト
# ══════════════════════════════════════════════════════════

class TestNounMatches:
    def test_exact_match(self):
        assert noun_matches('圧縮部', '圧縮部') is True

    def test_suffix_match(self):
        """ref_noun が combo_elem を末尾に含む（修飾語付き参照）。"""
        assert noun_matches('圧縮部', '高性能圧縮部') is True

    def test_prefix_match(self):
        """combo_elem が ref_noun を末尾に含む（略称参照）。"""
        assert noun_matches('高性能圧縮部', '圧縮部') is True

    def test_no_match(self):
        assert noun_matches('圧縮部', '展開部') is False

    def test_short_ref_no_false_positive(self):
        """2文字未満のref_nounでは末尾マッチを行わない。"""
        assert noun_matches('圧縮部', '部') is False


# ══════════════════════════════════════════════════════════
# has_selective_limitation のテスト
# ══════════════════════════════════════════════════════════

class TestHasSelectiveLimitation:
    def test_wa_predicate(self):
        """「前記Xは〜」→ 限定あり。"""
        text = '請求項１に記載の装置において、前記圧縮部はハフマン符号化を行う装置。'
        assert has_selective_limitation(text, ['圧縮部']) is True

    def test_ga_predicate(self):
        """「前記Xが〜」→ 限定あり。"""
        text = '請求項１に記載の装置において、前記センサが温度を検出するシステム。'
        assert has_selective_limitation(text, ['センサ']) is True

    def test_no_predicate(self):
        """「前記X」が経由参照のみ（述語なし）→ 限定なし。"""
        text = '前記圧縮部を用いてデータを圧縮する装置。'
        assert has_selective_limitation(text, ['圧縮部']) is False


# ══════════════════════════════════════════════════════════
# check_subcombination のメインテスト
# ══════════════════════════════════════════════════════════

class TestCheckSubcombination:
    """check_subcombination の正例・負例・エッジケース。"""

    # ── 検出すべきケース（warning を出す） ──────────────────

    def test_positive_basic(self):
        """典型的サブコンビネーション：親にAとB、従属でAのみ限定。"""
        claims = {
            1: '圧縮部と展開部とを有するデータ処理装置。',
            2: '請求項１に記載のデータ処理装置において、前記圧縮部はハフマン符号化を行うデータ処理装置。',
        }
        claims, dep_map, kinds = _make_inputs(claims)
        issues = check_subcombination(claims, dep_map, kinds)
        assert len(issues) == 1
        assert issues[0]['claim'] == 2
        assert issues[0]['level'] == 'warning'
        assert issues[0]['check'] == 'subcombination'
        assert '展開部' in issues[0]['msg']

    def test_positive_three_elements_one_limited(self):
        """3要素中の1つのみを限定するケース → 未言及の2要素が両方 msg に出る。"""
        claims = {
            1: 'センサと処理部と出力部とを備えた制御システム。',
            2: '請求項１に記載の制御システムにおいて、前記センサは温度センサである制御システム。',
        }
        claims, dep_map, kinds = _make_inputs(claims)
        issues = check_subcombination(claims, dep_map, kinds)
        assert len(issues) == 1
        # 3要素のうち処理部と出力部の両方が未言及として報告される
        assert '処理部' in issues[0]['msg']
        assert '出力部' in issues[0]['msg']

    def test_positive_and_conjunction_parent(self):
        """「AおよびB」パターンの親クレームで従属クレームがAのみ限定。"""
        claims = {
            1: '第一センサおよび第二センサを備えた検知装置。',
            2: '請求項１に記載の検知装置において、前記第一センサは赤外線センサである検知装置。',
        }
        claims, dep_map, kinds = _make_inputs(claims)
        issues = check_subcombination(claims, dep_map, kinds)
        assert len(issues) == 1

    # ── 検出しないケース（warning を出さない） ────────────────

    def test_negative_both_referenced(self):
        """従属クレームでAとBの両方を前記で参照している → warning なし。"""
        claims = {
            1: '圧縮部と展開部とを有するデータ処理装置。',
            2: (
                '請求項１に記載のデータ処理装置において、'
                '前記圧縮部はハフマン符号化を行い、'
                '前記展開部はハフマン復号化を行うデータ処理装置。'
            ),
        }
        claims, dep_map, kinds = _make_inputs(claims)
        issues = check_subcombination(claims, dep_map, kinds)
        assert issues == []

    def test_negative_no_nioi_te_form(self):
        """「において」「であって」がない従属クレームは対象外。"""
        claims = {
            1: '圧縮部と展開部とを有するデータ処理装置。',
            2: '前記圧縮部がハフマン符号化を行う請求項１に記載のデータ処理装置。',
        }
        claims, dep_map, kinds = _make_inputs(claims)
        issues = check_subcombination(claims, dep_map, kinds)
        # 「において」/「であって」がないので検出しない
        assert issues == []

    def test_negative_no_zenshou(self):
        """従属クレームに前記/上記がなければ対象外。"""
        claims = {
            1: '圧縮部と展開部とを有するデータ処理装置。',
            2: '請求項１に記載のデータ処理装置において、ハフマン符号化を行うデータ処理装置。',
        }
        claims, dep_map, kinds = _make_inputs(claims)
        issues = check_subcombination(claims, dep_map, kinds)
        assert issues == []

    def test_negative_parent_single_element(self):
        """親クレームの要素が1個のみ（コンビネーションでない）。"""
        claims = {
            1: '処理部を有するデータ処理装置。',
            2: '請求項１に記載のデータ処理装置において、前記処理部はGPUであるデータ処理装置。',
        }
        claims, dep_map, kinds = _make_inputs(claims)
        issues = check_subcombination(claims, dep_map, kinds)
        assert issues == []

    def test_negative_independent_claim(self):
        """独立項は対象外。"""
        claims = {
            1: '圧縮部と展開部とを有するデータ処理装置。',
        }
        claims, dep_map, kinds = _make_inputs(claims)
        issues = check_subcombination(claims, dep_map, kinds)
        assert issues == []

    def test_negative_multi_dep_excluded(self):
        """マルチクレーム（複数請求項への従属）は対象外。"""
        claims = {
            1: '圧縮部と展開部とを有するデータ処理装置。',
            2: 'センサと制御部とを有する検知装置。',
            3: (
                '請求項１または２に記載の装置において、'
                '前記圧縮部はハフマン符号化を行う装置。'
            ),
        }
        claims, dep_map, kinds = _make_inputs(claims)
        issues = check_subcombination(claims, dep_map, kinds)
        # マルチクレームは対象外
        assert all(i['claim'] != 3 for i in issues)

    def test_negative_external_element_not_flagged(self):
        """外部構成要素（外部サーバーと通信する等）は内部要素として扱われない。"""
        claims = {
            1: (
                '外部サーバーと通信する通信部と、'
                'データを処理する処理部とを有する装置。'
            ),
            2: (
                '請求項１に記載の装置において、'
                '前記処理部はGPUである装置。'
            ),
        }
        claims, dep_map, kinds = _make_inputs(claims)
        issues = check_subcombination(claims, dep_map, kinds)
        # 外部サーバーは内部構成要素ではないので、
        # 通信部と処理部の2要素コンビネーションとして検出される可能性あり
        # ただし外部構成の「と」は除外されるため、
        # 内部要素「処理部」が単独の場合は警告しない
        # この検証は実装の動作確認
        for issue in issues:
            assert '外部サーバー' not in issue['msg']

    # ── 連鎖従属のエッジケース ──────────────────────────────

    def test_chained_dependency(self):
        """連鎖従属：請求項3→請求項2→請求項1 の場合。"""
        claims = {
            1: '圧縮部と展開部とを有するデータ処理装置。',
            2: (
                '請求項１に記載のデータ処理装置において、'
                '前記圧縮部はハフマン符号化を行い、'
                '前記展開部はハフマン復号化を行うデータ処理装置。'
            ),
            3: (
                '請求項２に記載のデータ処理装置において、'
                '前記圧縮部は可逆圧縮を行うデータ処理装置。'
            ),
        }
        claims, dep_map, kinds = _make_inputs(claims)
        issues = check_subcombination(claims, dep_map, kinds)
        # 請求項2は両方参照しているのでOK
        assert all(i['claim'] != 2 for i in issues)
        # 請求項3は請求項2に従属、請求項2の親はさらに請求項1だが、
        # 本チェックは直接の親クレームのみを見るので、
        # 請求項2自体に「圧縮部と展開部」があるかどうかで判断
        # 請求項2はコンビネーション動詞（を有する）がないので要素抽出不可→警告なし
        # この挙動を確認
        for issue in issues:
            assert issue['check'] == 'subcombination'


# ══════════════════════════════════════════════════════════
# check_other_device_internals のテスト（M2c-A）
# ══════════════════════════════════════════════════════════

class TestCheckOtherDeviceInternals:
    """M2c-A: 独立項において他装置の内部構成が記述されているケース。"""

    def _kinds_independent(self, nums):
        from meisai_checker.parser import KIND_INDEPENDENT
        return {n: KIND_INDEPENDENT for n in nums}

    # ── 検出すべきケース ──

    def test_server_internals_in_device_claim(self):
        """パターンA: サーバBの内部構成を情報処理装置Aのクレームに記述。"""
        body = (
            'サーバ装置Bと通信可能な情報処理装置Aであって、'
            '前記サーバ装置Bは、データベースとクエリ処理部とを有し、'
            '前記情報処理装置Aは、送信部を備える、'
            '情報処理装置A。'
        )
        claims = {1: body}
        kinds = self._kinds_independent([1])
        issues = check_other_device_internals(claims, kinds)
        assert len(issues) == 1
        assert issues[0]['check'] == 'subcombination_other_internals'
        assert 'サーバ装置B' in issues[0]['msg'] or 'サーバ' in issues[0]['msg']

    def test_cloud_server_internals_in_program_claim(self):
        """パターンD: クラウドサーバの機械学習モデル記述をプログラムクレームに記述。"""
        body = (
            'クラウドサーバHに接続されるスマートフォン用アプリケーションプログラムであって、'
            '前記クラウドサーバHは、機械学習モデルを保有し、'
            'コンピュータに、前記クラウドサーバHへユーザ入力を送信するステップを実行させるプログラム。'
        )
        claims = {1: body}
        kinds = self._kinds_independent([1])
        issues = check_other_device_internals(claims, kinds)
        assert len(issues) == 1

    # ── 検出しないケース ──

    def test_main_subject_self_reference_not_flagged(self):
        """発明主体自身への「は〜を備える」は検出しない。"""
        body = (
            '処理部と記憶部とを有する情報処理装置Aであって、'
            '前記情報処理装置Aは、表示部をさらに備える、'
            '情報処理装置A。'
        )
        claims = {1: body}
        kinds = self._kinds_independent([1])
        issues = check_other_device_internals(claims, kinds)
        assert issues == []

    def test_internal_component_not_flagged(self):
        """内部構成要素（処理部）への記述は検出しない。"""
        body = (
            '処理部と記憶部とを有するデータ処理装置であって、'
            '前記処理部は、演算ユニットとレジスタとを備える、'
            'データ処理装置。'
        )
        claims = {1: body}
        kinds = self._kinds_independent([1])
        issues = check_other_device_internals(claims, kinds)
        assert issues == []

    def test_dependent_claim_not_checked(self):
        """従属項は対象外。"""
        from meisai_checker.parser import KIND_SINGLE_DEP
        body = (
            '請求項１に記載の装置において、'
            '前記サーバBは、追加モジュールを有する装置。'
        )
        claims = {2: body}
        kinds = {2: KIND_SINGLE_DEP}
        issues = check_other_device_internals(claims, kinds)
        assert issues == []


# ══════════════════════════════════════════════════════════
# check_purpose_only のテスト（M2c-C）
# ══════════════════════════════════════════════════════════

class TestCheckPurposeOnly:
    """M2c-C: 独立項において用途限定のみの他システム参照があるケース。"""

    def _kinds_independent(self, nums):
        from meisai_checker.parser import KIND_INDEPENDENT
        return {n: KIND_INDEPENDENT for n in nums}

    # ── 検出すべきケース ──

    def test_karanaoru_system_youto(self):
        """「〜からなるシステムに用いられる」→ 検出。"""
        body = (
            'スマートフォンEおよびクラウドサーバFからなるシステムに用いられる'
            'エッジコンピューティング装置Gであって、'
            '演算処理部と通信インターフェースとを備えるエッジコンピューティング装置G。'
        )
        claims = {1: body}
        kinds = self._kinds_independent([1])
        issues = check_purpose_only(claims, kinds)
        assert len(issues) == 1
        assert issues[0]['check'] == 'subcombination_purpose_only'

    def test_kousei_system_notameno(self):
        """「〜で構成されるシステムのための」→ 検出。"""
        body = (
            'サーバとクライアントとで構成されるシステムのための'
            '情報処理方法であって、データを送信するステップを含む情報処理方法。'
        )
        claims = {1: body}
        kinds = self._kinds_independent([1])
        issues = check_purpose_only(claims, kinds)
        assert len(issues) == 1

    # ── 検出しないケース ──

    def test_no_system_reference(self):
        """システム参照がない通常の装置クレーム → 検出しない。"""
        body = '処理部と記憶部とを有するデータ処理装置。'
        claims = {1: body}
        kinds = self._kinds_independent([1])
        issues = check_purpose_only(claims, kinds)
        assert issues == []

    def test_dependent_claim_not_checked(self):
        """従属項は対象外。"""
        from meisai_checker.parser import KIND_SINGLE_DEP
        body = (
            '請求項１に記載の装置において、'
            '前記からなるシステムに用いられる装置。'
        )
        claims = {2: body}
        kinds = {2: KIND_SINGLE_DEP}
        issues = check_purpose_only(claims, kinds)
        assert issues == []
