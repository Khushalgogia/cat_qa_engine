import os
import json
import random
from google import genai
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# ─────────────────────────────────────────────
# STEP 1: Generate raw math pairs programmatically
# ─────────────────────────────────────────────

def generate_raw_questions():
    questions = []

    # Reciprocals: 1/n for n = 2 to 20
    reciprocal_map = {
        2: "50%", 3: "33.33%", 4: "25%", 5: "20%", 6: "16.67%",
        7: "14.28%", 8: "12.5%", 9: "11.11%", 10: "10%",
        11: "9.09%", 12: "8.33%", 13: "7.69%", 14: "7.14%",
        15: "6.67%", 16: "6.25%", 17: "5.88%", 18: "5.56%",
        19: "5.26%", 20: "5%"
    }
    for n, pct in reciprocal_map.items():
        all_vals = list(reciprocal_map.values())
        wrong = [v for v in all_vals if v != pct]
        wrong_3 = random.sample(wrong, 3)
        opts = wrong_3 + [pct]
        random.shuffle(opts)
        questions.append({
            "category": "reciprocal",
            "raw_question": f"1/{n} as a percentage",
            "correct_answer": pct,
            "options": opts,
            "correct_answer_index": opts.index(pct)
        })

    # Squares: 1² to 30²
    for n in range(1, 31):
        ans = n * n
        wrongs = [str((n + r) ** 2) for r in [-2, -1, 1, 2] if r != 0 and (n + r) > 0]
        wrong_3 = random.sample(wrongs, min(3, len(wrongs)))
        while len(wrong_3) < 3:
            wrong_3.append(str(ans + random.choice([-4, 4, 6, -6])))
        opts = wrong_3 + [str(ans)]
        random.shuffle(opts)
        questions.append({
            "category": "square",
            "raw_question": f"{n}² = ?",
            "correct_answer": str(ans),
            "options": opts,
            "correct_answer_index": opts.index(str(ans))
        })

    # Cubes: 1³ to 15³
    for n in range(1, 16):
        ans = n ** 3
        wrongs = [str((n + r) ** 3) for r in [-1, 1, 2] if (n + r) > 0]
        wrong_3 = random.sample(wrongs, min(3, len(wrongs)))
        while len(wrong_3) < 3:
            wrong_3.append(str(ans + random.choice([-10, 10, 25, -25])))
        opts = wrong_3 + [str(ans)]
        random.shuffle(opts)
        questions.append({
            "category": "cube",
            "raw_question": f"{n}³ = ?",
            "correct_answer": str(ans),
            "options": opts,
            "correct_answer_index": opts.index(str(ans))
        })

    # Primes up to 100
    def is_prime(n):
        if n < 2: return False
        for i in range(2, int(n**0.5)+1):
            if n % i == 0: return False
        return True

    composites_with_factors = []
    for n in range(50, 150):
        if not is_prime(n):
            for i in range(2, int(n**0.5)+1):
                if n % i == 0:
                    composites_with_factors.append((n, i, n//i))
                    break

    for n, f1, f2 in random.sample(composites_with_factors, min(25, len(composites_with_factors))):
        correct = f"{f1} × {f2}"
        wrongs = [
            f"Prime",
            f"{f1+1} × {f2-1}" if f1+1 != f2-1 else f"{f1+2} × {f2}",
            f"{f1-1} × {f2+1}" if f1 > 1 else f"{f1} × {f2+2}"
        ]
        opts = wrongs + [correct]
        random.shuffle(opts)
        questions.append({
            "category": "prime",
            "raw_question": f"Can {n} be factored, or is it prime?",
            "correct_answer": correct,
            "options": opts,
            "correct_answer_index": opts.index(correct)
        })

    # Multiplication tables: selective high-value pairs
    valuable_pairs = [
        (13, 7), (17, 8), (14, 9), (18, 7), (23, 6),
        (16, 7), (19, 8), (21, 7), (24, 6), (27, 8),
        (28, 7), (17, 9), (13, 12), (14, 13), (23, 8),
        (17, 13), (19, 12), (24, 8), (26, 7), (29, 6)
    ]
    for a, b in valuable_pairs:
        ans = a * b
        wrongs = [str(ans + d) for d in [-10, 10, a, -b] if ans + d != ans][:3]
        while len(wrongs) < 3:
            wrongs.append(str(ans + random.choice([-5, 5, -15, 15])))
        opts = wrongs + [str(ans)]
        random.shuffle(opts)
        questions.append({
            "category": "table",
            "raw_question": f"{a} × {b} = ?",
            "correct_answer": str(ans),
            "options": opts,
            "correct_answer_index": opts.index(str(ans))
        })

    return questions

# ─────────────────────────────────────────────
# STEP 2: Wrap in contextual framing via Gemini
# ─────────────────────────────────────────────

CONTEXT_PROMPT = """
You are helping create flashcard-style math questions for a product analyst 
preparing for the CAT exam. 

Below is a batch of raw math facts. For each one, rewrite the question as a 
short, vivid scenario from the world of product analytics, dashboards, or 
business operations. Keep it under 2 sentences. Keep the answer options exactly 
as given — do not change them. Do not add formulas. Just make the scenario feel 
real and specific.

Return a JSON array. Each element: 
{{"index": N, "question_text": "rewritten scenario"}}

Return only valid JSON. No text outside the JSON.

Batch:
{batch}
"""

def call_gemini(prompt, max_retries=5):
    import time
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3-flash-preview", contents=prompt
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            return text
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait = 2 ** attempt * 10
                print(f"  ⏳ Rate limited. Waiting {wait}s before retry {attempt+1}/{max_retries}...")
                time.sleep(wait)
            else:
                raise
    raise Exception("Max retries exceeded for Gemini API")

def wrap_with_context(raw_batch):
    formatted = []
    for i, q in enumerate(raw_batch):
        formatted.append({
            "index": i,
            "raw": q["raw_question"],
            "correct": q["correct_answer"]
        })
    
    text = call_gemini(CONTEXT_PROMPT.format(batch=json.dumps(formatted, indent=2)))
    return json.loads(text)

# ─────────────────────────────────────────────
# STEP 3: Insert to Supabase
# ─────────────────────────────────────────────

def main():
    print("Generating raw math questions...")
    raw_questions = generate_raw_questions()
    print(f"Generated {len(raw_questions)} raw questions.")

    # Process in batches of 20 to avoid token limits
    batch_size = 20
    all_wrapped = []

    for i in range(0, len(raw_questions), batch_size):
        batch = raw_questions[i:i+batch_size]
        print(f"Wrapping batch {i//batch_size + 1}/{(len(raw_questions)-1)//batch_size + 1}...")
        try:
            wrapped = wrap_with_context(batch)
            for item in wrapped:
                idx = item["index"]
                all_wrapped.append({
                    "original_index": i + idx,
                    "question_text": item["question_text"]
                })
        except Exception as e:
            print(f"Batch failed: {e}. Using raw question text as fallback.")
            for idx, q in enumerate(batch):
                all_wrapped.append({
                    "original_index": i + idx,
                    "question_text": q["raw_question"]
                })

    print(f"\nSample output (first 3 questions):")
    for item in all_wrapped[:3]:
        q = raw_questions[item["original_index"]]
        print(f"  [{q['category']}] {item['question_text']}")
        print(f"  Options: {q['options']}")
        print(f"  Correct: {q['correct_answer']} (index {q['correct_answer_index']})\n")

    confirm = input(f"Insert all {len(raw_questions)} questions into Supabase? (y/n): ")
    if confirm.lower() != 'y':
        print("Aborted.")
        return

    rows = []
    for item in all_wrapped:
        i = item["original_index"]
        q = raw_questions[i]
        rows.append({
            "category": q["category"],
            "difficulty_level": 1,
            "question_text": item["question_text"],
            "options": q["options"],
            "correct_answer_index": q["correct_answer_index"],
            "times_correct": 0,
            "times_attempted": 0
        })

    # Insert in chunks of 50
    for i in range(0, len(rows), 50):
        chunk = rows[i:i+50]
        supabase.table("math_sprints").insert(chunk).execute()
        print(f"Inserted rows {i+1} to {min(i+50, len(rows))}...")

    print(f"\nDone. {len(rows)} questions in the database.")

if __name__ == "__main__":
    main()
