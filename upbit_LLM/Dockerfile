FROM python:3.13-slim-bullseye
LABEL maintainer="contact@wookingwoo.com"

WORKDIR /auto_trade_coin

# 시스템 패키지 의존성 설치 (numpy/pandas 빌드에 필요한 최소한)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libatlas-base-dev \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

# pip 최신화
RUN pip install --upgrade pip setuptools wheel

# requirements.txt 복사 및 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# numpy, pandas, pandas_ta, pyupbit 명시적으로 설치
RUN pip install --no-cache-dir --prefer-binary numpy pandas pandas_ta pyupbit


# 코드 복사
COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py"]
