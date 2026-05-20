# -*- coding: utf-8 -*-
"""TC7: 読点欠落チェック（特許ライティングマニュアル第2版 5-2/5-3）。

5-2: 接続語句（しかし、また、したがって 等）のあとに読点がない
5-3: 原因・理由・条件を表す節（〜ので、〜ため、〜によっては 等）のあとに読点がない

スコープ: 明細書本文（発明の詳細な説明）
"""

from __future__ import annotations

import re


# ── 5-2: 接続語句リスト（特許ライティングマニュアル 表1 より）
# 長いもの（複数語）を先に置いて誤マッチを防ぐ
_CONNECTIVES = [
    'しかしながら', 'それどころか', 'そうすると', 'それなら', 'それでも',
    'したがって', 'ならびに', 'すなわち', 'なぜなら', '具体的には',
    'とはいえ', 'もっとも', 'もしくは', 'あるいは', 'ところで',
    'それで', 'そこで', 'ゆえに', 'よって', 'そのため', 'このため',
    'かつ', 'および', 'そして', 'さらに', 'なお', 'つまり',
    'ただし', 'または', 'しかし', 'また', 'さて', 'ちなみに',
    '例えば',
]

# 接続語句の後に読点がないパターン（文の先頭または句点直後）
# キャプチャグループ 1: 接続語句
_CONNECTIVE_PAT = re.compile(
    r'(?:(?:^|。))(' + '|'.join(re.escape(c) for c in _CONNECTIVES) + r')([^、。\n])'
)

# ── 5-3: 原因・理由・条件節の後に読点がないパターン
# 各パターン: (正規表現, 説明)
_CONDITION_PATTERNS = [
    # 〜ので（理由）: 動詞・形容詞の語尾のあとに限定して検出
    # ・「ものである」「ことのできる」等の名詞化助詞+のde を除外するため
    #   正規表現で動詞/形容詞語尾の直後にのみマッチ
    # ・「のである」「のであって」「のでなく」は TC5 冗長表現で別途検出するため除外
    (re.compile(
        r'(?<=[るうくすつたいなだよいしれせてえぬぶむ])'
        r'ので'
        r'(?!ある|あっ|なく|は)'
        r'([^、。\n])'
    ), '「〜ので」の後に読点が必要'),
    # 〜ため（理由・目的）: ために・ための・ためで でない場合
    (re.compile(r'(?<=[^\s])ため([^、。\nにのでが])'), '「〜ため」の後に読点が必要'),
    # 〜によっては（条件）
    (re.compile(r'によっては([^、。\n])'), '「〜によっては」の後に読点が必要'),
    # 〜ならば（条件）
    (re.compile(r'ならば([^、。\n])'), '「〜ならば」の後に読点が必要'),
    # 〜たら（条件）: たらの後
    (re.compile(r'(?<=[^\s])たら([^、。\nに])'), '「〜たら」の後に読点が必要'),
    # 〜れば（条件）
    (re.compile(r'(?<=[^\s])れば([^、。\n])'), '「〜れば」の後に読点が必要'),
    # 〜場合は / 〜場合には（条件）
    (re.compile(r'場合(?:に)?は([^、。\n])'), '「〜場合は」の後に読点が必要'),
]

_PARA_ID_PAT = re.compile(r'【(\d{4,5})】')
_HEADING_PAT = re.compile(r'^【[^】\d][^】]*】\s*$')
_PARA_NUM_PAT = re.compile(r'【\d{4,5}】')


def check_punctuation(sections):
    """TC7: 読点欠落チェック（5-2 接続語句 / 5-3 条件節）。

    sections: split_sections() の戻り値
    戻り値: issue dict のリスト
    """
    issues = []
    seen = set()

    text = sections.get("description", "")
    if not text:
        return issues

    current_para = None
    for line in text.splitlines():
        stripped = line.strip()
        m = _PARA_ID_PAT.match(stripped)
        if m:
            current_para = 'p-' + m.group(1)

        if _HEADING_PAT.match(stripped):
            continue

        body = _PARA_NUM_PAT.sub('', stripped).strip()
        if len(body) < 6:
            continue

        # 5-2: 接続語句の後に読点なし
        for match in _CONNECTIVE_PAT.finditer(body):
            conn = match.group(1)
            snippet = body[max(0, match.start() - 5):match.end() + 20].strip()
            key = ('TC7a', current_para, conn, snippet[:15])
            if key in seen:
                continue
            seen.add(key)
            issue = {
                "milestone": "TC7",
                "level": "info",
                "msg": f"接続語句「{conn}」の後に読点がありません（5-2）",
                "detail": snippet,
            }
            if current_para:
                issue["para_id"] = current_para
            issues.append(issue)

        # 5-3: 条件・理由節の後に読点なし
        for pat, note in _CONDITION_PATTERNS:
            for match in pat.finditer(body):
                # マッチした語句（節末尾）を含む前後の文脈
                end_word = body[match.start():match.end() - 1]  # 後続文字を除く
                snippet = body[max(0, match.start() - 15):match.end() + 15].strip()
                key = ('TC7b', current_para, end_word, snippet[:15])
                if key in seen:
                    continue
                seen.add(key)
                issue = {
                    "milestone": "TC7",
                    "level": "info",
                    "msg": f"条件・理由節の後に読点がありません：「{end_word}」— {note}",
                    "detail": snippet,
                }
                if current_para:
                    issue["para_id"] = current_para
                issues.append(issue)

    return issues
