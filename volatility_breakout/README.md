# auto-trade-coin

## strategy: VolatilityBreakout + fbprophet

1. 변동성 돌파 전략(Volatility Breakout)

- 일일 단위로 일정 수준 이상의 범위를 뛰어넘는 강한 상승세를 돌파 신호로 설정
- 상승하는 추세를 따라가며 일 단위로 수익을 실현하는 단기 투자 전략

2. fbprophet

- Facebook에서 개발한 오픈 소스 예측 라이브러리
- 시계열 데이터를 사용하여 추세 및 계절성을 예측

## introduce source

### main program

- auto_trade.py: 비트코인 자동매매 (변동성 돌파전략, 15일 이동 평균선, Prophet 종가 예측 적용)

### test program

- back_test.py : 백테스팅
- best_K.py : optimal한 k값 찾기
- balance_inquiry.py: 현재 잔고 조회

## 참고 문서

- <https://wikidocs.net/book/1665>
- <https://github.com/sharebook-kr/pyupbit>
- 유튜브 조코딩

## Installation

### Windows

- 아나콘다(<https://www.anaconda.com/>) 설치

```sh
pip install pyupbit
pip install schedule
conda install -c conda-forge fbprophet
pip install pystan --upgrade
```

### Ubuntu 20.4

- fbprophet 설치 환경: 4GB이상 RAM 필요 (AWS t2.medium 이상)
- 동작 환경: AWS t3a.nano에서 정상 동작 확인

```sh
sudo apt update
sudo ln -sf /usr/share/zoneinfo/Asia/Seoul /etc/localtime
sudo apt install python3-pip
pip3 install pyupbit
pip3 install schedule
pip3 install pystan==2.19.1.1
pip3 install convertdate
pip3 install fbprophet
```

## conda 가상환경

```sh
conda info --envs
```

mac/linux

```sh
source activate my_python_env
```

windows

```sh
activate my_python_env
```
