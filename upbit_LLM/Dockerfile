FROM python:3.13
LABEL maintainer="contact@wookingwoo.com"

WORKDIR /auto_trade_coin

# Copy requirements.txt
COPY requirements.txt .

# Install the specified packages
RUN pip3 install --no-cache-dir --no-binary :all: numpy pandas pandas_ta pyupbit
RUN pip3 install -r requirements.txt

# Copy all codes
COPY . .

EXPOSE 8501
CMD ["streamlit", "run", "streamlit_app.py"]