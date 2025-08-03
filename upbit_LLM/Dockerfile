FROM arm64v8/python:3.11
LABEL maintainer="contact@wookingwoo.com"

WORKDIR /auto_trade_coin

# Copy requirements.txt
COPY requirements.txt .

# Install system dependencies for ARM compatibility
RUN apt-get update && apt-get install -y \
    libopenblas-base \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for ARM compatibility
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
ENV BLAS=None
ENV LAPACK=None
ENV ATLAS=None

# Try ARM-compatible wheel first, fallback to older stable version if needed
RUN pip install --no-cache-dir numpy==1.24.3 || pip install --no-cache-dir numpy==1.21.6
RUN pip install --no-cache-dir pandas==2.0.3 || pip install --no-cache-dir pandas==1.5.3

# Install the rest of the packages
RUN pip install -r requirements.txt --ignore-installed pandas numpy

# Copy all codes
COPY . .

EXPOSE 8501
CMD ["streamlit", "run", "streamlit_app.py"]
