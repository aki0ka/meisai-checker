from meisai_checker.analyzer import analyze
from meisai_checker.preprocessor import normalize

_FILING = (
    '【書類名】明細書\n'
    '【発明の名称】装置\n'
    '【技術分野】\n'
    '【０００１】\n'
    '本発明は装置に関する。\n'
    '【書類名】特許請求の範囲\n'
    '【請求項１】\n'
    '部材を備える装置。\n'
    '【書類名】要約書\n'
    '【要約】\n'
    '【課題】装置を提供する。\n'
)


def _fc1(result):
    return [i for i in result['issues']['m8'] if i['check'] == 'FC1']


def test_fc1_not_raised_after_normalize_strips_shurui():
    norm = normalize(_FILING)
    assert '【書類名】' not in norm.text
    assert _fc1(analyze(norm.text, _skip_blocks=True, raw_text=_FILING)) == []


def test_fc1_raised_when_shurui_really_absent():
    text = _FILING.replace('【書類名】明細書\n', '')
    text = text.replace('【書類名】特許請求の範囲\n', '').replace('【書類名】要約書\n', '')
    assert _fc1(analyze(text, _skip_blocks=True, raw_text=text))
