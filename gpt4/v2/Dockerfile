FROM python:3.12
LABEL maintainer="contact@wookingwoo.com"

WORKDIR /root

# Copy requirements.txt
COPY requirements.txt .

# Install the specified packages
RUN pip install -r requirements.txt

# Copy all codes
COPY . .

CMD ["python3", "autotrade.py"]
