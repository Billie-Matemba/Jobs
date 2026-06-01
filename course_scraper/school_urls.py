"""
South African business school programme seed URLs.

Add or edit schools here. The scraper starts at these URLs, follows same-domain
programme/MBA links, and imports the best course/module structure it can infer.
"""

SOUTH_AFRICAN_BUSINESS_SCHOOLS = [
    {
        "name": "Johannesburg Business School",
        "aliases": ["JBS", "University of Johannesburg Business School", "UJ JBS"],
        "urls": [
            "https://www.uj.ac.za/jbs/master-in-business-administration-mba/",
        ],
    },

    {
        "name": "Wits Business School",
        "aliases": ["WBS", "University of the Witwatersrand Business School"],
        "urls": [
            "https://www.wbs.ac.za/academic-programmes/mba/master-business-administration",
        ],
    },

    {
        "name": "Gordon Institute of Business Science",
        "aliases": ["GIBS", "University of Pretoria GIBS"],
        "urls": [
            "https://www.gibs.co.za/programmes/mba/",
        ],
    },

    {
        "name": "UCT Graduate School of Business",
        "aliases": ["UCT GSB", "University of Cape Town Graduate School of Business"],
        "urls": [
            "https://www.gsb.uct.ac.za/academic-programmes/mba",
        ],
    },

    {
        "name": "Stellenbosch Business School",
        "aliases": ["USB", "University of Stellenbosch Business School"],
        "urls": [
            "https://www.stellenboschbusiness.ac.za/programmes/mba/",
        ],
    },

    {
        "name": "Henley Business School Africa",
        "aliases": ["Henley Africa", "Henley Business School South Africa"],
        "urls": [
            "https://www.henleysa.ac.za/mba/",
        ],
    },

    {
        "name": "Milpark Business School",
        "aliases": ["Milpark Education Business School"],
        "urls": [
            "https://www.milpark.ac.za/programmes/master-of-business-administration/",
        ],
    },

    {
        "name": "MANCOSA",
        "aliases": ["Management College of Southern Africa"],
        "urls": [
            "https://www.mancosa.co.za/programme/master-of-business-administration/",
        ],
    },

    {
        "name": "Regent Business School",
        "aliases": ["REGENT"],
        "urls": [
            "https://regent.ac.za/programme/master-of-business-administration/",
        ],
    },

    {
        "name": "Regenesys Business School",
        "aliases": ["Regenesys"],
        "urls": [
            "https://www.regenesys.net/program/master-of-business-administration/",
        ],
    },

    {
        "name": "UNISA Graduate School of Business Leadership",
        "aliases": ["UNISA SBL", "School of Business Leadership"],
        "urls": [
            "https://www.unisa.ac.za/sites/sbl/default/Programmes/MBA",
        ],
    },

    {
        "name": "Nelson Mandela University Business School",
        "aliases": ["NMU Business School", "Mandela University Business School"],
        "urls": [
            "https://businessschool.mandela.ac.za/Programmes/MBA",
        ],
    },

    {
        "name": "Rhodes Business School",
        "aliases": ["Rhodes University Business School"],
        "urls": [
            "https://www.ru.ac.za/businessschool/mba/",
        ],
    },

    {
        "name": "Tshwane School for Business and Society",
        "aliases": ["TSB", "Tshwane University of Technology Business School"],
        "urls": [
            "https://www.tsb.ac.za/programmes/mba",
        ],
    },

    {
        "name": "Da Vinci Business School",
        "aliases": ["The Da Vinci Institute"],
        "urls": [
            "https://davinci.ac.za/master-of-business-leadership/",
        ],
    },

    {
        "name": "IMM Graduate School",
        "aliases": ["IMM"],
        "urls": [
            "https://imm.ac.za/academic-qualifications/",
        ],
    },
]


def configured_schools():
    return SOUTH_AFRICAN_BUSINESS_SCHOOLS
