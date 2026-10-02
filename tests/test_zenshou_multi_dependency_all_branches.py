# -*- coding: utf-8 -*-
"""M3: 多項従属の先行詞チェックはANYではなくALLでなければならない。

「請求項１，８又は９のいずれか１項に記載の」のような多項従属は、どの直接親を
選んで読んでも明確でなければならない（特許法36条6項2号）。従来の実装は
_parent_results の any() で判定しており、直接親のうち1つ（例：請求項９、
その祖先に請求項８を含む）で先行詞が見つかれば、他の親（請求項１）に
先行詞が無くてもエラーにならないというバグがあった（2026-10-02 実機報告）。
"""
from __future__ import annotations

from meisai_checker.patent.anaphora import check_zenshou


def _errors(claims, dep_map):
    issues = check_zenshou(claims, dep_map)
    return [i for i in issues if i.get('level') == 'error']


def test_multi_dependency_missing_antecedent_in_one_branch_is_error():
    claims = {
        1: '駆動部を備える、装置。',
        8: '請求項１に記載の装置であって、検出部をさらに備える、装置。',
        9: '請求項８に記載の装置であって、前記検出部の出力値を取得する取得部をさらに備える、装置。',
        10: '請求項１，８又は９のいずれか１項に記載の装置であって、'
            '前記検出部における異常を判定する判定部をさらに備える、装置。',
    }
    dep_map = {1: [], 8: [1], 9: [8], 10: [1, 8, 9]}

    errs = _errors(claims, dep_map)
    assert len(errs) == 1
    assert '請求項10' in errs[0]['msg']
    assert '前記検出部' in errs[0]['msg']
    # どの枝で欠落しているかを具体的に示すこと
    assert '[1]' in errs[0]['msg']


def test_multi_dependency_antecedent_in_all_branches_is_ok():
    claims = {
        1: '検出部を備える、装置。',
        2: '駆動部をさらに備える、請求項１に記載の装置。',
        3: '請求項１又は２に記載の装置であって、前記検出部における異常を判定する判定部をさらに備える、装置。',
    }
    dep_map = {1: [], 2: [1], 3: [1, 2]}

    assert _errors(claims, dep_map) == []
