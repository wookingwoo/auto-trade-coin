# Binance JEV 자동매매 봇

JEV의 `Choice` 판단으로 Binance USDⓈ-M 무기한 선물의 롱·숏 진입과 보유 중 청산을 결정한다. 5분봉이 확정된 뒤 최대 30초 안에 판단하고, 손절·익절·4시간 청산과 계좌 손실 한도는 코드에서 별도로 적용한다. 기본 관찰 종목은 BTCUSDT와 ETHUSDT이며 전체 계정에서 포지션을 하나만 허용한다.

설계 원본은 [기획서](docs/superpowers/specs/2026-09-29-binance-jev-design.md)에 있다. 코드의 장부는 Linux 단일 실행기에서 복구하기 쉬운 SQLite를 사용한다. 형제 프로젝트 `binance_LLM`의 런타임에 의존하지 않는다.

## 설치와 모의거래

Python 3.11 이상:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
```

`.env`의 `TYPESAFE_API_KEY`를 입력한다. 모의거래의 `JEVBOT_PAPER_START_USDT=700`은 원화 100만 원의 환산값으로 확정된 수치가 아니라 실행 예시다. 실제 시작 자금은 운용 계획에 맞춰 직접 설정한다. `.env`는 Git에서 제외된다.

```bash
python -m unittest discover -s tests -v
python -m jevbot run
```

모의거래는 실시간 공개 Binance 시세와 JEV 호출을 사용한다. IOC 체결은 허용한 최악의 지정가로 기록하고, 손절·익절은 1초 감시가 마크가격을 확인한 뒤 시뮬레이션한다. 서버가 꺼진 동안 모의 보호 주문은 발동하지 않는다. 펀딩 비용과 실제 호가 깊이·지연을 완전히 재현하지 않으므로 모의 성과를 실거래 수익성으로 해석하지 않는다.

## 테스트넷과 라이브 설정

테스트넷은 `JEVBOT_MODE=testnet`과 테스트넷 선물 API 키를 사용한다. REST 호스트는 `https://demo-fapi.binance.com`이다. 라이브는 `JEVBOT_MODE=live`, 실제 선물 API 키, `JEVBOT_LIVE_ENABLED=YES`가 모두 있어야 시작한다. 모드마다 다른 DB 경로를 사용해야 한다. Compose는 `/data/<mode>.db`를 사용하며, 로컬 Python 실행에서는 `.env`의 `JEVBOT_DB_PATH`도 모드마다 바꾼다. 기존 DB는 최초 실행 모드에 묶여 다른 모드로 열 수 없다. 키에는 선물 거래에 필요한 권한만 주고 출금 권한은 주지 않는다. 가능하면 서버의 고정 IP만 허용한다.

봇은 계정을 자동 설정하지 않는다. 전용 계정에서 One-way, Single-Asset, BTC/ETH 격리 2배 레버리지를 먼저 설정해야 한다. 시작 점검이 계정 설정이나 거래소 시각 차이를 발견하면 거래를 시작하지 않는다. 자격증명, 서버, Binance 계정은 이 저장소에 포함되지 않는다.

**라이브 준비 상태:** 테스트는 가짜 거래소와 로컬 장부를 대상으로 실행했다. 실제 Binance 테스트넷 주문, API 장애 복구, 24시간 모의운용, 전용 계정의 입출금 대조는 아직 검증되지 않았다. 코드는 Binance `income` 내역에서 이체와 허용 목록 밖의 수입·자산을 감지하거나 조회가 실패하면 신규 진입을 중단한다. 60일 이상 된 최초 장부는 내역 보존 기간을 고려해 중단한다. 이 경로도 실계좌에서 검증되지 않았다. 라이브 모드를 켜기 전에 이 검증을 마쳐야 한다. 코드의 손실 기준은 주문을 멈추고 청산을 시도하는 기준이며 실제 체결 손실을 보장하지 않는다.

## 운영

```bash
python -m jevbot status
python -m jevbot pause
python -m jevbot resume
python -m jevbot flatten-and-halt
```

`pause`는 신규 진입만 막는다. `resume`은 사용자 일시정지만 해제하며 손실 한도·복구 오류의 중단 상태는 지우지 않는다. `flatten-and-halt`는 실행기 장부에 명령을 기록하고 위험 감시 루프가 청산을 시도한다. 명령 뒤 `status`로 결과를 확인한다.

Linux Docker 서버에서는 `.env`를 준비한 뒤 `docker compose up --build -d`로 실행한다. 장부는 Docker 볼륨에 저장한다. SQLite 장부, WAL, 설정을 서버 외부에 암호화 백업하고 복원 시 거래소 포지션·일반 주문·조건부 주문을 먼저 대조한다. Synology 동기화 폴더를 라이브 DB나 실행 잠금 파일 경로로 사용하지 않는다. Docker의 상태 점검은 서버 자체가 다운된 경우 알림을 보낼 수 없다. 서버 밖의 감시 서비스에서 제공한 비밀 HTTPS 핑 URL을 `JEVBOT_HEARTBEAT_URL`에 넣으면 위험 감시가 정상 완료된 뒤 60초마다 신호를 보낸다. 알림 수신 경로와 미수신 경보는 감시 서비스에서 설정한다.

`JEVBOT_DASHBOARD_TOKEN`을 24자 이상으로 설정하면 인증된 읽기 전용 `GET /status`를 연다. Compose는 포트를 서버의 `127.0.0.1:8765`에만 노출한다. 서버 밖에서는 SSH 터널이나 인증된 사설망을 사용한다.

## 판단과 위험 규칙

- JEV 모델 `jev-1.13.0`, 진입 선택 확률 0.65 이상, 1·2위 차이 0.20 이상. CLOSE는 0.60 이상. 이 확률은 승률이 아니다.
- 거래당 최초 운용자산과 현재 자산 중 작은 값의 0.5%를 손실 예산으로 사용한다. 명목금액 50%, 초기 증거금 25%, 일일 손실 2%, 누적 손실 10%를 제한한다.
- `1.5 × ATR14` 손절, 2배 거리 익절, 4시간 최대 보유. 비용과 거래 규칙을 반영한 뒤 수량을 `Decimal` 단위로 내린다.
- 진입은 호가에서 최대 5bp 범위의 IOC 지정가, 청산은 `reduceOnly` 시장가, 보호 주문은 거래소의 `STOP_MARKET`과 `TAKE_PROFIT_MARKET` 조건부 주문으로 낸다. 부분 체결 수량이 시장가 주문 단위와 맞지 않으면 최대 0.5% 허용 범위의 `reduceOnly` IOC를 시도하고 잔여 포지션이 있으면 중단한다.
- 주문 응답이 불명확하면 같은 슬롯을 다시 보내지 않고 거래소 주문 ID를 조회한다. 보호 주문 상태나 계좌 상태를 확인할 수 없으면 신규 진입을 멈춘다.

상세한 검증 항목과 아직 확정하지 않은 운영 설정은 기획서에 남겨 두었다.
