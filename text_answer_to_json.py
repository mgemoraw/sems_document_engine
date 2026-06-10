

import json
from pathlib import Path


def answer_text2jon(source=None):
    try:
        source_path = Path(source)
        result = {}
        with open(source_path, 'r') as file:
            data = file.read()

            # Split by whitespace
            tokens = data.split()

            # Convert into dictionary
            # result = {}
            for i in range(0, len(tokens), 2):
                qno = tokens[i]
                label = tokens[i+1]
                result[int(qno)] = label

        # Save to JSON file
        with open("answers.json", "w") as f:
            json.dump(result, f, indent=2)

        print("✅ Conversion complete! Saved as answers.json")

    except Exception as e:
        raise e


if __name__ == "__main__":
    source_path = "answers.txt"
    answer_text2jon(source_path)