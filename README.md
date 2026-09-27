# Memecoin Screener

A multi-platform memecoin rug-pull screener.

## Quick Start

python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000

Then open http://127.0.0.1:8000/docs

## Score Interpretation

0-20: LOW_RISK
21-50: MODERATE_RISK
51-75: HIGH_RISK
76-100: CRITICAL

## License

MIT
