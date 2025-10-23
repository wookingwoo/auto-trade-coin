FROM ubuntu:24.04
LABEL maintainer="contact@wookingwoo.com"

WORKDIR /auto_trade_coin

# Copy requirements.txt
COPY requirements.txt .

# Python, build tools installation
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-dev \
    build-essential gfortran libatlas-base-dev libopenblas-dev liblapack-dev \
    libffi-dev libssl-dev libjpeg-dev zlib1g-dev git curl \
    && rm -rf /var/lib/apt/lists/*


# Install Python packages
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Copy all codes
COPY . .

EXPOSE 8501
CMD ["streamlit", "run", "streamlit_app.py"]
