"""M3: 照応詞の直後に導入子（ある・或る・何らかの・いずれかの）が来る誤用の検出。

理論: 「前記」は既出の対象を指す参照、「ある」等は新しい対象を導入する語。
一つの名詞句で導入と参照は両立しない（範疇の衝突）。
検証ケース表: docs/zenshou_case_table.md（A1〜A4）
"""
import pytest

from meisai_checker.analyzer import analyze


def _m3(body):
    r = analyze("【書類名】特許請求の範囲\n【請求項１】\n" + body + "\n")
    return r["issues"]["m3"]


def _collision(issues):
    return [i for i in issues if "導入と参照を同時に" in i["msg"]]


@pytest.mark.parametrize("body", [
    "あるタイミングでデータを保存し、前記あるタイミングでデータを復元する、方法。",
    "所定のタイミングでデータを保存し、前記あるタイミングでデータを復元する、方法。",
    "端末と、サーバとを備え、前記或る端末は通信する、システム。",
    "端末と、サーバとを備え、前記何らかの端末は通信する、システム。",
    "端末と、サーバとを備え、前記いずれかの端末は通信する、システム。",
])
def test_introducer_after_zenshou_warns(body):
    hits = _collision(_m3(body))
    assert len(hits) == 1
    assert hits[0]["level"] == "warning"


@pytest.mark.parametrize("body", [
    "端末と、サーバとを備え、前記端末は通信する、システム。",
    "端末と、サーバとを備え、前記端末あるいはサーバは通信する、システム。",
    "ある端末と、サーバとを備え、前記端末は通信する、システム。",
])
def test_no_false_positive(body):
    assert _collision(_m3(body)) == []


# ---- 後付け修飾（記述照応詞）: 出来事に支えられていれば info、なければ warning ----

def _levels(body, needle="記述照応詞"):
    iss = _m3(body)
    return [i["level"] for i in iss if needle in i["msg"] or "再絞り込み" in i["msg"]]


@pytest.mark.parametrize("body,level", [
    # 先行する「受信」に支えられた産出記述 → info
    ("データを受信し、前記受信したデータを保存する、方法。", "info"),
    # 全文の繰り返し → info（記述照応詞としての通知のみ）
    ("受信したデータを保持し、前記受信したデータを保存する、方法。", "info"),
    ("高精度な処理部を備え、前記高精度な処理部は動作する、装置。", "info"),
    # 出来事の支えがない修飾 → warning（再絞り込み禁止）
    ("データを保持し、前記受信したデータを保存する、方法。", "warning"),
    ("データを受信し、前記新たなデータを保存する、方法。", "warning"),
    # 名詞語幹＋な（形容動詞）で「前記高精度」と誤認しない
    ("処理部を備え、前記高精度な処理部は動作する、装置。", "warning"),
])
def test_description_anaphor_level(body, level):
    assert _levels(body) == [level]
    assert not [i for i in _m3(body) if i["level"] == "error"]
