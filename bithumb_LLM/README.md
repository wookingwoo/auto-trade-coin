# Bithumb LLM

This project is designed to interact with the Bithumb API to fetch various market data and make trading decisions using the DeepSeek API.

## Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/wookingwoo/auto-trade-coin.git
   cd bithumb_LLM
   ```

2. Install the required packages:

   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:

   Create a `.env` file in the root directory and add your API keys:

   ```
   BITHUMB_API_KEY=your_bithumb_api_key
   BITHUMB_SECRET_KEY=your_bithumb_secret_key
   DEEPSEEK_API_KEY=your_deepseek_api_key
   ```

4. Run the main script:

   ```bash
   python main.py
   ```

## Features

- Fetch minute, day, week, and month candle data.
- Retrieve recent trade data.
- Get current ticker information.
- Access orderbook data.
- Make trading decisions using the DeepSeek API.
- Execute trades on the Bithumb exchange.

## Usage

- The main script `main.py` fetches market data, formats a prompt, and sends it to the DeepSeek API to get a trading decision.
- Based on the decision, it executes buy or sell orders on the Bithumb exchange.

## Configuration

- Modify `config.py` to change the market and symbol settings.
- The `prompt.md` file contains the template for the message sent to the DeepSeek API.

## License

This project is licensed under the MIT License.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request for any enhancements or bug fixes.

## Contact

For any inquiries or support, please contact [contact@wookingwoo.com](mailto:contact@wookingwoo.com).
