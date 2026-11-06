"""カギカッコ内の「要素名＋符号」は【符号の説明】の未使用警告の対象外。"""
from meisai_checker.patent.fugo import check_fugo_setsumeisho

_TMPL = """【発明を実施するための形態】
【０００２】
　制御部１０は、作業者が所持する%sに接続される。
【符号の説明】
【０００３】
　１０　制御部
　９５　外部端末
"""


def _unused(body):
    issues, _ = check_fugo_setsumeisho(
        [{'fugo': '１０', 'names': ['制御部'], 'count': 1, 'is_dup': False}],
        _TMPL % body)
    return [i for i in issues if '使用されていません' in i['msg']]


def test_quoted_name_fugo_counts_as_used():
    assert _unused('「外部端末９５」') == []


def test_really_unused_still_reported():
    assert len(_unused('外部端末')) == 1
