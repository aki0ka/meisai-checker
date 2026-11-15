"""「配置図５３７」のように構成要素名が「図」で終わる場合を図参照と誤認しない。"""
from meisai_checker.structure.ref_numbers import (
    check_figure_consistency, check_figure_notation)

DRAWINGS = '【図１】図１は実施形態のブロック図である。'


def _warn(desc):
    return check_figure_consistency({'description': desc, 'drawings': DRAWINGS})


def test_compound_name_not_figure_ref():
    for name in ('配置図', '断面図', 'ブロック図', '平面図'):
        assert _warn(f'{name}５３７を表示する。') == []


def test_real_figure_ref_still_detected():
    assert len(_warn('図２は配置を示す。')) == 1
    assert len(_warn('実施形態の図２を参照する。')) == 1
    assert _warn('図１に示す。') == []


def test_figure_notation_not_compound():
    assert check_figure_notation({'description': '配置図１（a）を表示する。'}) == []
    assert len(check_figure_notation({'description': '図１（a）を参照する。'})) == 1
