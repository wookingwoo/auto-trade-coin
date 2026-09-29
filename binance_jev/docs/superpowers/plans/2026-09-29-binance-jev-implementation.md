# Binance JEV 자동매매 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** JEV가 5분마다 Binance USDT 선물의 롱·숏을 판단하고, 거래소 보호 주문과 영속 손실 한도를 갖춘 단일 서버용 거래 실행기를 만든다.

**Architecture:** 거래소·모델 응답은 얇은 어댑터에서 정규화하고, 결정·수량·주문 상태는 독립적인 순수 코드와 영속 장부에서 처리한다. 단일 실행기가 시작 시 거래소와 장부를 대조하고, 새 진입보다 기존 포지션 보호를 우선한다. 실행 환경은 모의·테스트넷·라이브를 분리한다.

**Tech Stack:** Python 3.11+, TypeSafe SDK 0.7.1, httpx, SQLite, unittest/pytest, Docker.

**Spec:** `docs/superpowers/specs/2026-09-29-binance-jev-design.md`

**구현 현황 (2026-09-29):** 위 다섯 작업의 런타임 코드를 작성하고 단위·통합 테스트 51개를 통과시켰다. 아래 체크박스는 최초 계획 단계의 순서를 보존한다. 실호출, 테스트넷 체결, Docker 이미지 빌드, 24시간 모의운용과 백테스트는 아직 수행하지 않았다. 지표의 독립 손계산 fixture와 전체 수수료·펀딩 대조도 후속 검증 항목이다.

## Global Constraints

- 확정: 운용자금 약 100만 원, Binance 실거래 목표, JEV 판단, 롱·숏, 5분 주기, 수십 분~몇 시간 보유, 24시간 서버.
- 제안값: BTCUSDT·ETHUSDT, One-way/Single-Asset/격리 2배, 동시 포지션 1개, 거래당 0.5%, 일일 2%, 누적 10%, 최대 보유 4시간.
- 기존 서버 여부·OS·사양과 알림 수신 경로는 미정. 서버 구매·계좌 조작·실주문은 별도의 배포 작업이다.
- 현재 checkout은 `feature/binance-jev`이며 기획서가 아직 미추적 상태다. 해당 브랜치의 `binance_jev` 안에서 구현한다.
- 구현 장부는 단일 서버의 트랜잭션과 복구를 단순화하기 위해 SQLite를 사용한다. 기획서의 MongoDB 제안은 배포 전에 문서와 일치시키도록 수정한다.

## Review Focus

- 거래소 주문 타임아웃/503의 실행 여부 불명: 같은 슬롯에 새 주문을 보내지 않고 주문 ID로 재조회한다.
- 부분 체결 뒤 보호 등록 실패: 실제 포지션 수량을 다시 읽고 비상 청산한다.
- 프로세스 재시작/날짜 변경: 최초 자본과 손실 중단 상태가 초기화되지 않는다.
- 부정확한 봉/시세/계좌: 종료되지 않은 봉과 유효기간 지난 호가로 신규 진입하지 않는다.
- 원격 API 오류와 수량 반올림: 주문 수량이 손실·명목·증거금 상한을 넘지 않는다.

---

### Task 1: 입력 데이터와 위험 계산

**Files:** `jevbot/domain.py`, `jevbot/indicators.py`, `jevbot/risk.py`, `tests/test_indicators.py`, `tests/test_risk.py`

**Interfaces:** `build_features(candles_by_interval, now_ms) -> dict`; `size_entry(equity, price, atr, cost_rate, rules, available_margin, side) -> EntryPlan | None`; `loss_halt(initial_equity, day_start_equity, current_equity) -> bool`.

- [ ] 종료 봉·300개 준비·EMA20/50·RSI14·ATR14·거래량 배율을 손계산 fixture로 검증하는 실패 테스트를 작성·실행한다.
- [ ] Decimal 수량 내림, 5,000원 상당 손실 예산, 필터·비용·한도 경계의 실패 테스트를 작성·실행한다.
- [ ] 도메인과 지표·위험 계산을 구현하고 전체 테스트를 통과시킨다.

### Task 2: JEV 판단 계약

**Files:** `jevbot/jev.py`, `tests/test_jev.py`

**Interfaces:** `JevDecider.decide(state, held: bool) -> Decision`; `gate_decision(decision, held: bool) -> str`.

- [ ] 응답 분포의 진입 0.65·마진 0.20, 보유 중 CLOSE 0.60, 오류/스키마 이상 시 WAIT/KEEP의 실패 테스트를 작성·실행한다.
- [ ] 공식 SDK Choice 질문, 고정 모델, 시간 제한과 전체 분포 기록을 구현해 테스트를 통과시킨다.

### Task 3: Binance REST 경계

**Files:** `jevbot/binance.py`, `tests/test_binance.py`

**Interfaces:** 서명 요청·시세·계좌·포지션·일반 주문·조건부 주문·거래 규칙·주문 조회. 주문 결과 불명은 `UnknownOrderOutcome`으로 구분한다.

- [ ] 서명, Decimal 문자열, LIMIT IOC, STOP_MARKET/TAKE_PROFIT_MARKET, reduceOnly 시장 청산, 503/timeout 분류의 실패 테스트를 작성·실행한다.
- [ ] 공식 USDⓈ-M REST 형식으로 어댑터를 구현해 테스트를 통과시킨다.

### Task 4: 영속 상태와 실행/복구

**Files:** `jevbot/store.py`, `jevbot/execution.py`, `tests/test_store.py`, `tests/test_execution.py`

**Interfaces:** SQLite 장부 `Journal`, 계정·주문 조회 기반 `TradeExecutor.recover/enter/protect/exit`.

- [ ] 동일 슬롯 중복, 중단 상태 재시작 유지, 주문 타임아웃 복구, 부분 체결 보호 실패 테스트를 작성·실행한다.
- [ ] 주문 의도 선저장, 보호 주문 우선 등록, 미확정 주문 재조회, 정리 후 재진입 로직을 구현해 테스트를 통과시킨다.

### Task 5: 서버 루프와 운영 도구

**Files:** `jevbot/runner.py`, `jevbot/main.py`, `pyproject.toml`, `Dockerfile`, `compose.yaml`, `.env.example`, `README.md`, `tests/test_runner.py`

**Interfaces:** 5분 종료 슬롯, 별도 위험 감시, 환경별 시작 점검, `pause_entries`/`flatten_and_halt`, 로컬 상태 화면.

- [ ] 봉 시간 중복·부팅 복구·설정 누락·중단 상태의 실패 테스트를 작성·실행한다.
- [ ] 런타임과 서버 구성을 구현하고 전체 테스트, 정적 문법 검사, 설정 예제 점검을 통과시킨다.
- [ ] 실제 계정/키 없이 수행한 검증 범위와 라이브 배포 전 필요한 테스트넷·24시간 모의운용을 README에 명시한다.
