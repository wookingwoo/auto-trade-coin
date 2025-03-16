# UPbit LMM (gpt-4o)

## Overview

Auto-Trade-Coin is an automated cryptocurrency trading bot designed to optimize trading strategies for the KRW-BTC pair. It leverages advanced data analytics, real-time market data, and AI-driven insights to make informed trading decisions. The bot is built to maximize profit margins while minimizing risks through a systematic and data-driven approach.

## Features

- **Automated Trading**: Executes buy, sell, and hold decisions based on AI analysis.
- **Data-Driven Insights**: Utilizes market data, technical indicators, and news sentiment analysis.
- **Risk Management**: Incorporates risk management protocols to safeguard investments.
- **Real-Time Monitoring**: Provides a dashboard for real-time tracking of trading performance.

## Prerequisites

- Docker
- Python 3.12
- MongoDB
- Slack API credentials
- OpenAI API credentials
- Upbit API credentials
- SerpAPI credentials

## Installation

1. **Clone the Repository**:

   ```sh
   git clone https://github.com/wookingwoo/auto-trade-coin.git
   cd gpt4
   ```

2. **Set Up Environment Variables**:
   Create a `.env` file in the root directory and add the following environment variables:

   ```plaintext
   OPENAI_API_KEY=your_openai_api_key
   UPBIT_ACCESS_KEY=your_upbit_access_key
   UPBIT_SECRET_KEY=your_upbit_secret_key
   SERPAPI_API_KEY=your_serpapi_key
   SLACK_BOT_TOKEN=your_slack_bot_token
   SLACK_APP_TOKEN=your_slack_app_token
   SLACK_COINBOT_CHANNEL_NAME=your_slack_channel_name
   GPT_MODEL=your_gpt_model
   MONGO_URI=your_mongo_uri
   ```

3. **Build Docker Image**:

   ```sh
   docker build -t auto-trade-coin-gpt .
   ```

4. **Run Docker Container**:

   ```sh
   docker run --name auto-trade-coin-gpt auto-trade-coin-gpt
   ```

## Usage

### Running the Streamlit Dashboard

To visualize trading performance and insights, run the Streamlit app:

```sh
streamlit run streamlit_app.py
```

### AWS Lambda Deployment

For deploying the trading bot on AWS Lambda, use the provided Dockerfile in the `aws_lambda_env` directory.

### Jenkins CI/CD

A Jenkinsfile is included for automating the build and deployment process using Jenkins.

## Technical Details

- **Trading Strategy**: Utilizes a combination of technical indicators (SMA, EMA, RSI, MACD, Bollinger Bands) and sentiment analysis from news data.
- **AI Integration**: Employs OpenAI's GPT model to analyze data and provide trading recommendations.
- **Database**: MongoDB is used to store trading decisions and historical data.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License.

## Contact

For any inquiries or support, please contact [contact@wookingwoo.com](mailto:contact@wookingwoo.com).
