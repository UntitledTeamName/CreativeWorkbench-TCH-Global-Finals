# CharacterOS — Developer Setup

## Requirements
- Python 3.10+ (standard library only; zero external runtime dependencies)
- Node.js 18+ (optional, only needed for running `tests/core.test.cjs`)
- Modern web browser (Chrome, Edge, Firefox, Safari)

## Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/mrc2rules/CharacterOS.git
   ```
2. Run tests:
   ```bash
   python -m unittest discover -s tests -p "test_*.py"
   node tests/core.test.cjs
   ```
3. Start the development server (explicit dev mode):
   ```bash
   python -m story_universe_architect.server --port 8765
   ```
4. Open `http://127.0.0.1:8765` in your browser.

## Installing the Wheel Manually
```bash
pip install dist/story_universe_architect_workbench-1.1.0-py3-none-any.whl
characteros --help
characteros start
```

## Installing the WorkBuddy Skill
Extract or install `dist/CharacterOS.zip` into your WorkBuddy skills directory.
Then invoke `/characteros` (or `/sua`) in chat!
