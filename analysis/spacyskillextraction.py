"""
spaCy-backed skill extraction.

The extractor uses spaCy PhraseMatcher for known skills and aliases, then adds
lightweight phrase mining from noun chunks when a full spaCy model is present.
It falls back to the existing regex keyword extractor if spaCy is unavailable.
"""

import logging
from collections import Counter
from typing import Iterable, List, Tuple

from django.conf import settings

from .nlp_pipeline import SKILL_KEYWORDS, extract_skills

logger = logging.getLogger(__name__)


SKILL_ALIASES = {
    "artificial intelligence": ["ai", "generative ai", "gen ai"],
    "business intelligence": ["bi", "business intelligence", "dashboards", "dashboarding"],
    "communication": ["written communication", "verbal communication", "interpersonal communication"],
    "crm": ["customer relationship management"],
    "data analysis": ["data analyst", "analytical skills", "analysis"],
    "data analytics": ["analytics", "data insights", "insight generation"],
    "financial modelling": ["financial modeling", "financial models"],
    "google analytics": ["ga4", "google analytics 4"],
    "human resources": ["human resource management", "people management"],
    "machine learning": ["ml", "predictive modelling", "predictive modeling"],
    "microsoft office": ["ms office", "office suite"],
    "power bi": ["powerbi", "power-bi", "business intelligence dashboards"],
    "problem solving": ["troubleshooting", "analytical problem solving"],
    "project management": ["programme management", "program management"],
    "sql": ["t-sql", "sql server", "structured query language"],
    "stakeholder management": ["stakeholder engagement", "stakeholder relations"],
    "tableau": ["tableau dashboards"],
    "training and development": ["learning and development", "l&d"],
}

SKILL_HEAD_TERMS = {
    "accounting", "analysis", "analytics", "auditing", "budgeting", "communication",
    "compliance", "dashboard", "dashboards", "development", "forecasting", "leadership",
    "management", "marketing", "modelling", "modeling", "payroll", "programming",
    "recruitment", "reporting", "sales", "service", "statistics", "training",
}


class SpacySkillExtractor:
    def __init__(self):
        self.model_name = getattr(settings, "SPACY_MODEL_NAME", "en_core_web_sm")
        self.nlp = None
        self.matcher = None
        self.alias_lookup = {}
        self.phrase_lookup = {}
        self.backend = "regex"
        self._load_spacy()

    def _load_spacy(self) -> None:
        try:
            import spacy
            from spacy.matcher import PhraseMatcher
        except ImportError:
            logger.info("spaCy is not installed; using regex skill extraction fallback.")
            return

        try:
            self.nlp = spacy.load(self.model_name)
            self.backend = self.model_name
        except OSError:
            logger.warning("spaCy model %s is not installed; using blank English pipeline.", self.model_name)
            self.nlp = spacy.blank("en")
            self.backend = "spacy.blank.en"

        if "sentencizer" not in self.nlp.pipe_names and "parser" not in self.nlp.pipe_names:
            self.nlp.add_pipe("sentencizer")

        self.matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
        patterns_by_label = {}
        for skill in SKILL_KEYWORDS:
            canonical = self._canonical(skill)
            patterns_by_label.setdefault(canonical, set()).add(skill)
        for canonical, aliases in SKILL_ALIASES.items():
            normalized = self._canonical(canonical)
            patterns_by_label.setdefault(normalized, set()).add(canonical)
            patterns_by_label[normalized].update(aliases)

        for canonical, phrases in patterns_by_label.items():
            label = self._label(canonical)
            self.alias_lookup[label] = canonical
            clean_phrases = [phrase for phrase in phrases if phrase]
            for phrase in clean_phrases:
                self.phrase_lookup[self._canonical(phrase)] = canonical
            self.matcher.add(label, [self.nlp.make_doc(phrase) for phrase in clean_phrases])

    def _canonical(self, value: str) -> str:
        return " ".join(value.lower().replace("-", " ").split())

    def _label(self, value: str) -> str:
        return "SKILL_" + "".join(ch if ch.isalnum() else "_" for ch in value.upper())

    def extract(self, text: str) -> List[str]:
        if not text:
            return []
        if not self.nlp or not self.matcher:
            return extract_skills(text)

        doc = self.nlp(text)
        skills = set(extract_skills(text))
        for match_id, _, _ in self.matcher(doc):
            skills.add(self.alias_lookup[self.nlp.vocab.strings[match_id]])

        if doc.has_annotation("DEP"):
            skills.update(self._noun_chunk_skills(doc))

        return sorted(skills)

    def _noun_chunk_skills(self, doc) -> set:
        mined = set()
        for chunk in doc.noun_chunks:
            phrase = self._canonical(chunk.text)
            if not 2 <= len(phrase.split()) <= 4:
                continue
            canonical = self._known_skill_for_phrase(phrase)
            if canonical:
                mined.add(canonical)
                continue
            if any(term in phrase.split() for term in SKILL_HEAD_TERMS):
                mined.add(phrase)
        return mined

    def _known_skill_for_phrase(self, phrase: str):
        if phrase in self.phrase_lookup:
            return self.phrase_lookup[phrase]
        phrase_tokens = set(phrase.split())
        for known_phrase, canonical in sorted(self.phrase_lookup.items(), key=lambda item: len(item[0]), reverse=True):
            known_tokens = set(known_phrase.split())
            if known_tokens and known_tokens.issubset(phrase_tokens):
                return canonical
        return None

    def build_skill_matrix(self, texts: Iterable[str]) -> List[Tuple[str, int]]:
        skills = []
        for text in texts:
            skills.extend(self.extract(text))
        return Counter(skills).most_common()
