"""Fixed scoring items from the three public questionnaires."""

DATES = {
    "shed": "October 17–28, 2025",
    "pew": "April 14–20, 2025",
    "anes": "August 3–November 5, 2024",
}

SHED_GRID = "Did you take any of the following actions because of increases in prices over the past 12 months?"
PEW_INTRO = (
    "Online scams and attacks happen when technology is used to trick, harm or steal money or personal "
    "information. This can happen in various ways, like through emails, texts, phone calls, websites or software."
)
PEW_GRID = "How much of a problem do you think online scams and attacks are on each of the following?"
YES_NO = {1: "Yes", 0: "No"}
PROBLEM = {1: "Major problem", 2: "Minor problem", 3: "Not a problem"}
SPENDING = {1: "Increased", 2: "Decreased", 3: "Kept the same"}

ITEMS = {
    "shed": {
        **{
            f"INF3_{letter}": (f"{SHED_GRID}\n{item}", YES_NO)
            for letter, item in zip(
                "abcdef",
                (
                    "Switched to cheaper products",
                    "Used less or stopped using products",
                    "Reduced savings",
                    "Increased borrowing",
                    "Delayed a major purchase",
                    "Worked more or got another job",
                ),
            )
        },
        "INF5": (
            "In the past 12 months, did you make any large purchases sooner than you had planned "
            "because you expected prices to increase?",
            YES_NO,
        ),
    },
    "pew": {
        "OSCAM_PROB": (
            "How much of a problem do you think online scams and attacks are for people in the United States?",
            PROBLEM,
        ),
        **{
            f"OSCAM_PLAT_{letter}": (f"{PEW_GRID}\n{item}", {**PROBLEM, 4: "Not sure"})
            for letter, item in zip(
                "abcd",
                (
                    "Text messages and phone calls",
                    "Emails",
                    "Social media sites or apps",
                    "Shopping sites or apps",
                ),
            )
        },
    },
    "anes": {
        f"V241{number}": (
            f"Should federal spending on {item} be increased, decreased, or kept the same?",
            SPENDING,
        )
        for number, item in (
            (264, "public schools"),
            (267, "tightening border security to prevent illegal immigration"),
            (270, "dealing with crime"),
            (273, "welfare programs"),
            (276, "building and repairing highways"),
            (282, "protecting the environment"),
        )
    },
}
