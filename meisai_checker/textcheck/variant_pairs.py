# -*- coding: utf-8 -*-
"""TC11: 表記ゆれ（同一文書内の混在）チェック。

variant_pairs.json のペア表に従い、同一文書に同じ語の別表記が2種類以上
現れたら警告する。正誤は原則決めない。推奨表記が表にあるペアは、推奨表記へ
の統一を促す。推奨がないペアは文書内で件数の少ない側を指摘する。

ユーザー上書き: ~/.meisai-checker/variant_pairs.json（id 単位でマージ。
同じ id は項目ごと上書き、新しい id は追加、"enabled": false で無効化）。

severity: strong（既定）は warning、soft は「使い分けの可能性があるが念のため」の info。

スコープ: 明細書本文・請求項・要約（見出し行は除く）
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache

_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), 'variant_pairs.json')
_USER_PATH = os.path.join(os.path.expanduser('~'), '.meisai-checker',
                          'variant_pairs.json')

_HEADING_PAT = re.compile(r'^【[^】]+】\s*$')
_PARA_NUM_PAT = re.compile(r'^【\d{4,5}】')
_PARA_ID_PAT = re.compile(r'^【(\d{4,5})】')
_CLAIM_NUM_PAT = re.compile(r'^【請求項(\d+)】')

_MAX_ISSUES_PER_VARIANT = 10


def _read_json(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def load_pairs(user_path=_USER_PATH):
    """既定の表にユーザー上書きをマージして有効なペアを返す。"""
    base = _read_json(_DEFAULT_PATH) or {}
    pairs = {p['id']: dict(p) for p in base.get('pairs', [])}
    user = _read_json(user_path) if user_path else None
    if isinstance(user, dict):
        for up in user.get('pairs', []):
            pid = up.get('id')
            if not pid:
                continue
            if pid in pairs:
                pairs[pid].update(up)
            else:
                pairs[pid] = dict(up)
    out = []
    for p in pairs.values():
        if not p.get('enabled', True):
            continue
        if p.get('kind') == 'deprecated':
            if p.get('patterns'):
                out.append(p)
        elif len(p.get('variants', [])) >= 2:
            out.append(p)
    return out


@lru_cache(maxsize=None)
def _compile(pattern):
    return re.compile(pattern, re.M)


def _variant_regex(v):
    return _compile(v.get('regex') or re.escape(v['text']))


def _mask_excluded(body, excludes):
    for w in excludes:
        if w in body:
            body = body.replace(w, '\0' * len(w))
    return body


def _is_suffix_nado(body, pos):
    """「等」が接尾辞用法か（同等・均等・等しい等は除く）。"""
    try:
        from ..tokenizer import _tokenize
    except ImportError:
        return True
    try:
        for t in _tokenize(body):
            if t['start'] <= pos < t['end']:
                return t['surf'] == '等' and t['pos'] == '接尾辞'
    except Exception:
        return True
    return True


def _iter_body_lines(sections):
    """(section_name, anchor_kind, anchor, body) を順に返す。"""
    targets = [
        ('明細書', sections.get('description', '')),
        ('請求項', sections.get('claims', '')),
        ('要約', sections.get('abstract', '')),
    ]
    for name, text in targets:
        if not text:
            continue
        para = None
        claim = None
        for line in text.splitlines():
            s = line.strip()
            pm = _PARA_ID_PAT.match(s)
            if pm:
                para = 'p-' + pm.group(1)
            cm = _CLAIM_NUM_PAT.match(s)
            if cm:
                claim = int(cm.group(1))
            if _HEADING_PAT.match(s):
                continue
            body = _PARA_NUM_PAT.sub('', s).strip()
            if body:
                yield name, claim, para, body


def check_variant_pairs(sections, pairs=None, long_vowel=None):
    """TC11: 表記ゆれ（同一文書内の混在）チェック。

    sections: split_sections() の戻り値
    戻り値: issue dict のリスト
    """
    if long_vowel is None:
        # ペア表を明示しない通常呼び出しのときだけ長音チェックを行う
        long_vowel = pairs is None and _long_vowel_enabled()
    if pairs is None:
        pairs = load_pairs()
    if not pairs:
        return check_long_vowel(sections) if long_vowel else []

    mix_pairs = [p for p in pairs if p.get('kind') != 'deprecated']
    dep_pairs = [p for p in pairs if p.get('kind') == 'deprecated']

    # 出現位置を収集: hits[pair_id][variant_text] = [(section, claim, para, body, start, end)]
    hits = {p['id']: {v['text']: [] for v in p['variants']} for p in mix_pairs}
    dep_hits = []  # (pair, pattern, name, claim, para, body, start, end)
    for name, claim, para, body in _iter_body_lines(sections):
        for p in dep_pairs:
            masked = _mask_excluded(body, p.get('exclude', []))
            for pat in p['patterns']:
                for m in _variant_regex(pat).finditer(masked):
                    dep_hits.append((p, pat, name, claim, para, body,
                                     m.start(), m.end()))
        for p in mix_pairs:
            masked = _mask_excluded(body, p.get('exclude', []))
            for v in p['variants']:
                for m in _variant_regex(v).finditer(masked):
                    if p.get('pos_guard') and v['text'] == '等' \
                            and not _is_suffix_nado(body, m.start()):
                        continue
                    hits[p['id']][v['text']].append(
                        (name, claim, para, body, m.start(), m.end()))

    issues = []
    for p in mix_pairs:
        by_variant = hits[p['id']]
        present = [v['text'] for v in p['variants'] if by_variant[v['text']]]
        if len(present) < 2:
            continue
        counts = {t: len(by_variant[t]) for t in present}
        summary = '／'.join(f'{t}（{counts[t]}件）' for t in present)

        recommend = p.get('recommend')
        if recommend and recommend in present:
            keep = recommend
            hint = f'「{keep}」に統一することを推奨します'
        else:
            # 多数派に寄せる。同数なら表の並びで先のものを残す
            keep = max(present, key=lambda t: (counts[t], -present.index(t)))
            if recommend:
                hint = f'「{recommend}」への統一を推奨します'
            else:
                hint = f'件数の多い「{keep}」に寄せるなど、どちらかに統一してください'

        for t in present:
            if t == keep:
                continue
            seen = set()
            n = 0
            for name, claim, para, body, s, e in by_variant[t]:
                anchor = claim if claim else para
                key = (name, anchor)
                if key in seen:
                    continue
                seen.add(key)
                if n >= _MAX_ISSUES_PER_VARIANT:
                    break
                n += 1
                soft = p.get('severity') == 'soft'
                if soft:
                    msg = (f'表記ゆれの可能性（{p["label"]}）：{summary}。'
                           f'使い分けであれば問題ありません')
                else:
                    msg = f'表記ゆれ（{p["label"]}）：{summary}。{hint}'
                issue = {
                    'milestone': 'TC11',
                    'level': 'info' if soft else 'warning',
                    'msg': msg,
                    'detail': f'「{t}」（{name}）：…{body[max(0, s - 10):e + 10]}…',
                }
                if claim:
                    issue['claim'] = claim
                elif para:
                    issue['para_id'] = para
                issues.append(issue)

    # 旧表記・仮名書きの原則（単独指摘）。同一箇所・同一表記は1件にまとめる
    seen = set()
    for p, pat, name, claim, para, body, s_, e_ in dep_hits:
        anchor = claim if claim else para
        key = (p['id'], pat['text'], name, anchor)
        if key in seen:
            continue
        seen.add(key)
        issue = {
            'milestone': 'TC11', 'level': 'info',
            'msg': f'表記（{p["label"]}）：「{pat["text"]}」は「{pat["to"]}」と書くのが公用文の原則です',
            'detail': f'{p.get("source", "")}：…{body[max(0, s_ - 10):e_ + 10]}…',
        }
        if claim:
            issue['claim'] = claim
        elif para:
            issue['para_id'] = para
        issues.append(issue)
    if long_vowel:
        issues += check_long_vowel(sections)
    return issues


# ── 長音の揺れ（ユーザー／ユーザ、サーバー／サーバ 等） ──────────────
#
# ペア表では扱えないので、カタカナ名詞の語末の長音の有無を同一文書内で照合する。
# MeCab が複合語を分割する（ユーザーインタフェース→ユーザー＋インタフェース）ので、
# トークン単位の語末だけを見れば足りる。語中の長音（ビル／ビール）は別語なので見ない。
# 官（公用文作成の考え方 Ⅰ-1(3)エ：長音符号を使う）と技術文書の慣行（省略）が割れているため、
# 推奨は付けず、件数の多い側に寄せる。

_KATAKANA_TOKEN = re.compile(r'^[ァ-ヴ][ァ-ヴー]*$')
_LONG_MIN_BASE = 3   # 語末の長音を除いた長さの下限（「ケー／ケ」等を除く）


def _long_vowel_enabled():
    user = _read_json(_USER_PATH)
    return not (isinstance(user, dict) and user.get('long_vowel') is False)


def check_long_vowel(sections):
    """TC11b: カタカナ語の語末の長音の揺れ（同一文書内の混在）を検出する。"""
    try:
        from ..tokenizer import _tokenize
    except ImportError:
        return []

    # hits[base][True=長音あり / False=なし] = [(name, claim, para, body, start, end)]
    hits = {}
    for name, claim, para, body in _iter_body_lines(sections):
        try:
            tokens = _tokenize(body)
        except Exception:
            return []
        for t in tokens:
            surf = t['surf']
            if t['pos'] != '名詞' or not _KATAKANA_TOKEN.match(surf):
                continue
            has_long = surf.endswith('ー')
            base = surf[:-1] if has_long else surf
            if len(base) < _LONG_MIN_BASE or base.endswith('ー'):
                continue
            hits.setdefault(base, {}).setdefault(has_long, []).append(
                (name, claim, para, body, t['start'], t['end']))

    issues = []
    for base, by in hits.items():
        if len(by) < 2:
            continue
        forms = {True: base + 'ー', False: base}
        counts = {k: len(v) for k, v in by.items()}
        # 件数の多い側を残す。同数なら長音ありを残す（建議の原則）
        keep = max(counts, key=lambda k: (counts[k], k))
        summary = '／'.join(f'{forms[k]}（{counts[k]}件）' for k in (True, False))
        hint = f'件数の多い「{forms[keep]}」に寄せるなど、どちらかに統一してください'
        seen = set()
        n = 0
        for k, occ in by.items():
            if k == keep:
                continue
            for name, claim, para, body, s_, e_ in occ:
                anchor = claim if claim else para
                key = (name, anchor)
                if key in seen:
                    continue
                seen.add(key)
                if n >= _MAX_ISSUES_PER_VARIANT:
                    break
                n += 1
                issue = {
                    'milestone': 'TC11', 'level': 'warning',
                    'msg': f'表記ゆれ（長音：{forms[True]}／{forms[False]}）：{summary}。{hint}',
                    'detail': f'「{forms[k]}」（{name}）：…{body[max(0, s_ - 10):e_ + 10]}…',
                }
                if claim:
                    issue['claim'] = claim
                elif para:
                    issue['para_id'] = para
                issues.append(issue)
    return issues
