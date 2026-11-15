"""M3: 「前記」直後の修飾語の扱い（名詞句の始点規則）。
理論: docs/zenshou_theory.md。記述限定詞は後付けなら再絞り込み禁止、
「一又は複数の」は数「複数」の保存、「別の」は「他の」と同じ序列修飾。
"""
import pytest

from meisai_checker.analyzer import analyze


def _m3(body):
    r = analyze("【書類名】特許請求の範囲\n【請求項１】\n" + body + "\n")
    return r["issues"]["m3"]


@pytest.mark.parametrize("mod", ["所定の", "任意の", "特定の", "一定の", "所望の"])
def test_descriptive_limiter_after_bare_antecedent_is_retighten(mod):
    iss = _m3(f"タイミングでデータを保存し、前記{mod}タイミングでデータを復元する、方法。")
    assert [i["level"] for i in iss] == ["warning"]
    assert "再絞り込み禁止" in iss[0]["msg"]
    assert "見つかりません" not in iss[0]["msg"]


def test_descriptive_limiter_without_any_antecedent_stays_error():
    iss = _m3("データを保存し、前記所定のタイミングでデータを復元する、方法。")
    assert [i["level"] for i in iss] == ["error"]


def test_descriptive_limiter_matching_antecedent_ok():
    assert _m3("所定のタイミングでデータを保存し、前記所定のタイミングでデータを復元する、方法。") == []


@pytest.mark.parametrize("conj", ["又は", "若しくは", "もしくは", "あるいは"])
def test_one_or_plural_not_fragmented(conj):
    body = (f"一{conj}複数のタイミングでデータを保存し、"
            f"前記一{conj}複数のタイミングでデータを復元する、方法。")
    assert _m3(body) == []


def test_betsu_no_name_kept_whole():
    assert _m3("別のタイミングでデータを保存し、前記別のタイミングでデータを復元する、方法。") == []
    iss = _m3("タイミングでデータを保存し、前記別のタイミングでデータを復元する、方法。")
    assert "前記別のタイミング」の先行詞" in iss[0]["msg"]


# ---- 序数の表記ゆれ（第１／第1／第一）----

@pytest.mark.parametrize("a,b", [("第１", "第1"), ("第１", "第一"), ("第一", "第１"), ("第二", "第２")])
def test_ordinal_notation_variant_is_warning_not_missing(a, b):
    iss = _m3(f"{a}のデータを受信し、前記{b}のデータを保存する、方法。")
    assert [i["level"] for i in iss] == ["warning"]
    assert "序数の表記が異なります" in iss[0]["msg"]
    assert "見つかりません" not in iss[0]["msg"]


@pytest.mark.parametrize("f", ["第１", "第1", "第一", "第１０"])
def test_ordinal_same_notation_ok(f):
    assert _m3(f"{f}のデータを受信し、前記{f}のデータを保存する、方法。") == []


def test_ordinal_different_value_stays_error():
    iss = _m3("第１のデータを受信し、前記第２のデータを保存する、方法。")
    assert [i["level"] for i in iss] == ["error"]


def test_ordinal_value():
    from meisai_checker.patent.anaphora import _ordinal_value
    assert [_ordinal_value(x) for x in ("１", "1", "一", "十", "十二", "二十", "２０", "第")] \
        == [1, 1, 1, 10, 12, 20, 20, None]
