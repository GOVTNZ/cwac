"""Audit plugin for text analysis in web documents.

This file has 3 main functions:
 - calculates the Flesch-Kincaid Grade Level of the text
 - calculates the Simple Measure of Gobbledygook (SMOG) Grade Level of the text
 - performs sentiment analysis on the text
"""

# pylint: disable=too-many-branches

import logging
import math
import os
from typing import Any, Union, cast

import nltk  # type: ignore
from bs4 import BeautifulSoup
from nltk.corpus import cmudict  # type: ignore
from nltk.sentiment import SentimentIntensityAnalyzer  # type: ignore
from selenium.common import WebDriverException

from config import config
from src.audit_plugins.default_audit import DefaultAudit
from src.browser import Browser

# Download Natural Language Toolkit data
nltk_dir = os.getcwd() + "/nltk_data/"
nltk.download("punkt_tab", download_dir=nltk_dir, quiet=True)
nltk.download("cmudict", download_dir=nltk_dir, quiet=True)
nltk.download("vader_lexicon", download_dir=nltk_dir, quiet=True)
nltk.data.path.append(nltk_dir)
dictionary = cmudict.dict()

# Bool to toggle if sentiment analysis is run
RUN_SENTIMENT_ANALYSIS = config.audit_plugins["language_audit"]["run_sentiment_analysis"]


class LanguageAudit:
    """Language analysis for web pages."""

    audit_type = "LanguageAudit"

    def __init__(self, browser: Browser, **kwargs: Any) -> None:
        """Init variables."""
        self.browser = browser
        self.url = kwargs["url"]
        self.audit_id = kwargs["audit_id"]
        self.page_id = kwargs["page_id"]
        self.site_data = kwargs["site_data"]

    def run(self) -> Union[list[dict[Any, Any]], bool]:
        """Run the audit.

        Returns:
            bool: if the audit fails
            list[dict[Any, Any]]: a list of audit result dicts
        """
        lang = self.__get_document_lang()

        if lang != "en" or not lang.startswith("en-"):
            logging.warning("Test can only be run on English pages but lang for this page is %s: %s", lang, self.url)
            return True

        # Scrape main content
        content = self.scrape_main_content()

        # Check if test is not applicable (i.e. not enough text)
        if self.is_test_not_applicable(content):
            logging.warning("Test is not applicable: %s", self.url)
            return True

        # Calculate Flesch-Kincaid Grade Level
        fkgl = self.flesch_kincaid_grade_level(content)

        # Calculate SMOG Grade Level
        smog = self.simple_measure_of_gobbledygook(content)

        # Create output rows
        output_rows = [{**fkgl, "smog_gl": smog}]

        # Inject helpUrl
        output_rows[0]["helpUrl"] = (
            "https://www.digital.govt.nz/standards-and-guidance/"
            "design-and-ux/content-design-guidance/writing-style/"
            "plain-language/"
        )

        # Perform sentiment analysis
        if RUN_SENTIMENT_ANALYSIS:
            sentiment = self.sentiment_analysis(content)
            for key, value in sentiment.items():
                output_rows[0][key] = str(value)

        # Get page information from DefaultAudit
        default_audit_row = DefaultAudit(
            browser=self.browser,
            url=self.url,
            site_data=self.site_data,
            audit_id=self.audit_id,
            page_id=self.page_id,
        ).run()[0]

        output_rows = [{**default_audit_row, **row} for row in output_rows]

        return output_rows

    def sentence_ify(self, input_text: str) -> str:
        """Convert a string into a normalised sentence.

        A sentence should have a capital letter at the start,
        and end with a period. No trailing whitespace either.

        Args:
            input_text (str): the input text

        Returns:
            str: the normalised sentence
        """
        # Remove leading and trailing whitespace
        output = input_text.strip()

        # Capitalise the first letter
        if output:
            output = output[0].upper() + output[1:]

        # If it ends with a colon, remove it
        if output.endswith(":"):
            output = output[:-1]

        # Common punctuation that ends a sentence
        end_punct = set([".", "!", "?"])

        # If the element's content doesn't end with punctuation, add a period
        if not output.endswith(tuple(end_punct)):
            output += "."

        return output

    def filter_out_non_text(self, soup: BeautifulSoup) -> None:
        """Filter out non-text elements from the soup.

        Args:
            soup (BeautifulSoup): the soup to filter
        """
        # Remove all SVGs
        for svg in soup.find_all("svg"):
            svg.decompose()

        # Remove all tables
        for table in soup.find_all("table"):
            table.decompose()

        # Replace all img with <p> of alt text
        for img in soup.find_all("img"):
            try:
                text_for_p = img.get("alt")
                if text_for_p is not None:
                    p = soup.new_tag("p")
                    p.string = text_for_p
                    img.replace_with(p)
                    continue
            except TypeError:
                pass
            except AttributeError:
                pass
            img.decompose()

    def scrape_main_content(self) -> str:
        """Scrapes the main content out of a webpage, v2.

        Uses Mozilla's Readability library.

        Returns:
            str: the main content of the page
        """
        # Read Readability.js
        path_1 = "./node_modules/@mozilla/readability/Readability.js"
        with open(path_1, "r", encoding="utf-8-sig") as file:
            readability_js = file.read()

        path_2 = "./node_modules/@mozilla/readability/Readability-readerable.js"
        with open(path_2, "r", encoding="utf-8-sig") as file:
            readability_js += file.read()

        # JavaScript to execute Readability
        final_js = f"""
        {readability_js}
        const documentCopy = document.cloneNode(true);
        if (isProbablyReaderable(documentCopy) === false) return false;
        const reader = new Readability(documentCopy);
        const article = reader.parse();
        if (article === null) return false;
        return [article.title, article.content];
        """

        # Execute JavaScript
        try:
            content = self.browser.driver.execute_script(final_js)
        except Exception:  # pylint: disable=broad-except
            logging.exception("WebDriver exception for Readability")
            return ""

        if content is False:
            logging.warning(
                "Readability rejected the page. %s",
                self.url,
            )
            return ""

        # Parse the HTML
        soup = BeautifulSoup(content[1], "html.parser")

        # Remove all SVGs
        self.filter_out_non_text(soup)

        # Accepted element types
        accepted_elements = ["p", "li", "h1", "h2", "h3", "h4", "h5", "h6"]

        flat_output = ""

        for element in soup.find_all(accepted_elements):
            flat_output += self.sentence_ify(element.text) + " "

        # Add the title
        flat_output = self.sentence_ify(content[0]) + " " + flat_output

        return str(flat_output)

    def __get_document_lang(self) -> str:
        try:
            return cast(str, self.browser.driver.execute_script("return document.documentElement.lang"))
        except WebDriverException:
            logging.exception("Could not get document element language")
            return ""

    def count_syllables(self, word: str) -> int:
        """Count num of syllables in a word.

        Args:
            word (str): the word to count syllables in

        Returns:
            int: the number of syllables in the word
        """
        try:
            return [len(list(y for y in x if y[-1].isdigit())) for x in dictionary[word.lower()]][0]
        except KeyError:
            return 1

    def is_test_not_applicable(self, text: str) -> bool:
        """Return True if the test is unlikely to produce good results.

        Some webpages have insufficient text data to perform analysis.
        This function checks if the text is likely to produce good results.

        Args:
            text (str): the text to check

        Returns:
            bool: True if the test is unlikely to produce good results
        """
        # Split the text into sentences
        sentences = nltk.sent_tokenize(text)

        # Split the text into words
        words = nltk.word_tokenize(text)

        # If there are less than 10 sentences, the test is not applicable
        if len(sentences) < 10:
            return True

        # If there are less than 200 words, the test is not applicable
        if len(words) < 200:
            return True

        return False

    def flesch_kincaid_grade_level(self, text: str) -> dict[Any, Any]:
        """Calculate the Flesch-Kincaid Grade Level.

        The Flesch-Kincaid Grade Level is a readability test that estimates
        the years of education needed to understand a text.

        Args:
            text (str): the text to calculate the Flesch-Kincaid Grade Level

        Returns:
            float: the Flesch-Kincaid Grade Level
        """
        # Split the text into sentences
        sentences = nltk.sent_tokenize(text)

        # Split the text into words
        words = nltk.word_tokenize(text)

        # Calculate the average number of words per sentence
        words_per_sentence = len(words) / len(sentences)

        # Calculate the average number of syllables per word
        syllables_per_word = 0.0
        for word in words:
            syllables_per_word += self.count_syllables(word)
        syllables_per_word /= float(len(words))

        # Calculate the Flesch-Kincaid Grade Level
        fk_score = 0.39 * words_per_sentence + 11.8 * syllables_per_word - 15.59

        return {
            "flesch_kincaid_gl": f"{fk_score:.3f}",
            "num_sentences": len(sentences),
            "words_per_sentence": f"{words_per_sentence:.3f}",
            "syllables_per_word": f"{syllables_per_word:.3f}",
        }

    def sentiment_analysis(self, text: str) -> dict[str, float]:
        """Calculate the sentiment analysis score.

        The sentiment analysis score is a score between -1 and 1 that
        indicates the sentiment of the text.

        Args:
            text (str): the text to calculate the sentiment analysis score

        Returns:
            dict[str, float]: the sentiment analysis score
                "neg": negative sentiment
                "neu": neutral sentiment
                "pos": positive sentiment
                "compound": compound sentiment
        """
        sia = SentimentIntensityAnalyzer()
        scores: dict[str, float] = sia.polarity_scores(text)

        # Prefix keys with "sentiment_" for clarity
        scores = {f"sentiment_{k}": v for k, v in scores.items()}
        return scores

    def simple_measure_of_gobbledygook(self, text: str) -> str:
        """Calculate the simple measure of gobbledygook (SMOG).

        SMOG is a readability test that estimates the years of education
        needed to understand a text.

        Args:
            text (str): the text to calculate the SMOG

        Returns:
            str: the SMOG score as a .3f str
        """
        # Split the text into sentences
        sentences = nltk.sent_tokenize(text)

        # Calculate the number of sentences with 3 or more syllables
        polysyllabic_words = 0
        for sentence in sentences:
            words = nltk.word_tokenize(sentence)
            for word in words:
                if self.count_syllables(word) >= 3:
                    polysyllabic_words += 1
        # Calculate the SMOG
        sqrt = math.sqrt(polysyllabic_words * (30.0 / len(sentences)))
        smog = 1.043 * sqrt + 3.1291

        return f"{smog:.3f}"
