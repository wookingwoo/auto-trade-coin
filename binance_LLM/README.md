AI-Based Bitcoin Auto Trading System (Binance + LangChain)

Overview
- Collects market data from Binance, stores in SQLite.
- Analyzes features and prompts an LLM (LangChain) for trade decisions.
- Executes trades in paper mode by default; supports live spot/futures with API keys.
- Real-time monitoring via a simple Streamlit dashboard.

Stack
- Python 3.10+
- Binance (REST/WebSocket), python-binance
- LangChain (+ OpenAI or other LLM via LangChain)
- SQLite via SQLAlchemy
- Streamlit for monitoring

Quick Start
1) Create and activate a virtualenv, then install deps:
   - python -m venv .venv && source .venv/bin/activate
   - pip install -r requirements.txt

2) Copy env template and set variables:
   - cp .env.example .env
   - Edit `.env` with your preferences. For live trading, set API keys.

3) Initialize DB and run collector + strategy loop (paper trading):
   - python -m atc.main run

4) Start dashboard in a separate terminal:
   - streamlit run dashboard/streamlit_app.py

Env Vars (.env)
- ATC_SYMBOL=BTCUSDT
- ATC_INTERVAL=1m
- ATC_DB_PATH=atc.db
- ATC_MODE=paper    # paper | live
- ATC_MARKET=spot   # spot | futures
- BINANCE_API_KEY=  # required for live
- BINANCE_API_SECRET=
- OPENAI_API_KEY=   # optional; if missing, uses fallback rule-based strategy

Notes
- Use paper mode to validate signals and PnL without risk.
- To run live, ensure proper API permissions and risk controls.
- This is a reference implementation; extend risk management before using live funds.

