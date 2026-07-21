# language audit

## Overview

This audit analyses the readability and sentiment of the main text content on each page. It produces two readability scores — Flesch-Kincaid Grade Level (FKGL) and SMOG Grade Level — and optionally a sentiment score. These metrics provide an indication of how difficult the page text is to read, supporting plain-language best practice.

See <https://www.digital.govt.nz/standards-and-guidance/design-and-ux/content-design-guidance/writing-style/plain-language/> for more details.

> [!WARNING]
>
> This audit only runs on English-language pages (pages where the `<html lang>` attribute starts with `en`). Pages in other languages are skipped. Pages with fewer than 10 sentences or 200 words are also skipped as the scores would not be reliable.

More technical details about how the scores are calculated is available from
the [Python Natural Language Toolkit](https://www.nltk.org/) which is the underlying technology used by the audit.

## Configuration

As with all audits, this audit is configured by the `audit_plugins` section in the JSON config.

```jsonc
// Truncated snippet from config/config_default.json
{
  "audit_plugins": {
    // ...
    "language_audit": {
      "class_name": "LanguageAudit", // Dev use only - do not change this.
      "enabled": true,
      "run_sentiment_analysis": false
    }
    // ...
  }
  // ...
}
```

The language audit has no special requirements beyond the standard audit configuration.

- `run_sentiment_analysis` (boolean) - Whether to include VADER sentiment scoring in addition to readability scoring.

## How the audit works

1. Read the `lang` attribute of the `<html>` element. Skip the page if the language is not English.
2. Extract the main readable content from the page using Mozilla's Readability library (the same engine used by Firefox Reader View). Tables and SVGs are excluded; image alt text is included.
3. Skip the page if there are fewer than 10 sentences or 200 words (insufficient data for reliable scores).
4. Calculate the **Flesch-Kincaid Grade Level** (FKGL): a score estimating the US school grade level needed to read the text, based on average words per sentence and average syllables per word.
5. Calculate the **SMOG Grade Level**: an alternative readability score based on the proportion of polysyllabic words across sentences.
6. Optionally calculate **sentiment scores** (negative, neutral, positive, compound) using NLTK's VADER sentiment analyser.

## Interpreting results

If the language audit was enabled for a scan, its results will be in `language_audit.csv` in the results.

### Report columns

The columns in `language_audit.csv` include standard metadata fields plus language-specific result fields:

- `organisation`
  - The organisation label from the input base URL list.
- `sector`
  - The sector label from the input base URL list.
- `page_title`
  - The page `<title>` text captured by the browser for this URL.
- `base_url`
  - The base site URL the page belongs to.
- `url`
  - The specific page URL that was audited.
- `viewport_size`
  - Browser viewport dimensions used for this audit row (stored as a width/height object string).
- `audit_id`
  - The audit run + viewport identifier (for example `1_small`).
- `page_id`
  - Sequential page identifier within the run.
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

## Replicating findings

The easiest way to manually replicate these checks is to use a browser addon that calculates the readability scores for a given web page.

## Fixing language issues

Readability issues are addressed by editing the content of the site.

- Shorten long sentences by splitting them into two or more shorter sentences.
- Replace complex or technical words with simpler everyday alternatives.
- Use active voice rather than passive voice.
- Refer to the [NZ Government plain language guidance](https://www.digital.govt.nz/standards-and-guidance/design-and-ux/content-design-guidance/writing-style/plain-language/) for further advice.

## More information

- [NZ Government plain language guidance](https://www.digital.govt.nz/standards-and-guidance/design-and-ux/content-design-guidance/writing-style/plain-language/)
- [Python Natural Language Toolkit](https://www.nltk.org/)
