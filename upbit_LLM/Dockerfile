FROM python:3.12-bullseye
LABEL maintainer="contact@wookingwoo.com"

WORKDIR /auto_trade_coin

# 필수 시스템 패키지 설치 (numpy/pandas를 포함)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-numpy \
    python3-pandas \
    libatlas-base-dev \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

# pip 최신화
RUN pip install --upgrade pip setuptools wheel

# requirements 복사 및 설치 (numpy, pandas 제외)
COPY requirements.txt .
RUN sed -i '/numpy/d' requirements.txt && sed -i '/pandas/d' requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# ARM 호환 패키지 설치
RUN pip install --no-cache-dir pandas_ta pyupbit

COPY . .

EXPOSE 8501
CMD ["streamlit", "run", "streamlit_app.py"]
