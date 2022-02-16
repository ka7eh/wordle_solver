# Words list from http://wordlist.aspell.net/12dicts/.

import argparse
import logging
import random
import re
from textwrap import indent
import time

import Levenshtein
from playwright.sync_api import sync_playwright

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument(
    "word",
    help="[Optional] The word to solve for. If not set, uses Wordle site.",
    nargs="?",
)
arg_parser.add_argument(
    "--auto", action="store_true", help="Automatically guess", default=False
)
arg_parser.add_argument(
    "--random", help="[Optional] Use random word.", action="store_true"
)
arg_parser.add_argument(
    "--tries", help="[Optional] Number of tries to make.", type=int, default=1
)
arg_parser.add_argument("--debug", action="store_true", default=False)

args = arg_parser.parse_args()

LOG_LEVEL = logging.DEBUG if args.debug else logging.INFO

logging.basicConfig(level=LOG_LEVEL, format="%(levelname)-8s %(message)s")
logger = logging.getLogger("Wordle Solver")


class Solver:
    def __init__(self, auto=False):
        self.correct_letters = [None] * 5
        # A mapping of present letters to a set of positions that they do not appear in (confusing, ha?).
        # E.g., if 'A' is in the word, but is not in the second and fourth positions, then the value for key 'A' would be {1, 3}.
        self.present_letters = {}
        self.absent_letters = set()

        self.auto = auto

        with open("words.txt", "r") as f:
            self.words = [(w, self.get_word_weight(w)) for w in f.read().splitlines()]
            self.words.sort(key=lambda x: x[1])

    def get_word_weight(self, word):
        weight = Levenshtein.distance(
            word, "".join(map(lambda c: c if c else "0", self.correct_letters))
        )
        for letter in self.present_letters:
            if letter in word:
                weight -= 1

        return weight

    def update_word_weights(self):
        pattern = []
        for i in range(5):
            if self.correct_letters[i]:
                pattern.append(self.correct_letters[i])
            else:
                exclude = {
                    c for c in self.present_letters if i in self.present_letters[c]
                }
                exclude.update(self.absent_letters)
                if exclude:
                    exclude = "".join(exclude)
                    pattern.append(f"[^{exclude}]")
                else:
                    pattern.append("[a-z]")

        logger.debug(f"Pattern: {''.join(pattern)}")
        pattern = re.compile("".join(pattern))
        self.words = [
            (w[0], self.get_word_weight(w[0]))
            for w in self.words
            if re.match(pattern, w[0])
        ]

        self.words.sort(key=lambda x: x[1])

    def get_min_weight_count(self):
        if not self.words:
            # This shouldn't happen.
            raise IndexError("No words left!")

        min_weight = self.words[0][1]
        for idx, (_, word_weight) in enumerate(self.words):
            if word_weight > min_weight:
                break

        return (idx or 0) + 1

    def solve_word(self, word):
        guess_count = 0
        while guess_count < 6:
            if self.auto:
                guess = "0"
            else:
                guess = input(f"Guess {guess_count+1} (Enter 0 for auto-guess): ")

            if guess == "0":
                self.update_word_weights()
                guess = random.choice(self.words[: self.get_min_weight_count()])[0]
                logger.info(f"Trying '{guess}'")
            elif len(guess) != 5 and guess.lower() not in self.words:
                logger.info("Enter a valid 5 letter word")
                continue

            is_valid_guess = True
            for i in range(5):
                if guess[i] == word[i]:
                    self.correct_letters[i] = guess[i]
                elif guess[i] in word:
                    self.present_letters.setdefault(guess[i], set()).add(i)
                else:
                    self.absent_letters.add(guess[i])

            logger.info(
                f"Answer status: {self.correct_letters}\tPresent letters: {self.present_letters}\t\tAbsent letters: {self.absent_letters}\n"
            )

            if is_valid_guess:
                guess_count += 1
                if all(self.correct_letters):
                    answer = "".join(self.correct_letters)
                    logger.info(f"Answer: {answer}")
                    return answer

    def solve_wordle(self):
        with sync_playwright() as p:
            browser = p.firefox.launch()

            page = browser.new_page()
            page.goto("https://www.nytimes.com/games/wordle/index.html")

            # Reject cookies
            if page.locator("#pz-gdpr-btn-reject").count():
                page.click("#pz-gdpr-btn-reject")

            # Close modals (should be one for help)
            modals = page.locator("game-modal")
            for i in range(modals.count()):
                modals.nth(i).evaluate("node => node.removeAttribute('open')")

            rows = page.locator("game-row")

            guess_count = 0
            answer = None
            while guess_count < 6:
                if self.auto:
                    guess = "0"
                else:
                    guess = input(f"Guess {guess_count+1} (Enter 0 for auto-guess): ")

                if guess == "0":
                    self.update_word_weights()
                    guess = random.choice(self.words[: self.get_min_weight_count()])[0]
                    logger.info(f"Trying '{guess}'")
                elif len(guess) != 5 and guess.lower() not in self.words:
                    logger.info("Enter a valid 5 letter word")
                    continue

                page.type("html", guess)
                page.press("html", key="Enter")

                # Wait for the submission to be validated
                time.sleep(5)

                row_tiles = rows.nth(guess_count).locator("game-tile")

                is_valid_guess = True
                for i in range(5):
                    tile = row_tiles.nth(i)
                    evaluation = tile.get_attribute("evaluation")
                    if not evaluation:
                        # This should be captured by the first tile. If it has not evaluation attribute, it means the word was not accepted.
                        logger.info("Invalid word.")
                        for _ in range(5):
                            page.press("html", key="Backspace")
                        is_valid_guess = False
                        break

                    if evaluation == "correct":
                        self.correct_letters[i] = guess[i]
                    elif evaluation == "present":
                        self.present_letters.setdefault(guess[i], set()).add(i)
                    else:
                        self.absent_letters.add(guess[i])

                logger.info(
                    f"Answer status: {self.correct_letters}\tPresent letters: {self.present_letters}\t\tAbsent letters: {self.absent_letters}\n"
                )

                if is_valid_guess:
                    guess_count += 1
                    if all(self.correct_letters):
                        answer = "".join(self.correct_letters)
                        logger.info(f"Answer: {answer}")
                        break

            browser.close()

        return answer


if __name__ == "__main__":
    word = None
    if args.random:
        with open("words.txt", "r") as f:
            word = random.choice(f.read().splitlines())
    elif args.word:
        word = args.word

    if word:
        success_count = 0
        for _ in range(args.tries):
            answer = Solver(True).solve_word(word)
            if answer == word:
                success_count += 1
        print(f"{success_count}/{args.tries}")
    else:
        print(Solver(auto=args.auto).solve_wordle())
