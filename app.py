import streamlit as st
from openai import OpenAI
import os
from datetime import datetime
import json
import pandas as pd

# -------------------------------
# OpenAI Client
# -------------------------------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -------------------------------
# Helper Functions
# -------------------------------
def generate_quiz(categories: str):
    messages = [
        {"role": "system", "content": "You are a cybersecurity professional and instructor with 25+ years experience."},
        {"role": "user", "content": 
            f"""
            Create a cybersecurity awareness assessment test.
            Provide EXACTLY 10 questions.
            Each question must include:
            - 4 multiple-choice options
            - Correct Answer
            - Short contextual explanation
            Base the questions on these categories:
            {categories}
            """
        }
    ]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=1500,
        temperature=0.4
    )
    return response.choices[0].message.content.strip()

def parse_quiz(quiz_text: str):
    """Parse quiz text into structured dictionary with robust correct-answer mapping"""
    questions = quiz_text.split("\n\n")
    parsed = []
    for block in questions:
        lines = block.strip().split("\n")
        if len(lines) < 6:
            continue
        question = lines[0]
        options = lines[1:5]
        correct_raw = lines[5].replace("Correct Answer:", "").strip()
        # Map correct answer to exact option text
        correct_text = next((opt for opt in options if correct_raw.lower() in opt.lower()), options[0])
        context = lines[-1].replace("Context:", "").strip()
        parsed.append({
            "question": question,
            "options": options,
            "correct": correct_text,
            "context": context
        })
    return parsed

def save_quiz_file(quiz_text):
    with open("latest_quiz.json", "w") as f:
        json.dump({"quiz_text": quiz_text}, f, indent=4)

def load_quiz_file():
    try:
        with open("latest_quiz.json", "r") as f:
            data = json.load(f)
        return data["quiz_text"]
    except FileNotFoundError:
        return None

def save_student_results(student_name, score, parsed_questions, user_answers):
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    results = []
    for i, q in enumerate(parsed_questions):
        results.append({
            "question": q["question"],
            "student_answer": user_answers[i],
            "correct_answer": q["correct"],
            "context": q["context"]
        })
    filename = f"results_{student_name}_{timestamp}.json"
    with open(filename, "w") as f:
        json.dump({"student_name": student_name, "score": score, "answers": results}, f, indent=4)
    return filename

def load_all_results():
    import glob
    all_results = []
    for file in glob.glob("results_*.json"):
        with open(file, "r") as f:
            all_results.append(json.load(f))
    return all_results

# -------------------------------
# App UI
# -------------------------------
st.title("🔐 Cybersecurity Quiz Platform")
mode = st.sidebar.selectbox("Select Mode:", ["Teacher", "Student"])

# -------------------------------
# Teacher Mode
# -------------------------------
if mode == "Teacher":
    st.header("📌 Teacher Dashboard - Generate Quiz")
    categories_input = st.text_area("Enter Training Categories / Topics:", "Introduction to Cybersecurity")
    
    if st.button("Generate Quiz"):
        if not categories_input.strip():
            st.error("Please enter at least one category.")
        else:
            with st.spinner("Generating quiz via OpenAI..."):
                try:
                    quiz_text = generate_quiz(categories_input)
                    save_quiz_file(quiz_text)
                    st.success("✅ Quiz generated and saved successfully!")
                    st.subheader("Sample Questions Preview:")
                    parsed = parse_quiz(quiz_text)
                    for q in parsed[:3]:  # show first 3 questions as preview
                        st.write(q["question"])
                        st.write(q["options"])
                except Exception as e:
                    st.error(f"Error generating quiz: {e}")
    
    st.subheader("All Student Results")
    all_results = load_all_results()
    if all_results:
        df = pd.DataFrame([{"Student": r["student_name"], "Score": r["score"]} for r in all_results])
        st.table(df)
    else:
        st.info("No student results yet.")

# -------------------------------
# Student Mode
# -------------------------------
elif mode == "Student":
    st.header("📝 Take Quiz")
    student_name = st.text_input("Enter your name:").strip().replace(" ", "_") or "Unknown"

    quiz_text = load_quiz_file()
    if not quiz_text:
        st.warning("Quiz not yet generated by teacher. Please contact your teacher.")
    else:
        parsed_questions = parse_quiz(quiz_text)
        user_answers = []
        for i, q in enumerate(parsed_questions):
            st.subheader(f"Q{i+1}: {q['question']}")
            answer = st.radio("Choose your answer:", q["options"], key=f"q{i}")
            user_answers.append(answer)
        
        if st.button("Submit Answers"):
            score = 0
            for i, q in enumerate(parsed_questions):
                if user_answers[i].strip() == q["correct"].strip():
                    score += 1
            st.success(f"🎉 {student_name}, you scored {score} / {len(parsed_questions)}")
            filename = save_student_results(student_name, score, parsed_questions, user_answers)
            st.info(f"Results saved as **{filename}**")
