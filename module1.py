import io
import os
import sqlite3
from collections import Counter
from datetime import datetime

import streamlit as st
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from xml.sax.saxutils import escape

st.set_page_config(page_title="The Kindness Within", page_icon="💗", layout="centered")

# This educational questionnaire is original, not a validated clinical scale.
# No individual responses or free-text answers are stored in the database.
DB_PATH = os.environ.get("KINDNESS_DB", "kindness_aggregates.sqlite3")
ADMIN_PASSWORD = os.environ.get("KINDNESS_ADMIN_PASSWORD", "")

QUESTIONS = [
    ("q1", "When you make a mistake that nobody else knows about, what hurts the most?", ["I didn't meet my own expectations", "Someone might find out and judge me", "It feels like the mistake says something about me", "I'm disappointed, but the mistake doesn't define me"]),
    ("q4", "Someone you care about says, 'I'm not good enough, no matter how hard I try.' What would you say?", ["You need to stop thinking that way", "You don't have to be perfect to matter", "You should work harder to improve", "What happened that made you feel this way?"]),
    ("q5", "Now imagine you're thinking, 'I'm not good enough, no matter how hard I try.' What would you say to yourself?", ["I need to stop thinking that way", "I don't have to be perfect to matter", "I should work harder to improve", "What happened that made me feel this way?"]),
    ("q9", "Someone important becomes distant without explaining why. What's your first thought?", ["I must have done something wrong", "They probably don't value me", "I feel worried, but there may be other reasons", "I want to understand before blaming myself"]),
    ("q10", "When you feel hurt or embarrassed, what usually happens?", ["I replay it and criticize myself", "I distract myself or push it away", "I notice the feeling, but it's hard to let go", "I try to understand my feelings without judging myself"]),
    ("q13", "Which is hardest to give yourself?", ["Forgiveness after mistakes", "Rest without guilt", "Reassurance that I'm enough", "Patience with my progress", "Understanding when I'm struggling"]),
    ("q14", "What makes speaking kindly to yourself difficult?", ["I don't always feel I deserve it", "I worry kindness will make me less motivated", "Criticism feels more natural", "I don't know what to say to myself", "It isn't especially difficult"]),
]
TRIGGERS = ["Not meeting my expectations", "Rejection or criticism", "Appearance comparisons", "Feeling less successful", "Disappointing someone", "Resting instead of being productive", "Feeling excluded", "None of these"]
SCALE = ["Never", "Rarely", "Sometimes", "Often", "Almost always"]
SCALE_EASE = ["Not difficult", "Slightly difficult", "Moderately difficult", "Very difficult", "Extremely difficult"]

# Each question is optional except the minimum needed for a meaningful report.
def radio(key, label, choices):
    return st.radio(label, choices, index=None, key=key)


def db():
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.execute("CREATE TABLE IF NOT EXISTS counts (metric TEXT NOT NULL, category TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(metric,category))")
    con.execute("CREATE TABLE IF NOT EXISTS submissions (id INTEGER PRIMARY KEY CHECK(id=1), total INTEGER NOT NULL DEFAULT 0)")
    con.execute("INSERT OR IGNORE INTO submissions(id,total) VALUES (1,0)")
    return con


def save_aggregates(results):
    # Counts only. No respondent identifiers, timestamps, free text or response rows.
    with db() as con:
        con.execute("UPDATE submissions SET total=total+1 WHERE id=1")
        items = [("pattern", results["pattern"])]
        items += [("trigger", x) for x in results["triggers"]]
        items += [("focus", results["focus"])]
        items += [("friend_comparison", results["comparison"])]
        for metric, category in items:
            con.execute("INSERT INTO counts(metric,category,count) VALUES(?,?,1) ON CONFLICT(metric,category) DO UPDATE SET count=count+1", (metric, category))


def analyze(a):
    votes = Counter()
    q1 = a.get("q1")
    if q1:
        votes[["High expectations", "Fear of judgment", "Self-blame", "Supportive perspective"][QUESTIONS[0][2].index(q1)]] += 2
    q9 = a.get("q9")
    if q9:
        votes[["Self-blame", "Fear of judgment", "Supportive perspective", "Supportive perspective"][QUESTIONS[3][2].index(q9)]] += 1
    q10 = a.get("q10")
    if q10:
        votes[["Self-blame", "Emotional avoidance", "Emotional awareness", "Supportive perspective"][QUESTIONS[4][2].index(q10)]] += 1
    q14 = a.get("q14")
    if q14:
        votes[["Self-blame", "High expectations", "Self-blame", "Learning self-kindness", "Supportive perspective"][QUESTIONS[6][2].index(q14)]] += 1
    triggers = a.get("q7", [])
    if "Not meeting my expectations" in triggers or "Resting instead of being productive" in triggers:
        votes["High expectations"] += 1
    if "Feeling less successful" in triggers or "Appearance comparisons" in triggers:
        votes["Comparison"] += 1
    if "Rejection or criticism" in triggers or "Feeling excluded" in triggers:
        votes["Fear of judgment"] += 1
    if a.get("q2", 0) >= 4:
        votes["Self-blame"] += 1
    if a.get("q11", 0) >= 4:
        votes["Comparison"] += 1
    if a.get("q3", 0) >= 4:
        votes["Self-blame"] += 1
    pattern = votes.most_common(1)[0][0] if votes else "Mixed reflections"
    if votes and len(votes) > 1 and votes.most_common(2)[0][1] == votes.most_common(2)[1][1]:
        pattern = "Mixed reflections"

    # Parallel question choices are comparable only as broad response styles, not clinical scores.
    styles = ["Dismissive", "Supportive", "Performance-focused", "Curious"]
    friend = a.get("q4")
    self_answer = a.get("q5")
    if friend and self_answer:
        fi = QUESTIONS[1][2].index(friend)
        si = QUESTIONS[2][2].index(self_answer)
        comparison = "Similar response styles" if fi == si else "Different response styles"
        friend_style, self_style = styles[fi], styles[si]
    else:
        comparison, friend_style, self_style = "Not enough answers", "Not answered", "Not answered"

    focus = a.get("q13") or "General self-kindness"
    return {"pattern": pattern, "triggers": [x for x in triggers if x != "None of these"], "focus": focus,
            "comparison": comparison, "friend_style": friend_style, "self_style": self_style,
            "ratings": {"Self-blame": a.get("q2"), "Harsh self-talk": a.get("q3"), "Worth tied to productivity": a.get("q8"), "Comparison distress": a.get("q11"), "Nonjudgmental awareness": a.get("q12")}}


EXERCISES = {
    "Forgiveness after mistakes": ("Separate behavior from identity", "Write down what happened, what you can repair, and what you would do differently. Avoid turning a mistake into a label about who you are."),
    "Rest without guilt": ("Practice rest without earning it", "Choose a short break today. Notice any pressure to justify it, and remind yourself that rest supports your ability to function."),
    "Reassurance that I'm enough": ("Check the standard", "Write down the standard you're using to judge yourself. Ask whether you would apply that same standard to someone you care about."),
    "Patience with my progress": ("Describe progress fairly", "Name one thing you've learned and one thing you're still working on. Both can be true without making you a failure."),
    "Understanding when I'm struggling": ("Ask instead of attack", "When a harsh thought appears, ask: What am I feeling, and what would actually help right now?"),
    "General self-kindness": ("Use a fairer inner voice", "Notice one harsh statement today and rewrite it as something accurate without attacking yourself."),
}


def pdf_bytes(r):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, rightMargin=45, leftMargin=45, topMargin=45, bottomMargin=45)
    styles = getSampleStyleSheet()
    story = []
    def para(text, style="BodyText"):
        story.append(Paragraph(escape(str(text)), styles[style]))
        story.append(Spacer(1, 10))
    para("The Kindness Within", "Title")
    para("Your personal reflection report", "Heading2")
    para("Educational reflection only. Not a diagnosis or validated assessment.")
    para("Your inner voice: " + r["pattern"], "Heading2")
    para("Friend response style: " + r["friend_style"] + ". Self response style: " + r["self_style"] + ".")
    para("Reported triggers", "Heading2")
    para(", ".join(r["triggers"]) if r["triggers"] else "No triggers selected.")
    para("Your reflection ratings", "Heading2")
    for label, val in r["ratings"].items():
        if val is not None:
            para(f"{label}: {val} out of 5")
    para("What the research says", "Heading2")
    para("Kristin Neff (2003) describes self-kindness, common humanity and mindfulness as components of self-compassion. These responses are reflections, not validated scale scores.")
    para("Your next step", "Heading2")
    name, exercise = EXERCISES[r["focus"]]
    para(name + ": " + exercise)
    para("Resources to Improve Your Self-Talk", "Heading2")
    para("Learn about self-compassion and explore practical exercises from Kristin Neff.")
    story.append(Paragraph('<link href="https://self-compassion.org/" color="blue">Visit Self-Compassion.org</link>', styles["BodyText"]))
    story.append(Spacer(1, 10))
    para("Sources", "Heading2")
    para("Alison Wood Brooks, Talk: The Science of Conversation and the Art of Being Ourselves (2025). Communication framing; the extension to inner dialogue is this project's interpretation.")
    para("Neff, K. D. (2003). Self-compassion: An alternative conceptualization of a healthy attitude toward oneself. Self and Identity, 2(2), 85-101. https://doi.org/10.1080/15298860309032")
    doc.build(story)
    return buffer.getvalue()


st.title("The Kindness Within")
st.subheader("How do you communicate with yourself?")
st.write("We spend so much time thinking about how we communicate with others. What about the way we speak to ourselves?")
st.info("This is a voluntary educational reflection, not a psychological evaluation. You can skip questions and stop at any time. Your personal responses are not saved.")

if "started" not in st.session_state:
    st.session_state.started = False
if "report" not in st.session_state:
    st.session_state.report = None
if "shared" not in st.session_state:
    st.session_state.shared = False

if not st.session_state.started:
    if st.button("Begin My Assessment", type="primary"):
        st.session_state.started = True
        st.rerun()
else:
    with st.form("assessment"):
        st.header("1. Your inner voice")
        a = {}
        a["q1"] = radio("q1", "1. When you make a mistake that nobody else knows about, what hurts the most?", QUESTIONS[0][2])
        a["q2"] = st.selectbox("2. How often do you blame yourself even when things weren't entirely in your control?", [None, 1, 2, 3, 4, 5], format_func=lambda x: "Choose an answer" if x is None else f"{x} — {SCALE[x-1]}", key="q2")
        a["q3"] = st.selectbox("3. How often do you speak to yourself more harshly than you would to someone you love?", [None, 1, 2, 3, 4, 5], format_func=lambda x: "Choose an answer" if x is None else f"{x} — {SCALE[x-1]}", key="q3")
        st.header("2. You versus a friend")
        a["q4"] = radio("q4", "4. Someone you care about says, 'I'm not good enough, no matter how hard I try.' What would you say?", QUESTIONS[1][2])
        a["q5"] = radio("q5", "5. Now imagine you're thinking the same thing. What would you say to yourself?", QUESTIONS[2][2])
        a["q6"] = st.selectbox("6. When you disappoint someone, how often do you feel you ARE a disappointment?", [None, 1, 2, 3, 4, 5], format_func=lambda x: "Choose an answer" if x is None else f"{x} — {SCALE[x-1]}", key="q6")
        st.header("3. What triggers self-criticism?")
        a["q7"] = st.multiselect("7. Which situations make it hardest to feel good about yourself? Choose up to three.", TRIGGERS, max_selections=3, key="q7")
        a["q8"] = st.selectbox("8. How difficult is it to feel you deserve rest and kindness when you haven't been productive?", [None, 1, 2, 3, 4, 5], format_func=lambda x: "Choose an answer" if x is None else f"{x} — {SCALE_EASE[x-1]}", key="q8")
        a["q9"] = radio("q9", "9. Someone important becomes distant without explaining why. What's your first thought?", QUESTIONS[3][2])
        st.header("4. How you handle emotional pain")
        a["q10"] = radio("q10", "10. When you feel hurt or embarrassed, what usually happens?", QUESTIONS[4][2])
        a["q11"] = st.selectbox("11. How often does it seem like everyone else handles life better than you?", [None, 1, 2, 3, 4, 5], format_func=lambda x: "Choose an answer" if x is None else f"{x} — {SCALE[x-1]}", key="q11")
        a["q12"] = st.selectbox("12. How often can you notice painful feelings without judging yourself for having them?", [None, 1, 2, 3, 4, 5], format_func=lambda x: "Choose an answer" if x is None else f"{x} — {SCALE[x-1]}", key="q12")
        st.header("5. What would help you?")
        a["q13"] = radio("q13", "13. Which is hardest to give yourself?", QUESTIONS[5][2])
        a["q14"] = radio("q14", "14. What makes speaking kindly to yourself difficult?", QUESTIONS[6][2])
        a["q15"] = st.text_area("15. Optional: One thing I wish I could stop telling myself is...", max_chars=300, key="q15")
        st.caption("Your written reflection is not used for automated scoring or saved to the class statistics.")
        submitted = st.form_submit_button("See My Personal Report", type="primary")
    if submitted:
        # Require only enough information to avoid a misleading empty report.
        if sum(bool(a.get(k)) for k in ["q1", "q4", "q5", "q9", "q10", "q13", "q14"]) < 3:
            st.warning("Please answer at least three multiple-choice questions to create a meaningful report.")
        else:
            st.session_state.report = analyze(a)
            st.session_state.shared = False
    if st.session_state.report:
        r = st.session_state.report
        st.divider()
        st.header("Your Inner Voice Report")
        st.caption("A reflection on your answers, not a diagnosis or personality type.")
        st.subheader("1. Your prominent pattern")
        st.write("**" + r["pattern"] + "**")
        st.write("This is a descriptive theme based on your selected answers. Different situations can bring out different responses.")
        st.subheader("2. How you treat yourself versus others")
        st.write(f"**Toward a friend:** {r['friend_style']}  |  **Toward yourself:** {r['self_style']}")
        st.write(r["comparison"])
        st.subheader("3. Your self-criticism triggers")
        st.write(", ".join(r["triggers"]) if r["triggers"] else "You did not select any triggers.")
        st.subheader("4. Strengths and growth areas")
        ratings = {k: v for k, v in r["ratings"].items() if v is not None}
        if ratings:
            st.bar_chart(ratings, horizontal=True)
            st.caption("Raw answers on a 1–5 scale. Higher numbers are not always better; the final item reflects emotional awareness rather than distress.")
        else:
            st.write("Answer the rating questions to see your reflection chart.")
        st.subheader("5. Psychology behind your responses")
        st.write("Kristin Neff's 2003 framework describes self-kindness, common humanity, and mindfulness as parts of self-compassion. Our questions invite reflection on those themes, but are not a validated measure.")
        st.write("Alison Wood Brooks's *Talk* explores communication between people. This project applies the idea of intentional communication to the way we address ourselves; that extension is our own interpretation.")
        st.subheader("6. Your self-kindness action plan")
        name, exercise = EXERCISES[r["focus"]]
        st.write("**" + name + "**")
        st.write(exercise)
        st.subheader("7. Resources to Improve Your Self-Talk")
        st.write(
            "Want to learn more about treating yourself with kindness? "
            "Explore research-based information and practical self-compassion exercises."
        )
        st.link_button("Explore Self-Compassion Resources", "https://self-compassion.org/")
        st.download_button("Download My PDF Report", pdf_bytes(r), "the_kindness_within_report.pdf", mime="application/pdf")
        st.divider()
        st.subheader("Contribute anonymous class statistics? (Optional)")
        st.write("If you agree, the app will add only category counts to the class dashboard. It will not store your name, written reflection, or individual response record. You still receive your report if you decline.")
        if not st.session_state.shared:
            if st.button("Yes, add my anonymous statistics"):
                try:
                    save_aggregates(r)
                    st.session_state.shared = True
                    st.success("Thank you. Only aggregate counts were added.")
                except Exception:
                    st.error("Statistics could not be saved. Your personal report is still available.")
        else:
            st.success("Your aggregate contribution was recorded for this session.")
        if st.button("Start over"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

with st.sidebar:
    st.caption("Research: Alison Wood Brooks, *Talk* (2025); Kristin Neff, *Self and Identity* (2003).")
    st.caption("Educational reflection only. No personal answer records are retained by this app.")
    with st.expander("Class dashboard (administrator)"):
        if not ADMIN_PASSWORD:
            st.info("Set KINDNESS_ADMIN_PASSWORD as an environment variable to enable the class dashboard.")
        else:
            pwd = st.text_input("Administrator password", type="password")
            if pwd == ADMIN_PASSWORD:
                try:
                    with db() as con:
                        total = con.execute("SELECT total FROM submissions WHERE id=1").fetchone()[0]
                        rows = con.execute("SELECT metric, category, count FROM counts ORDER BY metric, count DESC").fetchall()
                    st.metric("Consenting participants", total)
                    if total < 5:
                        st.info("Class statistics will appear after at least five consenting participants.")
                    else:
                        for metric in sorted({x[0] for x in rows}):
                            st.write("**" + metric.replace("_", " ").title() + "**")
                            safe = [(c, n) for m, c, n in rows if m == metric and n >= 5]
                            if safe:
                                st.bar_chart({c: n for c, n in safe}, horizontal=True)
                            else:
                                st.caption("Counts suppressed because groups are too small.")
                except Exception:
                    st.error("Could not read aggregate statistics.")
            elif pwd:
                st.error("Incorrect password")


