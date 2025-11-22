import streamlit as st
from openai import OpenAI
import os
from datetime import datetime
import pandas as pd

# -------------------------------
# OpenAI Client
# -------------------------------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -------------------------------
# Function: Generate Questions
# -------------------------------
def generate_question(categories: str) -> str:
    messages = [
        {"role": "system", "content": "You are a cybersecurity professional and instructor with 25+ years experience."},
        {"role": "user", "content": 
            f"""
            Create a cybersecurity awareness training assessment test.
            Provide EXACTLY 10 questions.
            Each question must include:
            - 4 multiple-choice options
            - Correct Answer
            - Short contextual explanation
            Respond ONLY with the quiz.
            Base the questions on the following categories:
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

# -------------------------------
# Streamlit UI
# -------------------------------
st.title("🔐 Cybersecurity Assessment Generator (OpenAI API)")

# -------------------------------
# Student Name Input
# -------------------------------
student_name = st.text_input("Enter your name:")
st.write("Hello,", student_name)

# -------------------------------
# Load categories
# -------------------------------
default_categories = ""
if os.path.exists("trainingcontent.txt"):
    with open("trainingcontent.txt", "r") as file:
        default_categories = ", ".join([line.strip() for line in file.readlines()])

categories_input = st.text_area("📌 Training Categories:", default_categories)

# -------------------------------
# Generate Assessment
# -------------------------------
if st.button("Generate Assessment"):
    if not categories_input.strip() or not student_name.strip():
        st.error("Please provide both your name and training categories.")
    else:
        with st.spinner("Generating questions..."):
            quiz_text = generate_question(categories_input)
        st.success("Quiz Generated Successfully!")

        # Save quiz text for student
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        quiz_filename = f"Generated_Quiz_{student_name}_{timestamp}.txt"
        os.makedirs("quizzes", exist_ok=True)
        with open(os.path.join("quizzes", quiz_filename), "w") as f:
            f.write(quiz_text)

        st.session_state["quiz"] = quiz_text

# -------------------------------
# Parse Quiz & Show MCQs
# -------------------------------
if "quiz" in st.session_state:
    st.header("📝 Take the Assessment")
    quiz_raw = st.session_state["quiz"]

    questions = quiz_raw.split("\n\n")
    parsed_questions = []

    for block in questions:
        lines = block.strip().split("\n")
        if len(lines) < 6:
            continue
        question = lines[0]
        options = lines[1:5]
        correct = lines[5].replace("Correct Answer:", "").strip()
        context = lines[-1].replace("Context:", "").strip()
        parsed_questions.append({
            "question": question,
            "options": options,
            "correct": correct,
            "context": context
        })

    user_answers = []
    for i, q in enumerate(parsed_questions):
        st.subheader(f"Q{i+1}: {q['question']}")
        answer = st.radio("Choose your answer:", q["options"], key=f"q{i}")
        user_answers.append(answer)

    if st.button("Submit Answers"):
        score = 0
        feedback = ""
        for i, q in enumerate(parsed_questions):
            user_ans = user_answers[i]
            if user_ans.strip() == q["correct"].strip():
                score += 1
            feedback += f"""
Q{i+1}: {q['question']}
Your Answer: {user_ans}
Correct Answer: {q['correct']}
Context: {q['context']}
---------------------------------------------------
"""
        st.success(f"🎉 {student_name}, you scored {score} / {len(parsed_questions)}")

        # Save student result
        os.makedirs("results", exist_ok=True)
        results_filename = f"Quiz_Result_{student_name}_{timestamp}.txt"
        with open(os.path.join("results", results_filename), "w") as f:
            f.write(feedback)

        st.info(f"Results saved as **{results_filename}**")
        st.text(feedback)

# -------------------------------
# Teacher Dashboard
# -------------------------------
st.header("👨‍🏫 Teacher Dashboard")
admin_pass = st.text_input("Enter admin password:", type="password")

if admin_pass == st.secrets.get("ADMIN_PASS", "12345"):
    st.subheader("All Student Results")
    results_list = []
    if os.path.exists("results"):
        for file in os.listdir("results"):
            if file.endswith(".txt"):
                with open(os.path.join("results", file), "r") as f:
                    content = f.read()
                results_list.append({"file": file, "content": content})
    if results_list:
        for res in results_list:
            st.text_area(res["file"], res["content"], height=200)
    else:
        st.info("No student results found yet.")
