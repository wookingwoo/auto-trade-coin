# auto-trade-coin

## introduce source

backTest.py : 백테스팅

bestK.py : optimal한 k값 찾기

autoTrade.py: 비트코인 자동매매 (변동성 돌파전략, 15일 이동 평균선, Prophet 종가 예측 적용)

autoTradeBitcoinWithMA.py: 상승장 투자전략 (이동평균선 이상일때만 거래)


## 참고 문서

https://wikidocs.net/book/1665

https://github.com/sharebook-kr/pyupbit



## Installation

```sh
sudo apt install python3-pip
pip3 install pyupbit
pip3 install schedule
pip3 install pystan==2.19.1.1
pip3 install convertdate
pip3 install fbprophet
```

pyjwt 모듈을 필요로 합니다. (pyjwt >= 2.0)

```sh
pip install pyjwt
```
