FROM arm64v8/python:3.11
LABEL maintainer="contact@wookingwoo.com"

WORKDIR /auto_trade_coin

# Copy requirements.txt
COPY requirements.txt .

# Install system dependencies for pandas compatibility on ARM
RUN apt-get update && apt-get install -y \
    build-essential \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install numpy first with OPENBLAS for ARM compatibility
RUN pip install --no-cache-dir numpy==1.24.3

# Install pandas with specific configuration for ARM
RUN OPENBLAS_NUM_THREADS=1 pip install --no-cache-dir --no-binary=pandas pandas==2.0.3

# Install the rest of the packages
RUN pip install -r requirements.txt --ignore-installed pandas

# Copy all codes
COPY . .

EXPOSE 8501
CMD ["streamlit", "run", "streamlit_app.py"]
