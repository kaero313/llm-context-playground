# LLM Context Playground

LLM API를 사용할 때 대화 맥락(context)을 어떻게 구성하고 유지할지 실험하는 학습용 playground입니다. 환불 문의, 내부 정책 충돌, 개인정보 memory, 긴 세션 같은 예제를 통해 프롬프트에 어떤 정보가 들어가고 빠지는지, 답변 품질과 token 비용이 어떻게 달라지는지 확인할 수 있습니다.

## 목표

- 어떤 프롬프트가 실제 API 입력으로 전달되는지 확인합니다.
- 최근 대화 유지, 요약 압축, 구조화 상태, RAG, KV cache 전략을 비교합니다.
- 답변에 유지되어야 할 근거와 노출되면 안 되는 정보를 함께 점검합니다.
- Mock mode로 비용 없이 구조를 학습하고, 필요할 때 Live API mode로 실제 모델 응답을 검증합니다.
- 블로그에 정리하기 좋도록 실험 요약과 캡처용 화면을 제공합니다.

## 실행

```powershell
python -m context_lab.server
```

서버가 정상 실행되면 터미널에 다음 형식의 메시지가 출력됩니다.

```text
LLM Context Playground UI running at http://127.0.0.1:8765
```

브라우저에서 [http://127.0.0.1:8765](http://127.0.0.1:8765) 로 접속합니다.

## 웹 실험 흐름

1. **프롬프트 입력**: 학습 케이스를 고르고 사용자 질문을 수정합니다.
2. **맥락 전략 설정**: 최근 대화 유지 개수, 압축 전략, RAG, KV cache, token 예산을 조정합니다.
3. **최종 API 입력 프롬프트 확인**: 모델에 전달될 context bundle을 확인합니다.
4. **모델 답변 확인**: Mock mode 또는 Live API mode의 답변과 지표를 확인합니다.
5. **답변 분석**: 필수 근거 유지 여부와 민감 정보 노출 여부를 점검합니다.
6. **결과 비교 및 캡처 노트**: 전략별 차이와 블로그용 정리 포인트를 확인합니다.

## Mock mode와 Live API mode

기본 실행은 `Mock mode`입니다. 실제 API 비용 없이 deterministic mock provider로 context 구성과 평가 흐름을 학습할 수 있습니다.

Live API mode를 사용하려면 서버를 시작하기 전에 환경변수를 설정합니다.

```powershell
pip install -e ".[openai]"
$env:OPENAI_API_KEY="..."
$env:OPENAI_MODEL="gpt-4.1-mini"
python -m context_lab.server
```

웹 UI에서 `Live API`를 선택하면 실제 OpenAI API를 호출합니다. 기본 범위는 **현재 설정만 호출**입니다. `비교 후보 전체 호출`을 선택하면 현재 화면 기준 여러 후보를 모두 실제 API로 호출하므로 비용이 더 발생합니다.

CLI에서도 직접 실행할 수 있습니다.

```powershell
python -m context_lab run --case support_refund --strategy hybrid --mode mock --show-context
python -m context_lab run --case support_refund --strategy hybrid --mode openai --show-context
```

## CLI 예시

여러 전략 비교:

```powershell
python -m context_lab compare --case support_refund --strategies full_history sliding_window summary structured rag hybrid --mode mock
```

token 예산 제한 실험:

```powershell
python -m context_lab run --case long_running_session --strategy full_history --mode mock --max-input-tokens 120 --reserved-output-tokens 20 --show-context
```

## 전략

- `full_history`: 전체 대화를 그대로 보냅니다.
- `sliding_window`: 최근 대화만 유지합니다.
- `summary`: 오래된 대화를 running summary로 압축합니다.
- `structured`: 사용자 프로필과 안전한 memory를 구조화합니다.
- `rag`: 검색된 문서 근거를 추가합니다.
- `hybrid`: 요약, 구조화 상태, 검색 근거, 최근 대화를 함께 사용합니다.
- `privacy`: 개인정보를 redaction하고 안전한 memory만 유지합니다.
- `tool_compaction`: raw tool result를 요약해 필요한 근거만 남깁니다.

## 학습 케이스

- `support_refund`: 환불 문의에서 invoice, 구매일, 정책 근거가 유지되는지 확인합니다.
- `internal_policy`: 오래된 정책과 최신 정책이 충돌할 때 어떤 근거를 우선해야 하는지 확인합니다.
- `tool_result_compaction`: raw IP 같은 민감 tool output을 줄이고 요약만 유지합니다.
- `privacy_memory`: 개인정보를 장기 memory에 저장하지 않는 흐름을 확인합니다.
- `long_running_session`: 긴 세션에서 summary와 budget trimming이 필요한 이유를 확인합니다.
- `openai_state`: manual state, stored conversation, compaction의 차이를 확인합니다.

## 테스트

```powershell
python -m pytest
```

현재 테스트는 전략별 context 구성, RAG 검색, privacy redaction, mock 평가, web API payload를 검증합니다.

## 구조

```text
context_lab/
  cases.py          # 한국어 학습 시나리오
  models.py         # context, message, memory, document 모델
  strategies.py     # context 구성 전략
  retrieval.py      # 간단한 키워드 기반 retriever
  providers.py      # mock provider와 선택적 OpenAI provider
  evaluation.py     # 답변 품질 평가
  server.py         # 로컬 web API 서버
  web/              # Korean playground UI
tests/
```
