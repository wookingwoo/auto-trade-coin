# Auto-Trade-Coin: Advanced Cryptocurrency Trading Automation Platform

## 🚀 Overview

Auto-Trade-Coin is a sophisticated cryptocurrency trading automation platform that combines cutting-edge artificial intelligence, advanced technical analysis, and robust risk management to optimize trading decisions across multiple major cryptocurrency exchanges. The platform leverages state-of-the-art language models, real-time market data analysis, and proven trading strategies to maximize returns while minimizing risks.

### Key Highlights

- **Multi-Exchange Support**: Binance, UPbit, and Bithumb integration
- **AI-Powered Decision Making**: OpenAI GPT, DeepSeek, and LangChain integration
- **Advanced Trading Strategies**: Volatility breakout, LLM-based analysis, and Prophet forecasting
- **Comprehensive Risk Management**: Portfolio allocation, stop-loss mechanisms, and position sizing
- **Real-Time Monitoring**: Interactive dashboards and Slack notifications
- **Production-Ready**: Docker containerization, AWS Lambda support, and CI/CD pipelines

## 📊 Trading Strategies

### 1. **UPbit LLM Strategy** (`upbit_LLM/`)

*OpenAI-powered KRW-BTC trading optimization* [[Learn more]](https://github.com/wookingwoo/auto-trade-coin/tree/develop/upbit_LLM)

- **Technology Stack**: Python 3.12, OpenAI Agents, MongoDB, Streamlit, Docker
- **Features**:
  - Advanced technical analysis with pandas_ta
  - News sentiment analysis via SerpAPI
  - Fear & Greed Index integration
  - MongoDB for decision history tracking
  - AWS Lambda deployment support
  - Jenkins CI/CD pipeline
**Key Components**:

- `autotrade.py`: Main trading engine with comprehensive market analysis
- `gpt_agent.py`: OpenAI agent for decision making
- `slack_bot.py`: Real-time notifications and monitoring
- `streamlit_app.py`: Interactive trading dashboard

### 2. **Binance LLM Strategy** (`binance_LLM/`)

*AI-powered trading with LangChain integration* [[Learn more]](https://github.com/wookingwoo/auto-trade-coin/tree/develop/binance_LLM)

- **Technology Stack**: Python 3.10+, LangChain, OpenAI, SQLite, Streamlit
- **Features**:
  - Real-time market data collection via Binance WebSocket
  - Technical indicator analysis (SMA, EMA, RSI, MACD, Bollinger Bands, ATR)
  - LLM-driven decision making with confidence scoring
  - Paper trading and live trading modes
  - SQLite database for historical data storage
  - Real-time monitoring dashboard

**Key Components**:

- `binance_client.py`: Binance API integration for spot and futures trading
- `strategy_llm.py`: LangChain-based decision engine
- `features.py`: Technical indicator calculations
- `trader.py`: Order execution engine with paper/live trading support
- `data_collector.py`: Real-time market data collection

### 3. **Bithumb LLM Strategy** (`bithumb_LLM/`)

*DeepSeek-powered multi-asset trading* [[Learn more]](https://github.com/wookingwoo/auto-trade-coin/tree/develop/bithumb_LLM)

- **Technology Stack**: Python 3.10+, DeepSeek API, Slack integration
- **Features**:
  - Multi-timeframe analysis (minute, day, week, month)
  - Order book and tick data analysis
  - Dynamic fee calculation
  - Multi-asset portfolio management (KRW-USDT, KRW-BTC)

**Key Components**:

- `main.py`: Multi-asset trading orchestration
- `fetch_trade.py`: Comprehensive market data collection
- `llm_decision/deepseek.py`: DeepSeek AI integration
- `order_execution.py`: Trade execution engine

### 4. **Volatility Breakout Strategy** (`volatility_breakout/`)

*Classical technical analysis with Prophet forecasting* [[Learn more]](https://github.com/wookingwoo/auto-trade-coin/tree/develop/volatility_breakout)

- **Technology Stack**: Python 3.8+, fbprophet, pyupbit, Schedule
- **Features**:
  - Volatility breakout signal detection
  - 15-day moving average trend confirmation
  - Facebook Prophet price forecasting
  - Automated K-value optimization
  - Comprehensive backtesting framework

**Key Components**:

- `auto_trade.py`: Main trading logic with Prophet integration
- `back_test.py`: Strategy performance backtesting
- `best_K.py`: Optimal K-value determination
- `balance_inquiry.py`: Portfolio management utilities

## 🏗️ Architecture

Independent project structure organized by trading strategy

```
Auto-Trade-Coin/
├── binance_LLM/          # Binance + LangChain Strategy
│   ├── atc/              # Core trading module
│   │   ├── main.py       # Main execution engine
│   │   ├── strategy_llm.py # LLM decision making
│   │   ├── binance_client.py # Exchange API client
│   │   ├── trader.py     # Order execution
│   │   └── features.py   # Technical indicators
│   └── dashboard/        # Streamlit monitoring
├── upbit_LLM/           # UPbit + OpenAI Strategy
│   ├── autotrade.py     # Main trading engine
│   ├── gpt_agent.py     # OpenAI integration
│   ├── streamlit_app.py # Dashboard
│   └── aws_lambda_env/  # AWS deployment
├── bithumb_LLM/         # Bithumb + DeepSeek Strategy
│   ├── main.py          # Multi-asset orchestration
│   ├── fetch_trade.py   # Market data collection
│   └── llm_decision/    # AI decision engine
├── volatility_breakout/ # Classical + Prophet Strategy
│   ├── auto_trade.py    # Prophet-enhanced trading
│   ├── back_test.py     # Performance analysis
│   └── best_K.py        # Parameter optimization
└── gpt4/               # Historical GPT-4 experiments
```

## 🔧 Technical Features

### AI & Machine Learning

- **Language Models**: OpenAI GPT-4/5, DeepSeek, LangChain
- **Forecasting**: Facebook Prophet for time series prediction
- **Sentiment Analysis**: News data integration and market sentiment scoring
- **Technical Analysis**: 15+ technical indicators with customizable parameters

### Risk Management

- **Position Sizing**: Dynamic allocation based on confidence scores
- **Portfolio Management**: Multi-asset rebalancing and diversification
- **Stop-Loss Mechanisms**: Automated loss limitation
- **Fee Optimization**: Exchange-specific fee calculation and minimization

### Infrastructure

- **Containerization**: Docker support for all modules
- **Cloud Deployment**: AWS Lambda integration
- **CI/CD**: Jenkins pipeline automation
- **Monitoring**: Real-time Slack notifications and Streamlit dashboards
- **Data Storage**: SQLite, MongoDB for different use cases

## 📊 Monitoring & Analytics

### Real-Time Dashboards

- **Streamlit Dashboards**: Interactive performance monitoring
- **Trading History**: Comprehensive decision and outcome tracking
- **Portfolio Analytics**: Real-time balance and P&L visualization

### Notification Systems

- **Slack Integration**: Real-time trade notifications
- **Error Alerting**: Automated error detection and reporting
- **Performance Reports**: Scheduled performance summaries

## ⚠️ Risk Disclaimer

**IMPORTANT**: This software is for educational and research purposes. Cryptocurrency trading involves substantial risk of loss. Always:

- Start with paper trading to validate strategies
- Use only funds you can afford to lose
- Implement proper risk management
- Thoroughly test in your environment before live trading
- Monitor performance continuously

## 🤝 Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch
3. Implement your changes with tests
4. Submit a pull request with detailed description

### Development Guidelines

- Follow PEP 8 style guidelines
- Add comprehensive docstrings
- Include unit tests for new features
- Update documentation as needed

## 📞 Support & Contact

- **Email**: [contact@wookingwoo.com](mailto:contact@wookingwoo.com)
- **Issues**: GitHub Issues for bug reports and feature requests

## 🙏 Acknowledgments

Special thanks to [@youtube-jocoding](https://github.com/youtube-jocoding) for the invaluable educational content and inspiration that helped shape this project's development.
