FROM python:3.12
LABEL maintainer="contact@wookingwoo.com"

WORKDIR /auto_trade_coin

# Copy requirements.txt
COPY requirements.txt .

# Install the specified packages
RUN pip install -r requirements.txt

# Copy all codes
COPY . .

EXPOSE 8501
CMD ["start.sh"]
