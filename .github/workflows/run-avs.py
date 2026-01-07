name: Run AV Scripts

on:
  workflow_dispatch:

jobs:
  run_avs:
    runs-on: ubuntu-latest

    strategy:
      max-parallel: 18
      matrix:
        av: [37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54]

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt || pip install httpx

      - name: Run AV${{ matrix.av }}
        run: python scripts/AV${{ matrix.av }}.py
