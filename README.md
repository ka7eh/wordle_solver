## A Wordle solver/helper [WIP]

> Tested with Python 3.10

Install the dependencies in your environment: `pip install -r requirements.txt`. Then install `playwright` firefox driver: `playwright install firefox`.

Run `python solver.py --auto` to auto solve Wordle's word of the day.

See `python solver.py --help` for more options.

> Need some metrics for success rate. It works great with words with at most one repeated letter, but the rate drops after that.
