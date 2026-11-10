"""2026-11-10 実機気づき2件の回帰テスト。"""
from meisai_checker.patent.fugo import _extract_elements_tokens
from meisai_checker.structure.docfields import check_docfields


def test_adjv_prefix_kept_in_element_name():
    """「最適」(MeCab形状詞)が要素名の先頭から脱落しない。"""
    pairs, _ = _extract_elements_tokens("装置１は、最適初期刺激ＤＢ１０を備える。")
    assert ('最適初期刺激ＤＢ', '１０') in [(p[0], p[1]) for p in pairs]


def test_adjv_with_na_is_still_modifier():
    """「最適な〜」は修飾であり要素名に含めない。"""
    pairs, _ = _extract_elements_tokens("最適な初期刺激ＤＢ１０を備える。")
    assert [(p[0], p[1]) for p in pairs] == [('初期刺激ＤＢ', '１０')]


def _filing(claims_name):
    return (f"【書類名】明細書\n【発明の名称】テスト\n【技術分野】\n【０００１】本発明。\n"
            f"【書類名】{claims_name}\n【請求項１】装置。\n"
            f"【書類名】要約書\n【要約】\n【課題】あ\n")


def test_pct_claims_name_not_flagged():
    msgs = [i['msg'] for i in check_docfields(_filing('請求の範囲'))]
    assert not any('特許請求の範囲 が見つかりません' in m for m in msgs)


def test_missing_claims_still_flagged():
    text = "【書類名】明細書\n【発明の名称】テスト\n【書類名】要約書\n【要約】\n"
    msgs = [i['msg'] for i in check_docfields(text)]
    assert any('特許請求の範囲 が見つかりません' in m for m in msgs)
