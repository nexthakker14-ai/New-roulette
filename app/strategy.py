
RED = {
    1, 3, 5, 7, 9, 12, 14, 16, 18,
    19, 21, 23, 25, 27, 30, 32, 34, 36
}


def attributes(number):
    if number == 0:
        return {
            "color": "green",
            "parity": "zero",
            "range": "zero",
            "column": "zero"
        }

    return {
        "color": "red" if number in RED else "black",
        "parity": "even" if number % 2 == 0 else "odd",
        "range": "low" if number <= 18 else "high",
        "column": f"column_{((number - 1) % 3) + 1}"
    }


RULES = [
    ("color", {5, 6, 7}),
    ("parity", {4, 5, 6}),
    ("range", {4, 5, 6}),
    ("column", {4, 5})
]


def analyze(numbers_newest_first):
    ordered = [
        attributes(number)
        for number in reversed(numbers_newest_first)
    ]

    if not ordered:
        return []

    alerts = []

    for category, thresholds in RULES:
        value = ordered[-1][category]

        if value in ("zero", "green"):
            continue

        streak = 0

        for item in reversed(ordered):
            if item[category] != value:
                break
            streak += 1

        if streak in thresholds:
            alerts.append({
                "category": category,
                "value": value,
                "streak": streak
            })

    return alerts
