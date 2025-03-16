# Auto-Trade-Coin

## Overview

Auto-Trade-Coin is an automated cryptocurrency trading bot designed to optimize trading strategies for various cryptocurrency pairs. It leverages advanced data analytics, real-time market data, and AI-driven insights to make informed trading decisions. The bot is built to maximize profit margins while minimizing risks through a systematic and data-driven approach.

## Strategies

1. **Volatility Breakout Strategy + fbprophet**
   - This strategy uses the Volatility Breakout method combined with the fbprophet library to predict closing prices. It aims to capitalize on significant price movements by setting breakout signals based on daily volatility.
   - [Learn more](https://github.com/wookingwoo/auto-trade-coin/tree/develop/volatility_breakout)

2. **UPbit LMM (OpenAI)**
   - Utilizes OpenAI's language model to analyze market data and make trading decisions on the UPbit exchange. This strategy focuses on optimizing trades for the KRW-BTC pair using AI-driven insights.
   - [Learn more](https://github.com/wookingwoo/auto-trade-coin/tree/develop/gpt4)

3. **Bithumb LMM (DeepSeek)**
   - Similar to the UPbit strategy, this approach uses DeepSeek's language model to interact with the Bithumb API. It fetches market data and makes trading decisions to optimize trading outcomes.
   - [Learn more](https://github.com/wookingwoo/auto-trade-coin/tree/develop/bithumb_LLM)

## Features

- **Automated Trading**: Executes buy, sell, and hold decisions based on AI analysis.
- **Data-Driven Insights**: Utilizes market data, technical indicators, and news sentiment analysis.
- **Risk Management**: Incorporates risk management protocols to safeguard investments.
- **Real-Time Monitoring**: Provides a dashboard for real-time tracking of trading performance.

## Prerequisites

- Docker
- Python 3.12 or later
- Access to UPbit and Bithumb APIs

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/wookingwoo/auto-trade-coin.git
   cd auto-trade-coin
   ```

2. Install the required packages:

   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   - Create a `.env` file in the root directory and add your API keys:

     ```
     UPBIT_ACCESS_KEY=your_upbit_access_key
     UPBIT_SECRET_KEY=your_upbit_secret_key
     BITHUMB_API_KEY=your_bithumb_api_key
     BITHUMB_SECRET_KEY=your_bithumb_secret_key
     ```

4. Run the main script:

   ```bash
   python main.py
   ```

## Usage

- The main script `main.py` fetches market data, formats a prompt, and sends it to the AI model to get a trading decision.
- Based on the decision, it executes buy or sell orders on the respective exchange.

## License

This project is licensed under the MIT License.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request for any enhancements or bug fixes.

## Contact

For any inquiries or support, please contact [contact@wookingwoo.com](mailto:contact@wookingwoo.com).
