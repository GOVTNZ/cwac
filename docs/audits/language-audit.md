# Understanding the language audit

## Overview

This audit analyses the readability and sentiment of the main text content on each page. It produces two readability scores — Flesch-Kincaid Grade Level (FKGL) and SMOG Grade Level — and optionally a sentiment score. These metrics provide an indication of how difficult the page text is to read, supporting plain-language best practice.

See <https://www.digital.govt.nz/standards-and-guidance/design-and-ux/content-design-guidance/writing-style/plain-language/> for more details.

> [!WARNING]
>
> This audit only runs on English-language pages (pages where the `<html lang>` attribute starts with `en`). Pages in other languages are skipped. Pages with fewer than 10 sentences or 200 words are also skipped as the scores would not be reliable.

If the language audit was enabled for a scan, its results will be in the `language_audit.csv` file in the results.

More technical details about how the scores are calculated is available from
the [Python Natural Language Toolkit](https://www.nltk.org/) which is the underlying technology used by the audit.

## Severity rationale

Content that is unnecessarily difficult to read creates barriers for users with cognitive disabilities, low literacy, or those reading in a second language. Plain language is a requirement of the NZ Government's content design guidance.

## Required configuration

The language audit has no special requirements beyond the standard audit configuration. Sentiment analysis is optional and controlled by the `run_sentiment_analysis` setting under `audit_plugins.language_audit` in the config.

## How the audit works

1. Read the `lang` attribute of the `<html>` element. Skip the page if the language is not English.
2. Extract the main readable content from the page using Mozilla's Readability library (the same engine used by Firefox Reader View). Tables and SVGs are excluded; image alt text is included.
3. Skip the page if there are fewer than 10 sentences or 200 words (insufficient data for reliable scores).
4. Calculate the **Flesch-Kincaid Grade Level** (FKGL): a score estimating the US school grade level needed to read the text, based on average words per sentence and average syllables per word.
5. Calculate the **SMOG Grade Level**: an alternative readability score based on the proportion of polysyllabic words across sentences.
6. Optionally calculate **sentiment scores** (negative, neutral, positive, compound) using NLTK's VADER sentiment analyser.

## Interpreting the report spreadsheet

The important columns in the CSV are:

- `flesch_kincaid_gl`
  - The Flesch-Kincaid Grade Level. Lower values indicate easier reading. A score of 8 or below is a common plain-language target.
- `smog_gl`
  - The SMOG Grade Level. Also represents the approximate US school grade level needed. Lower is easier.
- `num_sentences`
  - Number of sentences detected in the main content.
- `words_per_sentence`
  - Average number of words per sentence. Shorter sentences are easier to read.
- `syllables_per_word`
  - Average number of syllables per word. Simpler words are easier to read.
- `sentiment_neg`, `sentiment_neu`, `sentiment_pos`, `sentiment_compound` _(if sentiment analysis is enabled)_
  - VADER sentiment scores. `compound` ranges from -1 (most negative) to +1 (most positive).

    TODO add guidance for what numbers represent a problem. maybe add pass/fail for those numbers if possible?

## Fixing language issues

Readability issues are addressed by editing the content of the site.

- Shorten long sentences by splitting them into two or more shorter sentences.
- Replace complex or technical words with simpler everyday alternatives.
- Use active voice rather than passive voice.
- Refer to the [NZ Government plain language guidance](https://www.digital.govt.nz/standards-and-guidance/design-and-ux/content-design-guidance/writing-style/plain-language/) for further advice.
