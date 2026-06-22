#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[선택] Claude API로 다음 호를 자동 리서치·작성한다.

웹검색(server tool)으로 이번 주 한국 IT기업 HR·노무·법령 이슈를 조사한 뒤,
구조화 출력(structured outputs)으로 사이트가 요구하는 호 JSON을 생성한다.

요구사항:
    pip install anthropic
    환경변수 ANTHROPIC_API_KEY 설정 (없으면 new_issue.py 로 대체 권장)

사용법:
    python scripts/generate_issue.py
    python scripts/generate_issue.py --date 2026-06-29

참고: 본 스크립트는 외부 API와 웹검색에 의존하므로, 실행 후 생성된
data/issues/<slug>.json 의 사실관계·출처를 사람이 검수한 뒤 배포하는 것을 권장한다.
"""
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parent.parent
ISSUES = ROOT / "data" / "issues"
MODEL = "claude-opus-4-8"

# ----------------------------------------------------------------- 호 메타 계산
def next_meta(pub_date):
    issues = []
    if ISSUES.exists():
        for p in ISSUES.glob("*.json"):
            try:
                issues.append(json.loads(p.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                pass
    next_no = max((i.get("issueNumber", 0) for i in issues), default=0) + 1
    iso = pub_date.isocalendar()
    slug = f"{iso[0]}-w{iso[1]:02d}"
    week_of_month = (pub_date.day - 1) // 7 + 1
    week_label = f"{pub_date.year}년 {pub_date.month}월 {week_of_month}주차"
    return next_no, slug, week_label

# ----------------------------------------------------------------- 구조화 출력 스키마
ISSUE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "headline": {"type": "string"},
        "intro": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "emoji": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "headline": {"type": "string"},
                                "category": {"type": "string"},
                                "effectiveDate": {"type": "string"},
                                "summary": {"type": "string"},
                                "whatChanged": {"type": "string"},
                                "itImpact": {"type": "string"},
                                "sources": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "name": {"type": "string"},
                                            "url": {"type": "string"},
                                        },
                                        "required": ["name", "url"],
                                    },
                                },
                            },
                            "required": ["headline", "category", "effectiveDate", "summary", "whatChanged", "itImpact", "sources"],
                        },
                    },
                },
                "required": ["title", "emoji", "items"],
            },
        },
        "lawWatch": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "law": {"type": "string"},
                    "status": {"type": "string"},
                    "effectiveDate": {"type": "string"},
                    "note": {"type": "string"},
                    "url": {"type": "string"},
                },
                "required": ["law", "status", "effectiveDate", "note", "url"],
            },
        },
        "quickStats": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "value": {"type": "string"},
                    "label": {"type": "string"},
                    "url": {"type": "string"},
                },
                "required": ["value", "label", "url"],
            },
        },
        "actionItems": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["headline", "intro", "sections", "lawWatch", "quickStats", "actionItems"],
}

RESEARCH_PROMPT = """오늘은 {today}이다 (이번 주: {week_label}). 당신은 IT기업 대상 주간 HR·노무 뉴스레터의 리서처다.
web_search 도구를 적극 사용해, 최근 1~2주 한국의 IT/테크 기업과 관련된 HR·노무 이슈와 법령 개정/시행/판례를 조사하라.

다룰 주제(해당되는 것 위주로):
- 근로기준법·최저임금·임금(포괄임금, 통상임금, 임금체불) 관련 개정·지침·판례
- 일·가정 양립(육아휴직, 배우자 출산휴가 등) 제도 변화
- 노사관계(노조법 등), 플랫폼·특수고용 근로자성 판례
- IT업계 근무제(주4일/4.5일제, 유연·재택근무), 개발자 보상·스톡옵션
- 산업안전·중대재해, 직장 내 괴롭힘, 직장 내 AI·개인정보

요구사항:
- 고용노동부·법제처·국회·주요 언론·대형 법무법인 등 신뢰 출처를 우선하고, 각 사안의 실제 URL과 날짜를 확보하라.
- 확정된 수치·시행일을 우선하고, 불확실한 내용은 그렇다고 명시하라.
- 6~10개 사안을 도출하고, 각 사안마다 (1)무슨 일인가 (2)무엇이 바뀌었나 (3)IT 인사 담당자 시사점 (4)출처(이름+URL)를 정리해 한국어로 작성하라.
검색을 충분히 수행한 뒤 정리된 조사 결과를 출력하라."""

WRITE_PROMPT = """다음은 이번 주({week_label}) 조사 결과다. 이것을 바탕으로 IT기업 HR 뉴스레터 한 호의 콘텐츠를 한국어로 작성하라.
- 3~5개의 주제 섹션(각 섹션에 emoji 1개)으로 묶고, 각 항목은 headline/category/effectiveDate/summary/whatChanged/itImpact/sources 구조.
- itImpact는 'IT 인사 담당자가 무엇을 해야 하는가' 관점.
- lawWatch(법령 상태 추적), quickStats(인상적 수치), actionItems(실무 체크리스트 4~6개)도 채워라.
- 모든 sources/url은 조사 결과의 실제 URL만 사용하고, 사실을 지어내지 말 것.

조사 결과:
{research}"""


def run():
    try:
        import anthropic
    except ImportError:
        sys.exit("anthropic 패키지가 필요합니다: pip install anthropic")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("환경변수 ANTHROPIC_API_KEY가 필요합니다. (대안: python scripts/new_issue.py)")

    date_str = None
    if "--date" in sys.argv:
        date_str = sys.argv[sys.argv.index("--date") + 1]
    pub_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now()
    today = pub_date.strftime("%Y-%m-%d")
    issue_no, slug, week_label = next_meta(pub_date)

    out_path = ISSUES / f"{slug}.json"
    if out_path.exists():
        print(f"이미 존재함: {out_path} (덮어쓰지 않음)")
        return

    client = anthropic.Anthropic()

    # --- 1단계: 웹검색 리서치 (서버 사이드 web_search; pause_turn 루프 처리) ---
    print("① 웹검색 리서치 중…")
    messages = [{"role": "user", "content": RESEARCH_PROMPT.format(today=today, week_label=week_label)}]
    tools = [{"type": "web_search_20260209", "name": "web_search"}]
    for _ in range(6):  # pause_turn 안전 한도
        resp = client.messages.create(
            model=MODEL,
            max_tokens=12000,
            thinking={"type": "adaptive"},
            tools=tools,
            messages=messages,
        )
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        break
    research = "".join(b.text for b in resp.content if b.type == "text").strip()
    if not research:
        sys.exit("리서치 결과가 비어 있습니다. 잠시 후 다시 시도하세요.")

    # --- 2단계: 구조화 출력으로 호 JSON 생성 ---
    print("② 뉴스레터 호 작성 중…")
    with client.messages.stream(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"format": {"type": "json_schema", "schema": ISSUE_SCHEMA}},
        messages=[{"role": "user", "content": WRITE_PROMPT.format(week_label=week_label, research=research)}],
    ) as stream:
        final = stream.get_final_message()
    payload_text = next(b.text for b in final.content if b.type == "text")
    issue = json.loads(payload_text)

    # --- 메타 병합 & 저장 ---
    issue.update({
        "issueNumber": issue_no,
        "slug": slug,
        "weekLabel": week_label,
        "date": today,
        "sourceNote": "본 호는 Claude API가 공개 웹자료를 수집·요약해 자동 생성했습니다. 배포 전 사실관계·출처 검수를 권장합니다.",
    })
    ISSUES.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(issue, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ 생성 완료: {out_path}")
    print(f"   제{issue_no}호 · {week_label} · {today}")


if __name__ == "__main__":
    run()
