import streamlit as st
from openai import OpenAI
import os
from datetime import datetime

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
# Student Name
# -------------------------------
if "student_name" not in st.session_state:
    st.session_state["student_name"] = ""

st.session_state["student_name"] = st.text_input(
    "Enter your name:",
    st.session_state["student_name"]
)

student_name = st.session_state["student_name"].strip().replace(" ", "_") or "Unknown"

st.write(f"Hello, {st.session_state['student_name']}")

# Load categories from file OR user input
default_categories = ""
if os.path.exists("trainingcontent.txt"):
    with open("trainingcontent.txt", "r") as file:
        default_categories = ", ".join([line.strip() for line in file.readlines()])

categories_input = st.text_area("📌 Training Categories:", default_categories)

# -------------------------------
# Generate Quiz
# -------------------------------
if st.button("Generate Assessment"):
    if not categories_input.strip():
        st.error("Please provide categories.")
    else:
        with st.spinner("Generating questions using OpenAI..."):
            try:
                quiz_text = generate_question(categories_input)
            except Exception as e:
                st.error(f"Error generating quiz: {e}")
                quiz_text = ""
        
        if quiz_text:
            st.success("Quiz Generated Successfully!")
            
            # Save quiz
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            quiz_filename = f"Generated_Quiz_{timestamp}.txt"
            with open(quiz_filename, "w") as f:
                f.write(quiz_text)
            st.info(f"Quiz saved as **{quiz_filename}**")

            st.session_state["quiz"] = quiz_text

# -------------------------------
# QUIZ PARSING + INTERACTIVE QUIZ
# -------------------------------
if "quiz" in st.session_state:
    st.header("📝 Take the Assessment")

    quiz_raw = st.session_state["quiz"]

    # Parse quiz text
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

        st.success(f"🎉 {st.session_state['student_name']}, you scored {score} / {len(parsed_questions)}")
        st.text(feedback)

        # Save results
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        results_filename = f"Quiz_Result_{student_name}_{timestamp}.txt"
        with open(results_filename, "w") as f:
            f.write(feedback)
        st.info(f"Results saved as **{results_filename}**")
