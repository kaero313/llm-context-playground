# LLM Context Playground

LLM API를 사용할 때 대화 맥락(context)을 어떻게 구성하고 유지할지 실험하는 학습용 playground입니다. 환불 문의, 내부 정책 충돌, 개인정보 memory, 긴 세션 같은 예제를 통해 프롬프트에 어떤 정보가 들어가고 빠지는지, 그 결과 답변 품질과 token 비용이 어떻게 달라지는지 확인할 수 있습니다.

## 목표

- 어떤 프롬프트가 실제 API 입력으로 전달되는지 확인합니다.
- 최근 대화 유지 개수, 요약 압축, 구조화 memory, RAG, KV 캐시 후보가 결과에 미치는 영향을 비교합니다.
- 답변에 반드시 유지되어야 할 근거와 노출되면 안 되는 정보를 함께 점검합니다.
- 블로그에 정리하기 좋게 실험 결과와 캡처용 화면을 제공합니다.

## 실행 방법

Python 3.11 이상이 필요합니다.

```powershell
pip install -e ".[dev]"
python -m context_lab.server
```

브라우저에서 다음 주소를 엽니다.

```text
http://127.0.0.1:8765
```

기본 실행은 `mock` mode입니다. 실제 LLM API 비용 없이 deterministic mock provider로 context 구성과 평가 흐름을 학습할 수 있습니다.

## UI 학습 흐름

1. **프롬프트 입력**: 학습 케이스를 고르고 사용자 질문을 수정합니다.
2. **맥락 전략 설정**: 최근 대화 유지 개수, 압축 전략, RAG, KV 캐시 방식을 바꿉니다.
3. **최종 API 입력 프롬프트 확인**: 모델에 실제로 전달될 context bundle을 확인합니다.
4. **모델 답변 확인**: mock 답변과 token, cache, latency 지표를 봅니다.
5. **답변 분석**: 유지해야 할 근거가 남았는지, 민감 정보가 차단됐는지 확인합니다.
6. **결과 비교와 캡처 노트**: 여러 전략을 비교하고 블로그 정리용 요약을 확인합니다.

## CLI 사용 예시

케이스와 전략 목록을 확인합니다.

```powershell
python -m context_lab list-cases
python -m context_lab list-strategies
```

같은 케이스를 여러 전략으로 비교합니다.

```powershell
python -m context_lab compare --case support_refund --strategies full_history sliding_window summary structured rag hybrid --mode mock
```

특정 전략의 context를 직접 확인합니다.

```powershell
python -m context_lab run --case support_refund --strategy sliding_window --mode mock --show-context
python -m context_lab run --case support_refund --strategy hybrid --mode mock --show-context
```

작은 token budget에서 어떤 section이 빠지는지 확인합니다.

```powershell
python -m context_lab run --case long_running_session --strategy full_history --mode mock --max-input-tokens 120 --reserved-output-tokens 20 --show-context
```

## 포함된 전략

- `full_history`: 전체 대화를 모두 넣는 기준선입니다.
- `sliding_window`: 최근 N개 메시지만 유지합니다.
- `summary`: 오래된 대화를 running summary로 압축합니다.
- `structured`: 사용자 프로필과 안전한 memory를 구조화해 넣습니다.
- `rag`: 현재 질문과 관련된 문서와 memory를 검색해 넣습니다.
- `hybrid`: 정책, 프로필, 요약, RAG, 도구 결과 요약, 최근 대화를 함께 사용합니다.
- `tool_compaction`: 긴 도구 실행 결과를 원문 대신 요약과 citation으로 압축합니다.
- `privacy`: 이메일, 전화번호, 카드번호, 주민등록번호 같은 PII를 redaction합니다.
- `openai_state`: manual state, stored conversation, context window, compaction 개념을 비교합니다.

## 포함된 학습 케이스

- `support_refund`: 환불 문의에서 구매일, invoice id, Enterprise 전환 이유가 유지되는지 확인합니다.
- `internal_policy`: 오래된 대화보다 최신 정책 문서가 우선되는지 확인합니다.
- `tool_result_compaction`: 긴 audit log를 raw data 대신 안전한 요약으로 다루는 방법을 확인합니다.
- `privacy_memory`: 민감 정보는 저장하지 않고 언어/문체 선호만 유지하는 방법을 확인합니다.
- `long_running_session`: 긴 세션에서 summary와 budget trimming이 필요한 이유를 확인합니다.
- `openai_state`: OpenAI conversation state 관련 선택지를 개념적으로 비교합니다.

## 프로젝트 구조

```text
context_lab/
  cases.py          # 한국어 학습 fixture
  cli.py            # CLI entrypoint
  evaluation.py     # 평가와 비교 로직
  models.py         # context bundle, session, memory 모델
  privacy.py        # PII 탐지와 redaction
  providers.py      # mock provider와 선택적 OpenAI provider
  retrieval.py      # dependency 없는 lexical retriever
  server.py         # 로컬 web API 서버
  strategies.py     # context 전략 구현
  tokenization.py   # 간단한 token estimator
  web/              # 브라우저 UI
tests/              # regression tests
```

## 테스트

```powershell
python -m pytest
```

현재 테스트는 전략별 context 구성, RAG 검색, privacy redaction, mock 평가, web API payload를 검증합니다.

## OpenAI live mode

실제 OpenAI API 호출은 선택 사항입니다.

```powershell
pip install -e ".[openai]"
$env:OPENAI_API_KEY="..."
python -m context_lab run --case support_refund --strategy hybrid --mode openai
```

운영 환경에서 live mode를 사용할 때는 최신 OpenAI 공식 문서 기준으로 모델, context window, stored conversation, compaction 정책을 다시 확인하는 것을 권장합니다.
