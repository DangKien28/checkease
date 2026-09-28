# Penalty weights based on category and severity
PENALTY_WEIGHTS = {
    "Security": {
        "Critical": 20,
        "Major": 10,
        "Minor": 3,
        "Trivial": 1
    },
    "Reliability": {
        "Critical": 15,
        "Major": 8,
        "Minor": 2,
        "Trivial": 0.5
    },
    "Maintainability": {
        "Critical": 10,
        "Major": 5,
        "Minor": 2,
        "Trivial": 0.5
    }
}

# Default Category Blending Weights
CATEGORY_WEIGHTS = {
    "Security": 0.5,
    "Reliability": 0.3,
    "Maintainability": 0.2
}
