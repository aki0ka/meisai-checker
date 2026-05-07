# -*- coding: utf-8 -*-
"""M7b: 明確性要件追加チェック（曖昧表現・非技術的事項）の単体テスト。"""
from __future__ import annotations

import pytest

from meisai_checker.patent.clarity import check_vague_range, check_nontechnical
from meisai_checker.parser import KIND_INDEPENDENT, KIND_SINGLE_DEP


# ══════════════════════════════════════════════════════════
# check_vague_range
# ══════════════════════════════════════════════════════════

class TestCheckVagueRange:

    def _kinds(self, claims: dict[int, str]) -> dict[int, str]:
        return {1: KIND_INDEPENDENT, **{n: KIND_SINGLE_DEP for n in claims if n != 1}}

    # ── 検出すべきケース ──

    def test_tekigyou_independent(self):
        """独立項の「適宜」→ warning。"""
        claims = {1: '前記処理部が適宜データを変換する装置。'}
        issues = check_vague_range(claims, self._kinds(claims))
        assert len(issues) == 1
        assert issues[0]['level'] == 'warning'
        assert issues[0]['check'] == 'clarity_vague_range'
        assert '適宜' in issues[0]['msg']

    def test_preferred_independent(self):
        """独立項の「好ましくは」→ warning。"""
        claims = {1: '好ましくは前記センサは温度センサである装置。'}
        issues = check_vague_range(claims, self._kinds(claims))
        assert any(i['level'] == 'warning' and '好ましくは' in i['msg'] for i in issues)

    def test_preferred_dependent_is_info(self):
        """従属項の「好ましくは」→ info（warningより低い）。"""
        claims = {
            1: '処理部を有する装置。',
            2: '請求項１に記載の装置において、好ましくは前記処理部はGPUである装置。',
        }
        kinds = {1: KIND_INDEPENDENT, 2: KIND_SINGLE_DEP}
        issues = check_vague_range(claims, kinds)
        dep_issues = [i for i in issues if i['claim'] == 2]
        assert all(i['level'] == 'info' for i in dep_issues)

    def test_numeric_approx_yaku(self):
        """「約10mm」→ 数値近似として検出。"""
        claims = {1: '直径が約10mmの円形部材を有する装置。'}
        issues = check_vague_range(claims, self._kinds(claims))
        assert any('約' in i['msg'] or '数値範囲' in i['msg'] for i in issues)

    def test_numeric_approx_teido(self):
        """「50℃程度」→ 数値近似として検出。"""
        claims = {1: '温度が50℃程度の環境下で動作する装置。'}
        issues = check_vague_range(claims, self._kinds(claims))
        assert len(issues) >= 1

    def test_hitsuyou_ni_oujite(self):
        """「必要に応じて」→ 裁量的表現として検出。"""
        claims = {1: '必要に応じてデータを圧縮する処理部を備えた装置。'}
        issues = check_vague_range(claims, self._kinds(claims))
        assert any('必要に応じて' in i['msg'] for i in issues)

    # ── 検出しないケース ──

    def test_no_vague_expression(self):
        """曖昧表現がない請求項 → 検出なし。"""
        claims = {1: '処理部と記憶部とを有するデータ処理装置。'}
        issues = check_vague_range(claims, self._kinds(claims))
        assert issues == []

    def test_numeric_range_ok(self):
        """「10mm以上20mm以下」は曖昧でないため検出しない。"""
        claims = {1: '直径が10mm以上20mm以下の部材を有する装置。'}
        issues = check_vague_range(claims, self._kinds(claims))
        assert issues == []


# ══════════════════════════════════════════════════════════
# check_nontechnical
# ══════════════════════════════════════════════════════════

class TestCheckNontechnical:

    def test_kabushiki_gaisha(self):
        """「株式会社〜製」→ 企業名として検出。"""
        claims = {1: '株式会社ABCが製造するセンサを備えた装置。'}
        issues = check_nontechnical(claims)
        assert any(i['check'] == 'clarity_nontechnical' for i in issues)

    def test_sha_sei(self):
        """「〜社製」→ 製造者名として検出。"""
        claims = {1: 'ABC社製のカメラモジュールを備えた装置。'}
        issues = check_nontechnical(claims)
        assert any('企業名' in i['msg'] or '製造者' in i['msg'] for i in issues)

    def test_price(self):
        """「〜円」→ 価格として検出。"""
        claims = {1: '1000円以下で製造可能な電子部品を備えた装置。'}
        issues = check_nontechnical(claims)
        assert any('価格' in i['msg'] for i in issues)

    def test_sales_territory(self):
        """「日本において販売される」→ 販売地域として検出。"""
        claims = {1: '日本において販売される電子機器であって、処理部を備えた電子機器。'}
        issues = check_nontechnical(claims)
        assert any('販売地域' in i['msg'] for i in issues)

    def test_shihan(self):
        """「市販の」→ 流通状態として検出。"""
        claims = {1: '市販のバッテリーを使用した携帯機器。'}
        issues = check_nontechnical(claims)
        assert any('流通状態' in i['msg'] for i in issues)

    # ── 検出しないケース ──

    def test_no_nontechnical(self):
        """非技術的事項がない請求項 → 検出なし。"""
        claims = {1: '処理部と記憶部とを有するデータ処理装置。'}
        issues = check_nontechnical(claims)
        assert issues == []
