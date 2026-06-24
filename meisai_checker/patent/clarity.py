# -*- coding: utf-8 -*-
"""M7b: 明確性要件違反の追加パターン（特許法36条6項2号・審査基準第II部第2章第3節）

(5) 範囲を曖昧にし得る表現（「約」「適宜」「好ましくは」等）
(2e) 非技術的事項の記載（販売地域・販売元・価格等）
"""
from __future__ import annotations

import re
from typing import Any

from ..parser import KIND_INDEPENDENT


# ══════════════════════════════════════════════════════════
# (5) 範囲を曖昧にし得る表現
# ══════════════════════════════════════════════════════════

# (キーワード, カテゴリラベル, 補足メッセージ)
_VAGUE_KEYWORDS: list[tuple[str, str, str]] = [
    # 裁量的表現
    ('適宜',         '裁量的表現', '条件または基準値を明示してください。'),
    ('必要に応じて', '裁量的表現', '条件を具体的に記載してください。'),
    ('場合によっては', '裁量的表現', '条件を具体的に記載してください。'),
    # 好適表現
    ('好ましくは',   '好適表現', '必須要件として記載するか、従属項に移してください。'),
    ('望ましくは',   '好適表現', '必須要件として記載するか、従属項に移してください。'),
    ('なるべく',     '好適表現', '発明の範囲が不確定になります。'),
    ('できるだけ',   '好適表現', '発明の範囲が不確定になります。'),
]

# 数値近似表現（「約10mm」「50℃程度」等）
_NUMERIC_APPROX_PAT = re.compile(
    r'(?:約|おおむね|ほぼ|略)\s*\d'           # 「約10」「おおむね50」
    r'|\d[\d.]*\s*'
    r'(?:mm|cm|m|nm|μm|kg|g|℃|°C|Hz|MHz|GHz|kHz|%|MPa|Pa|W|V|mA|A|N)?'
    r'\s*(?:程度|ほど|前後|くらい)',
    re.UNICODE,
)

_VAGUE_CITE = '（特許法36条6項2号・審査基準第II部第2章第3節(5)）'


def check_vague_range(
    claims: dict[int, str],
    kinds: dict[int, str],
) -> list[dict[str, Any]]:
    """(5) 発明の範囲を曖昧にし得る表現を請求項から検出する。

    独立項: warning（発明特定事項として直接問題）
    従属項: info（独立項ほど厳格ではないが記録）
    """
    issues: list[dict] = []

    for num in sorted(claims.keys()):
        body = claims[num]
        is_independent = kinds.get(num) == KIND_INDEPENDENT
        level = 'warning' if is_independent else 'info'

        for keyword, label, hint in _VAGUE_KEYWORDS:
            if keyword in body:
                issues.append({
                    'claim': num,
                    'level': level,
                    'check': 'clarity_vague_range',
                    'msg': (
                        f'請求項{num}：{label}「{keyword}」が発明特定事項に含まれています。'
                        f'{hint}'
                        f'{_VAGUE_CITE}'
                    ),
                })

        for m in _NUMERIC_APPROX_PAT.finditer(body):
            matched = m.group(0).strip()
            issues.append({
                'claim': num,
                'level': level,
                'check': 'clarity_vague_range',
                'msg': (
                    f'請求項{num}：「{matched}」は数値範囲を曖昧にします。'
                    f'具体的な数値または数値範囲（〇〇以上〇〇以下）で記載してください。'
                    f'{_VAGUE_CITE}'
                ),
            })

    return issues


# ══════════════════════════════════════════════════════════
# (2e) 非技術的事項の記載
# ══════════════════════════════════════════════════════════

# (正規表現, カテゴリラベル, 補足メッセージ)
_NONTECHNICAL_PATS: list[tuple[re.Pattern, str, str]] = [
    # 企業名・製造者名
    (
        re.compile(
            r'(?:株式会社|有限会社|合同会社|合資会社)[^\s、。]{1,20}'
            r'|[^\s、。]{2,10}社(?:製|製造|の製品)',
            re.UNICODE,
        ),
        '企業名・製造者名',
        '企業名・製造者名による限定は非技術的事項です。技術的特徴（仕様・構造・機能）で記載してください。',
    ),
    # 価格（「第１」等の序数や「円形状」「円弧」等の形状語は除外）
    (
        re.compile(r'(?<!第)\d[\d,]*\s*円(?![形弧筒柱錐環板盤周径心])', re.UNICODE),
        '価格',
        '価格による限定は非技術的事項です。',
    ),
    # 販売地域・流通地域
    (
        re.compile(
            r'(?:日本|海外|国内|アジア|欧米|北米|欧州|中国|米国|EU)'
            r'[^\s、。]{0,6}'
            r'(?:で|において|にて)(?:販売|流通|製造|輸出|輸入|市販)(?:され|する|した)',
            re.UNICODE,
        ),
        '販売地域',
        '販売地域・流通地域による限定は非技術的事項です（審査基準第II部第2章第3節(2)e）。',
    ),
    # 市販品
    (
        re.compile(r'市販(?:の|品|されている|品の)', re.UNICODE),
        '流通状態',
        '「市販の」等の流通状態による限定は非技術的事項となる可能性があります。',
    ),
]

_NONTECHNICAL_CITE = '（特許法36条6項2号）'


def check_nontechnical(claims: dict[int, str]) -> list[dict[str, Any]]:
    """(2e) 請求項中の非技術的事項（販売地域・企業名・価格等）を検出する。"""
    issues: list[dict] = []

    for num in sorted(claims.keys()):
        body = claims[num]
        for pat, label, hint in _NONTECHNICAL_PATS:
            for m in pat.finditer(body):
                matched = m.group(0)
                issues.append({
                    'claim': num,
                    'level': 'warning',
                    'check': 'clarity_nontechnical',
                    'msg': (
                        f'請求項{num}：{label}「{matched}」が含まれています。'
                        f'{hint}'
                        f'{_NONTECHNICAL_CITE}'
                    ),
                })

    return issues


# ══════════════════════════════════════════════════════════
# 相対表現・程度副詞の検出
# ══════════════════════════════════════════════════════════

_DEGREE_ADVERBS: list[str] = [
    '非常に', '極めて', '著しく', '大幅に', '格段に',
    '飛躍的に', '大いに', '甚だしく', '相当に', 'かなり',
    '十分に', '十二分に', 'はるかに', '遥かに',
]

_RELATIVE_ADJECTIVES: list[str] = [
    '高い', '低い', '速い', '早い', '遅い', '多い', '少ない',
    '大きい', '小さい', '良い', 'よい', '悪い', '強い', '弱い',
    '長い', '短い', '重い', '軽い', '広い', '狭い',
    '深い', '浅い', '厚い', '薄い', '硬い', '柔らかい',
]

_CHANGE_VERB_STEMS: list[str] = [
    '向上', '低下', '改善', '悪化', '増加', '減少',
    '拡大', '縮小', '増大', '軽減', '低減', '促進',
    '抑制', '強化', '劣化', '増強', '減衰', '効率化',
    '最適化', '簡略化', '複雑化',
]

_CHANGE_VERB_STEM_PAT = re.compile(
    r'(?:' + '|'.join(_CHANGE_VERB_STEMS) + r')'
    r'(?:し|する|され|させ|した|して|しない|すれ|させる|させた|させて|できる)',
    re.UNICODE,
)

_CHANGE_WAGO_PAT = re.compile(
    r'高ま|高め|増え|増やし|増やす|減る|減り|減らし|減らす'
    r'|(?<![きぎしじちにびみり])上がり'
    r'|(?<![きぎしじちにびみり])上がる'
    r'|(?<![きぎしじちにびみり])上げ'
    r'|(?<![きぎしじちにびみり])下がり'
    r'|(?<![きぎしじちにびみり])下がる'
    r'|(?<![きぎしじちにびみり])下げ'
    r'|伸び|縮み|縮ま|縮め|強ま|強め|弱ま|弱め'
    r'|広がる|広がっ|広げ|狭ま|狭め|深ま|深め|薄ま|薄め'  # 広がり(名詞)は除外
    r'|抑え',
    re.UNICODE,
)

_COMPARISON_BASIS_PAT = re.compile(
    r'比べ|比較|比して|より(?:も)?|に対し|を用いない|しない場合|がない場合|従来|前者|後者'
    r'|閾値|しきい値|閾|未満|以下|以上|超え'  # 数値基準による比較
    r'|特定の|所定の|予め定め|あらかじめ定め'  # 暗黙の基準値が存在する表現
    r'|無視でき',  # 「無視できる程度に」は暗黙の比較基準（機能要件に対して無視できる量）
    re.UNICODE,
)

_CORRELATION_CONNECTIVE_PAT = re.compile(
    r'ほど|につれ|に応じ|に伴い|に比例|に従って',
    re.UNICODE,
)

# 「〜てもよい」「〜でもよい」「であってよい」等の許可表現を除去（よい の誤検知防止）
_PERMISSIVE_YOKU_PAT = re.compile(
    r'(?:て|で)も?(?:よい|良い|よく)|であっ(?:ても)?(?:よい|良い)',
    re.UNICODE,
)

_RELATIVE_CITE = '（特許法36条6項2号）'

# ── 相対表現チェックの対象サブセクション ──────────────────────────────
# 技術分野・背景技術・図面の簡単な説明・符号の説明は文体チェック対象外

_DESC_HEADING_PAT = re.compile(r'^【[^】\d][^】]*】\s*$')

_TARGET_SECTION_PAT = re.compile(
    r'【(?:'
    r'発明が解決しようとする課題'
    r'|課題を解決するための手段'
    r'|発明の効果'
    r'|発明を実施するための(?:最良の)?形態'
    r'|発明の実施の形態'
    r'|実施(?:形態)?[０-９0-9]*'
    r'|実施例[０-９0-9]*'
    r')】',
    re.UNICODE,
)


def _extract_target_sections(desc: str) -> str:
    """description テキストからチェック対象サブセクションのみを抽出する。"""
    result_lines: list[str] = []
    in_target = False
    for line in desc.splitlines():
        stripped = line.strip()
        if _DESC_HEADING_PAT.match(stripped):
            in_target = bool(_TARGET_SECTION_PAT.match(stripped))
        if in_target:
            result_lines.append(line)
    return '\n'.join(result_lines)


def _has_change_verb(text: str) -> bool:
    return bool(_CHANGE_VERB_STEM_PAT.search(text) or _CHANGE_WAGO_PAT.search(text))


def _is_correlation_expr(sentence: str) -> bool:
    """連動表現（〜ほど、〜につれ等）かどうかを判定。

    「遠ざかるほど狭まる」のような空間形状記述では連動語の前方が
    空間的参照点（遠ざかる等）であり、変化動詞でなくてよい。
    連動語の後方に変化動詞があれば連動表現とみなす。
    """
    m = _CORRELATION_CONNECTIVE_PAT.search(sentence)
    if not m:
        return False
    return _has_change_verb(sentence[m.end():])


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r'[。．]', text) if s.strip()]


def _check_sentence_relative(
    sentence: str,
    context: str,
    level: str,
    cite: str = _RELATIVE_CITE,
) -> list[dict[str, Any]]:
    issues: list[dict] = []

    # ① 程度副詞（無条件）
    for adv in _DEGREE_ADVERBS:
        if adv in sentence:
            issues.append({
                'level': level,
                'check': 'clarity_relative',
                'msg': (
                    f'{context}：程度副詞「{adv}」は技術的根拠になりません。'
                    f'具体的な数値または条件で記載してください。'
                    f'{cite}'
                ),
            })

    # ② 相対形容詞（同一文に比較基準なければ警告）
    # 「〜てもよい」等の許可表現を除去してから判定
    sentence_adj = _PERMISSIVE_YOKU_PAT.sub('', sentence)
    if not _COMPARISON_BASIS_PAT.search(sentence):
        for adj in _RELATIVE_ADJECTIVES:
            if adj in sentence_adj:
                issues.append({
                    'level': level,
                    'check': 'clarity_relative',
                    'msg': (
                        f'{context}：相対形容詞「{adj}」に比較基準がありません。'
                        f'「〜と比べて」「従来〜に対して」等の基準を明示してください。'
                        f'{cite}'
                    ),
                })

    # ③ 方向性変化動詞（比較基準または連動表現がなければ警告）
    if _has_change_verb(sentence):
        if not (_COMPARISON_BASIS_PAT.search(sentence) or _is_correlation_expr(sentence)):
            m_stem = _CHANGE_VERB_STEM_PAT.search(sentence)
            m_wago = _CHANGE_WAGO_PAT.search(sentence)
            verb = (m_stem or m_wago).group(0)  # type: ignore[union-attr]
            issues.append({
                'level': level,
                'check': 'clarity_relative',
                'msg': (
                    f'{context}：変化動詞「{verb}」に比較基準がありません。'
                    f'「〜と比べて」「従来〜に対して」等の基準を明示してください。'
                    f'{cite}'
                ),
            })

    return issues


def check_relative_expression(
    claims: dict[int, str],
    kinds: dict[int, str],
    sections: dict[str, str],
) -> list[dict[str, Any]]:
    """相対表現・程度副詞・方向性変化動詞の比較基準欠如を検出する。

    請求項: warning（明確性違反）
    明細書: info（記載上の問題）
    """
    issues: list[dict] = []

    # ── 請求項
    for num in sorted(claims.keys()):
        for sent in _split_sentences(claims[num]):
            for issue in _check_sentence_relative(sent, f'請求項{num}', 'warning'):
                issue['claim'] = num
                issues.append(issue)

    # ── 明細書（対象サブセクションのみ：課題・手段・効果・実施形態・実施例）
    # 明細書本文は法令根拠なし（36条6項2号は請求項の明確性規定）
    desc = _extract_target_sections(sections.get('description', ''))
    if desc:
        for m in re.finditer(r'【(\d{4})】(.*?)(?=【\d{4}】|\Z)', desc, re.DOTALL):
            para_id = m.group(1)
            for sent in _split_sentences(m.group(2)):
                issues += _check_sentence_relative(sent, f'【{para_id}】', 'info', cite='')

    return issues
