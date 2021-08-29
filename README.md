# auto-trade-coin

## introduce source

auto_trade.py: 비트코인 자동매매 (변동성 돌파전략, 15일 이동 평균선, Prophet 종가 예측 적용)

back_test.py : 백테스팅

best_K.py : optimal한 k값 찾기

balanceInquiry.py: 현재 잔고 조회

## 참고 문서

https://wikidocs.net/book/1665

https://github.com/sharebook-kr/pyupbit

## Installation

### Windows

- 아나콘다(https://www.anaconda.com/) 설치

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
