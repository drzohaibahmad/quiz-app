# app.py
import streamlit as st
from openai import OpenAI
import os
from datetime import datetime
import re
import pandas as pd

# -------------------------------
# Config / Client
# -------------------------------
st.set_page_config(page_title="Public Quiz + Admin Dashboard", layout="wide")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")  # change in deployment or set env var

if not OPENAI_API_KEY:
    st.warning("OPENAI_API_KEY not set. Quiz generation will fail without it. Set OPENAI_API_KEY as environment variable.")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

RESULTS_CSV = "results.csv"

# -------------------------------
# Utility: generate quiz via OpenAI
# -------------------------------
def generate_question(categories: str) -> str:
    if not client:
        return ""
    messages = [
        {"role": "system", "content": "You are a cybersecurity professional and instructor with 25+ years experience."},
        {"role": "user", "content":
            f"""
            Create a cybersecurity awareness training assessment test.
            Provide EXACTLY 10 questions.
            Each question must include:
            - 4 multiple-choice options labeled A-D (or 1-4)
            - Correct Answer (letter or letter + option text)
            - Short contextual explanation or 'Context:'
            Respond ONLY with the quiz text (no additional commentary).
            Base the questions on the following categories:
            {categories}
            """
        }
    ]
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=1500,
        temperature=0.35
    )
    return resp.choices[0].message.content.strip()

# -------------------------------
# Robust Parser
# -------------------------------
def parse_quiz(quiz_raw: str):
    parsed_questions = []
    if not quiz_raw:
        return parsed_questions

    blocks = re.split(r"\n\s*\n", quiz_raw.strip())
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        question = lines[0]

        # options: lines that start with A-D or 1-4
        options = [ln for ln in lines[1:] if re.match(r"^[A-D1-4][\.\)]\s+", ln, re.IGNORECASE)]
        # If no A-D style options, try lines that look like choices (4 lines after question)
        if not options and len(lines) >= 5:
            options = lines[1:5]

        # correct answer match (Answer: or Correct Answer:)
        correct_m = re.search(r"(Correct Answer|Answer)\s*[:\-]?\s*(.*)", block, re.IGNORECASE)
        correct = correct_m.group(2).strip() if correct_m else ""

        # context/explanation match
        context_m = re.search(r"(Context|Explanation)\s*[:\-]?\s*(.*)", block, re.IGNORECASE)
        context = context_m.group(2).strip() if context_m else ""

        if question and options and correct:
            parsed_questions.append({
                "question": question,
                "options": options,
                "correct": correct,
                "context": context
            })
    return parsed_questions

# -------------------------------
# Storage helpers
# -------------------------------
def save_result_row(row: dict):
    df = pd.DataFrame([row])
    if os.path.exists(RESULTS_CSV):
        df.to_csv(RESULTS_CSV, mode="a", header=False, index=False)
    else:
        df.to_csv(RESULTS_CSV, index=False)

def load_results():
    if os.path.exists(RESULTS_CSV):
        return pd.read_csv(RESULTS_CSV)
    return pd.DataFrame(columns=[
        "timestamp","student_name","score","total","percentage","details"
    ])

# -------------------------------
# UI: Sidebar navigation
# -------------------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Student (Public Quiz)", "Teacher Dashboard (Admin)"])

# -------------------------------
# PAGE: Student (Public)
# -------------------------------
if page == "Student (Public Quiz)":
    st.header("🔐 Public Quiz — Student")
    st.markdown("Students: enter your name and categories, then generate/attempt the quiz. This is public — no login required.")

    student_name = st.text_input("👤 Your Name")
    categories_input = st.text_area("📌 Training Categories (comma-separated topics)", value="phishing, passwords, social engineering")

    # hold quiz text in session
    if "quiz_text" not in st.session_state:
        st.session_state["quiz_text"] = ""

    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("Generate Assessment"):
            if not student_name.strip():
                st.error("Please enter your name before generating the quiz.")
            elif not categories_input.strip():
                st.error("Please enter categories/topics.")
            else:
                with st.spinner("Generating questions..."):
                    quiz_txt = generate_question(categories_input)
                if quiz_txt:
                    st.session_state["quiz_text"] = quiz_txt
                    st.success("Quiz generated — scroll down to start.")
                else:
                    st.error("Failed to generate quiz. Check OpenAI key or try again.")

    with col2:
        if st.button("Clear Generated Quiz"):
            st.session_state["quiz_text"] = ""
            st.success("Cleared.")

    quiz_raw = st.session_state.get("quiz_text", "")
    parsed = parse_quiz(quiz_raw)

    if parsed:
        st.info(f"Quiz loaded — {len(parsed)} questions found.")
        # render quiz
        user_answers = st.session_state.get("user_answers", [None]*len(parsed))
        # ensure correct length
        if len(user_answers) != len(parsed):
            user_answers = [None]*len(parsed)
        for i, q in enumerate(parsed):
            st.markdown(f"""
                <div style="padding:12px; border-radius:8px; box-shadow: 1px 1px 6px rgba(0,0,0,0.08); margin-bottom:10px; background:#fff;">
                <strong>Q{i+1}:</strong> {q['question']}
                </div>
                """, unsafe_allow_html=True)
            user_answers[i] = st.radio(f"Select (Q{i+1})", q["options"], key=f"student_q_{i}")

            # progress small
            answered_count = sum(1 for a in user_answers if a)
            st.progress(answered_count / len(parsed))
            st.caption(f"Answered {answered_count}/{len(parsed)}")

        st.session_state["user_answers"] = user_answers

        if st.button("Submit Answers"):
            # scoring by mapping correct letter to full option
            total = len(parsed)
            score = 0
            details = []
            for i, q in enumerate(parsed):
                user_ans = user_answers[i] or ""
                # get letter from correct
                clm = re.match(r"^([A-D1-4])", q["correct"].strip(), re.IGNORECASE)
                correct_letter = clm.group(1).upper() if clm else ""
                # find correct option text
                correct_option_text = None
                for opt in q["options"]:
                    if correct_letter and opt.strip().upper().startswith(correct_letter):
                        correct_option_text = opt.strip()
                        break
                # fallback: if correct contains full option text, use that
                if not correct_option_text and q["correct"].strip():
                    correct_option_text = q["correct"].strip()
                is_correct = (user_ans.strip() == correct_option_text) if correct_option_text else False
                if is_correct:
                    score += 1
                details.append({
                    "q_index": i+1,
                    "question": q["question"],
                    "selected": user_ans,
                    "correct": correct_option_text or q["correct"],
                    "context": q.get("context",""),
                    "is_correct": is_correct
                })

            percentage = (score/total)*100 if total else 0
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Save to CSV
            row = {
                "timestamp": ts,
                "student_name": student_name,
                "score": score,
                "total": total,
                "percentage": round(percentage,2),
                "details": str(details)
            }
            save_result_row(row)

            # show results to student with colored feedback
            st.success(f"🎉 {student_name}, you scored {score} / {total} ({percentage:.1f}%)")
            pass_fail = "Pass ✅" if percentage >= 50 else "Fail ❌"
            st.info(pass_fail)

            for d in details:
                st.markdown(f"**Q{d['q_index']}:** {d['question']}")
                if d['is_correct']:
                    st.markdown(f"<span style='color:green; font-weight:bold;'>Your Answer: {d['selected']} — Correct</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<span style='color:red; font-weight:bold;'>Your Answer: {d['selected']} — Incorrect</span>", unsafe_allow_html=True)
                    st.markdown(f"<span style='color:green;'>Correct: {d['correct']}</span>", unsafe_allow_html=True)
                if d.get("context"):
                    with st.expander("Explanation / Context"):
                        st.write(d.get("context"))

            # clear session quiz so next student can generate fresh
            # (optional) keep quiz: comment next line
            st.session_state["quiz_text"] = ""

    else:
        if quiz_raw:
            st.warning("Could not parse questions from generated text. Try regenerating with a slightly different prompt.")
        else:
            st.info("No quiz generated yet. Click 'Generate Assessment' to create one.")

# -------------------------------
# PAGE: Teacher Dashboard (Admin)
# -------------------------------
if page == "Teacher Dashboard (Admin)":
    st.header("📊 Teacher Dashboard (Admin)")

    # password input
    password = st.text_input("Enter admin password", type="password")
    if password != ADMIN_PASS:
        if password:
            st.error("Incorrect admin password.")
        st.stop()

    # load results
    df = load_results()
    st.success("Authenticated — results loaded.")

    st.subheader("Summary")
    st.metric("Total Attempts", len(df))
    avg = df['percentage'].mean() if not df.empty else 0
    st.metric("Average Score (%)", f"{avg:.2f}")

    st.subheader("Top attempts")
    if not df.empty:
        topk = df.sort_values(["percentage","timestamp"], ascending=[False, False]).head(10)
        st.table(topk[["timestamp","student_name","score","total","percentage"]])
    else:
        st.info("No results yet.")

    st.subheader("All Attempts")
    st.dataframe(df.sort_values("timestamp", ascending=False))

    # Simple charts
    if not df.empty:
        st.subheader("Score distribution")
        st.bar_chart(df['percentage'])

    # allow export
    if not df.empty:
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv_data, file_name="results.csv", mime="text/csv")

    # option to clear results (dangerous)
    if st.button("Clear all results (irreversible)"):
        os.remove(RESULTS_CSV)
        st.success("Results cleared. Refresh the page.")
