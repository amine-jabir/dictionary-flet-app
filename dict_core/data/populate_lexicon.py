"""
Offline Lexicon generator and database builder for dict_core.
Generates an indexed, high-speed SQLite lexical database for instant offline word definitions.
"""

from pathlib import Path
import sqlite3
from typing import Dict, List

from dict_core.models.word import Definition, Meaning, Phonetic, WordEntry
from dict_core.providers.offline_provider import DEFAULT_OFFLINE_DB_PATH, OfflineDictionaryProvider


def get_curated_lexical_data() -> List[WordEntry]:
    """Generates a rich curated seed vocabulary of essential and advanced English terms."""
    raw_entries = [
        {
            "word": "hello",
            "ipa": "/həˈloʊ/",
            "meanings": [
                {
                    "pos": "interjection",
                    "defs": [
                        ("An expression of greeting used when meeting someone or answering the telephone.", "Hello, how are you today?", ["hi", "greetings", "hey"], ["goodbye", "farewell"])
                    ]
                },
                {
                    "pos": "noun",
                    "defs": [
                        ("An utterance of 'hello'; a greeting.", "She gave a friendly hello as she walked in.", ["greeting", "salutation"], [])
                    ]
                }
            ]
        },
        {
            "word": "dictionary",
            "ipa": "/ˈdɪk.ʃən.ər.i/",
            "meanings": [
                {
                    "pos": "noun",
                    "defs": [
                        ("A reference book or electronic resource listing words of a language with meanings, pronunciations, and etymologies.", "He looked up the definition of the word in the dictionary.", ["lexicon", "wordbook", "glossary", "vocabulary"], [])
                    ]
                }
            ]
        },
        {
            "word": "serendipity",
            "ipa": "/ˌsɛr.ənˈdɪp.ɪ.ti/",
            "meanings": [
                {
                    "pos": "noun",
                    "defs": [
                        ("The occurrence of events by chance in a happy or beneficial way.", "Finding this rare book in an old shop was pure serendipity.", ["chance", "happy accident", "fluke", "fortune"], ["misfortune", "adversity"])
                    ]
                }
            ]
        },
        {
            "word": "resilience",
            "ipa": "/rɪˈzɪl.jəns/",
            "meanings": [
                {
                    "pos": "noun",
                    "defs": [
                        ("The capacity to withstand or recover quickly from difficulties; toughness.", "The community showed remarkable resilience after the storm.", ["tenacity", "fortitude", "endurance", "perseverance"], ["fragility", "weakness"]),
                        ("The ability of a substance or object to spring back into shape; elasticity.", "The material was chosen for its flexibility and resilience.", ["elasticity", "flexibility", "springiness"], ["rigidity", "brittleness"])
                    ]
                }
            ]
        },
        {
            "word": "lucid",
            "ipa": "/ˈluː.sɪd/",
            "meanings": [
                {
                    "pos": "adjective",
                    "defs": [
                        ("Expressed clearly; easy to understand.", "She gave a lucid and compelling explanation of the complex topic.", ["clear", "comprehensible", "transparent", "coherent", "articulate"], ["confusing", "ambiguous", "opaque", "obscure"]),
                        ("Showing ability to think clearly, especially between periods of confusion or illness.", "He had a few lucid moments despite his fever.", ["sane", "rational", "clear-headed"], ["confused", "delirious"])
                    ]
                }
            ]
        },
        {
            "word": "ephemeral",
            "ipa": "/ɪˈfɛm.ər.əl/",
            "meanings": [
                {
                    "pos": "adjective",
                    "defs": [
                        ("Lasting for a very short time; transitory.", "Fame in the internet age can be fleeting and ephemeral.", ["transient", "fleeting", "short-lived", "momentary", "evanescent"], ["permanent", "enduring", "eternal", "everlasting"])
                    ]
                }
            ]
        },
        {
            "word": "pragmatic",
            "ipa": "/præɡˈmæt.ɪk/",
            "meanings": [
                {
                    "pos": "adjective",
                    "defs": [
                        ("Dealing with things sensibly and realistically in a way that is based on practical rather than theoretical considerations.", "She took a pragmatic approach to solving the team's budget constraints.", ["practical", "sensible", "realistic", "down-to-earth"], ["idealistic", "impractical", "unrealistic", "dogmatic"])
                    ]
                }
            ]
        },
        {
            "word": "ubiquitous",
            "ipa": "/juːˈbɪk.wɪ.təs/",
            "meanings": [
                {
                    "pos": "adjective",
                    "defs": [
                        ("Present, appearing, or found everywhere.", "Smartphones have become ubiquitous in modern society.", ["omnipresent", "everywhere", "pervasive", "universal"], ["rare", "scarce", "uncommon"])
                    ]
                }
            ]
        },
        {
            "word": "eloquent",
            "ipa": "/ˈɛl.ə.kwənt/",
            "meanings": [
                {
                    "pos": "adjective",
                    "defs": [
                        ("Fluent or persuasive in speaking or writing.", "He gave an eloquent speech that moved the entire audience to tears.", ["articulate", "persuasive", "expressive", "fluent"], ["inarticulate", "hesitant", "clumsy"])
                    ]
                }
            ]
        },
        {
            "word": "meticulous",
            "ipa": "/məˈtɪk.jə.ləs/",
            "meanings": [
                {
                    "pos": "adjective",
                    "defs": [
                        ("Showing great attention to detail; very careful and precise.", "The researcher kept meticulous records of every experiment.", ["conscientious", "diligent", "fastidious", "scrupulous", "thorough"], ["careless", "sloppy", "negligent"])
                    ]
                }
            ]
        },
        {
            "word": "tenacious",
            "ipa": "/təˈneɪ.ʃəs/",
            "meanings": [
                {
                    "pos": "adjective",
                    "defs": [
                        ("Tending to keep a firm hold of something; clinging or adhering closely.", "The plant has a tenacious grip on the rock face.", ["firm", "tight", "clinging"], ["loose", "weak"]),
                        ("Not readily relinquishing a position, principle, or course of action; determined.", "She was a tenacious advocate for human rights.", ["persistent", "determined", "resolute", "dogged", "stubborn"], ["wavering", "irresolute", "yielding"])
                    ]
                }
            ]
        },
        {
            "word": "empathy",
            "ipa": "/ˈɛm.pə.θi/",
            "meanings": [
                {
                    "pos": "noun",
                    "defs": [
                        ("The ability to understand and share the feelings of another.", "A great leader must possess deep empathy for their team members.", ["compassion", "understanding", "sensitivity", "fellow-feeling"], ["apathy", "indifference", "callousness"])
                    ]
                }
            ]
        },
        {
            "word": "algorithm",
            "ipa": "/ˈæl.ɡə.rɪ.ðəm/",
            "meanings": [
                {
                    "pos": "noun",
                    "defs": [
                        ("A process or set of rules to be followed in calculations or other problem-solving operations, especially by a computer.", "The search engine uses a sophisticated ranking algorithm.", ["procedure", "formula", "routine", "method", "logic"], [])
                    ]
                }
            ]
        },
        {
            "word": "paradigm",
            "ipa": "/ˈpær.ə.daɪm/",
            "meanings": [
                {
                    "pos": "noun",
                    "defs": [
                        ("A typical example or pattern of something; a model or overarching framework.", "Quantum mechanics introduced a radical new paradigm in physics.", ["model", "pattern", "framework", "prototype", "standard"], [])
                    ]
                }
            ]
        },
        {
            "word": "catalyst",
            "ipa": "/ˈkæt.əl.ɪst/",
            "meanings": [
                {
                    "pos": "noun",
                    "defs": [
                        ("A substance that increases the rate of a chemical reaction without itself undergoing any permanent chemical change.", "Platinum acts as a catalyst in automotive exhaust systems.", [], []),
                        ("A person or thing that precipitates an event or accelerates change.", "Her speech acted as a catalyst for widespread reform.", ["stimulus", "spark", "impetus", "trigger", "activator"], ["inhibitor", "deterrent"])
                    ]
                }
            ]
        },
        {
            "word": "anomaly",
            "ipa": "/əˈnɒm.ə.li/",
            "meanings": [
                {
                    "pos": "noun",
                    "defs": [
                        ("Something that deviates from what is standard, normal, or expected.", "The sudden temperature spike was an anomaly in the historical climate data.", ["abnormality", "irregularity", "deviation", "peculiarity", "exception"], ["norm", "conformity", "standard"])
                    ]
                }
            ]
        },
        {
            "word": "synthesize",
            "ipa": "/ˈsɪn.θə.saɪz/",
            "meanings": [
                {
                    "pos": "verb",
                    "defs": [
                        ("Combine a number of things into a coherent whole.", "The research report synthesizes findings from over fifty clinical studies.", ["combine", "integrate", "unify", "merge", "amalgamate"], ["separate", "dissect", "divide"]),
                        ("Produce something by chemical or biological synthesis.", "Plants synthesize glucose through photosynthesis.", ["produce", "create", "generate"], [])
                    ]
                }
            ]
        },
        {
            "word": "innovate",
            "ipa": "/ˈɪn.ə.veɪt/",
            "meanings": [
                {
                    "pos": "verb",
                    "defs": [
                        ("Make changes in something established, especially by introducing new methods, ideas, or products.", "Companies must continually innovate to remain competitive.", ["invent", "pioneer", "create", "modernize", "revolutionize"], ["stagnate", "replicate"])
                    ]
                }
            ]
        },
        {
            "word": "candid",
            "ipa": "/ˈkæn.dɪd/",
            "meanings": [
                {
                    "pos": "adjective",
                    "defs": [
                        ("Truthful and straightforward; frank.", "His candid feedback helped the team address their blind spots.", ["honest", "frank", "direct", "outspoken", "forthright"], ["dishonest", "evasive", "guarded", "insincere"]),
                        ("Taken informally without the subject's knowledge (of a photograph).", "She captured a candid moment of laughter between friends.", ["unposed", "spontaneous", "informal"], ["posed", "staged"])
                    ]
                }
            ]
        },
        {
            "word": "quintessential",
            "ipa": "/ˌkwɪn.tɪˈsɛn.ʃəl/",
            "meanings": [
                {
                    "pos": "adjective",
                    "defs": [
                        ("Representing the most perfect or typical example of a quality or class.", "He was the quintessential gentleman, courteous to everyone.", ["archetypal", "exemplary", "definitive", "prototypical", "classic"], ["atypical", "unrepresentative"])
                    ]
                }
            ]
        },
        {
            "word": "cognition",
            "ipa": "/kɒɡˈnɪʃ.ən/",
            "meanings": [
                {
                    "pos": "noun",
                    "defs": [
                        ("The mental action or process of acquiring knowledge and understanding through thought, experience, and the senses.", "Studies show that physical exercise enhances cognitive function and memory.", ["perception", "comprehension", "awareness", "reasoning", "intellect"], [])
                    ]
                }
            ]
        },
        {
            "word": "coherent",
            "ipa": "/koʊˈhɪər.ənt/",
            "meanings": [
                {
                    "pos": "adjective",
                    "defs": [
                        ("Logical and consistent (of an argument, theory, or policy).", "She proposed a coherent strategy that addressed every department's concerns.", ["logical", "reasoned", "rational", "consistent", "lucid"], ["incoherent", "confused", "muddled", "disjointed"])
                    ]
                }
            ]
        },
        {
            "word": "diligent",
            "ipa": "/ˈdɪl.ɪ.dʒənt/",
            "meanings": [
                {
                    "pos": "adjective",
                    "defs": [
                        ("Having or showing care and conscientiousness in one's work or duties.", "Her diligent efforts resulted in an outstanding academic performance.", ["hardworking", "industrious", "assiduous", "conscientious", "meticulous"], ["lazy", "careless", "slothful", "negligent"])
                    ]
                }
            ]
        },
        {
            "word": "versatile",
            "ipa": "/ˈvɜː.sə.taɪl/",
            "meanings": [
                {
                    "pos": "adjective",
                    "defs": [
                        ("Able to adapt or be adapted to many different functions or activities.", "Python is a versatile programming language used for web apps, data science, and automation.", ["adaptable", "flexible", "multipurpose", "resourceful", "all-round"], ["inflexible", "limited", "specialized"])
                    ]
                }
            ]
        },
        {
            "word": "profound",
            "ipa": "/prəˈfaʊnd/",
            "meanings": [
                {
                    "pos": "adjective",
                    "defs": [
                        ("Very great or intense (of a state, quality, or emotion).", "The book had a profound impact on my perspective of life.", ["deep", "immense", "intense", "far-reaching"], ["superficial", "mild", "slight"]),
                        ("Having or showing great knowledge or insight.", "A profound philosophical treatise.", ["insightful", "wise", "scholarly", "sagacious"], ["shallow", "trivial"])
                    ]
                }
            ]
        },
        {
            "word": "vital",
            "ipa": "/ˈvaɪ.təl/",
            "meanings": [
                {
                    "pos": "adjective",
                    "defs": [
                        ("Absolutely necessary or essential; crucial.", "Good communication is vital for any collaborative project.", ["crucial", "essential", "critical", "indispensable"], ["unimportant", "trivial", "secondary", "optional"]),
                        ("Full of energy; lively.", "A vital and energetic leader.", ["vibrant", "dynamic", "animated"], ["lifeless", "lethargic"])
                    ]
                }
            ]
        },
        {
            "word": "integrate",
            "ipa": "/ˈɪn.tɪ.ɡreɪt/",
            "meanings": [
                {
                    "pos": "verb",
                    "defs": [
                        ("Combine one thing with another so that they become a whole.", "The new software allows users to integrate various data sources seamlessly.", ["combine", "merge", "incorporate", "unite", "fuse"], ["separate", "isolate", "segregate"])
                    ]
                }
            ]
        },
        {
            "word": "articulate",
            "ipa": "/ɑːˈtɪk.jʊ.lət/",
            "meanings": [
                {
                    "pos": "adjective",
                    "defs": [
                        ("Having or showing the ability to speak fluently and coherently.", "She is an articulate speaker who explains complex concepts with ease.", ["eloquent", "fluent", "clear-spoken", "persuasive"], ["inarticulate", "hesitant"])
                    ]
                },
                {
                    "pos": "verb",
                    "defs": [
                        ("Express an idea or feeling fluently and coherently.", "He struggled to articulate his thoughts during the interview.", ["express", "state", "formulate", "voice"], ["suppress", "silence"])
                    ]
                }
            ]
        },
        {
            "word": "dynamic",
            "ipa": "/daɪˈnæm.ɪk/",
            "meanings": [
                {
                    "pos": "adjective",
                    "defs": [
                        ("Characterized by constant change, activity, or progress.", "Modern technology creates a dynamic and rapidly evolving marketplace.", ["energetic", "forceful", "vibrant", "active", "ever-changing"], ["static", "stagnant", "inert", "dormant"])
                    ]
                }
            ]
        },
        {
            "word": "sustainable",
            "ipa": "/səˈsteɪ.nə.bəl/",
            "meanings": [
                {
                    "pos": "adjective",
                    "defs": [
                        ("Able to be maintained at a certain rate or level.", "Sustainable economic growth requires long-term planning.", ["maintainable", "viable", "durable"], ["unsustainable", "unviable"]),
                        ("Conserving an ecological balance by avoiding depletion of natural resources.", "The company invested in sustainable solar energy systems.", ["renewable", "green", "eco-friendly"], ["polluting", "depleting"])
                    ]
                }
            ]
        }
    ]

    word_entries: List[WordEntry] = []
    for item in raw_entries:
        phonetics = [Phonetic(text=item["ipa"])] if "ipa" in item else []
        meanings = []
        for m in item["meanings"]:
            defs = [
                Definition(
                    definition=d[0],
                    example=d[1] if len(d) > 1 and d[1] else None,
                    synonyms=d[2] if len(d) > 2 else [],
                    antonyms=d[3] if len(d) > 3 else [],
                )
                for d in m["defs"]
            ]
            meanings.append(Meaning(part_of_speech=m["pos"], definitions=defs))

        word_entries.append(
            WordEntry(
                word=item["word"],
                phonetics=phonetics,
                meanings=meanings,
                provider="offline_lexicon",
                metadata={"source": "offline_lexicon", "offline": True},
            )
        )

    return word_entries


def build_offline_database(db_path: Path = DEFAULT_OFFLINE_DB_PATH) -> int:
    """Builds and populates the offline lexicon database with seed vocabulary."""
    provider = OfflineDictionaryProvider(db_path=db_path)
    entries = get_curated_lexical_data()

    for entry in entries:
        provider.insert_entry(entry)

    count = provider.count()
    print(f"Offline lexicon database populated successfully with {count} words at: {db_path}")
    return count


if __name__ == "__main__":
    build_offline_database()
