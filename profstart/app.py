from flask import Flask, render_template, request, redirect, url_for
from ai_analyzer import analyze_student_profile
from database import init_db, save_assessment, get_recent_assessments, clear_assessments

app = Flask(__name__)
init_db()

QUESTIONS = [
    # IT, инженерия и системный анализ
    ("q1", "it_tech", "Если что-то глючит или не работает, мне охота докопаться до самой причины, а не тыкать наугад."),
    ("q2", "it_tech", "Мне норм, когда правила игры жёсткие и понятные, а вот сам путь к решению нужно собрать из кусочков."),
    ("q3", "it_tech", "Я могу спокойно залипнуть в одной задаче на пару часов в тишине, если вижу, что всё начинает сходиться."),

    # Естественные науки, биотех и медицина
    ("q4", "science_med", "В споре или сомнениях я скорее поверю фактам и проверке, чем громким словам или догадкам."),
    ("q5", "science_med", "Меня не бесит кропотливая возня с мелочами — я понимаю, что одна ошибка в детали портит весь итог."),
    ("q6", "science_med", "Мне реально интересно, как устроены живые организмы, химия и здоровье — хочется понимать, что внутри."),

    # Гуманитарное, право и работа с людьми
    ("q7", "social_hum", "Я быстро считываю настроение человека и обычно знаю, как поддержать, чтобы стало легче."),
    ("q8", "social_hum", "Мне любопытно, почему люди поступают так, а не иначе, как устроены отношения, культура или законы."),
    ("q9", "social_hum", "Через разговор, переписку или текст мне проще всего разложить мысли по полочкам и помочь другому."),

    # Дизайн, архитектура и креативные индустрии
    ("q10", "creative_design", "Я сразу замечаю кривую вёрстку, странные цвета, неудобную кнопку или красивый фасад дома по дороге."),
    ("q11", "creative_design", "Пустой холст или чистый документ меня скорее заводят на придумку, чем ставят в тупик."),
    ("q12", "creative_design", "Мне хочется делать вещи не «как у всех», а со своим вкусом, подачей и характером."),

    # Экономика, предпринимательство и управление
    ("q13", "econ_mgmt", "Когда дело стоит на месте, мне часто хочется взять руль: кто что делает, какие сроки и что в итоге."),
    ("q14", "econ_mgmt", "Перед тем как вложиться временем или деньгами, я люблю прикинуть выгоду, риски и смысл затеи."),
    ("q15", "econ_mgmt", "Меня прёт от идеи запустить своё дело или проект и самому отвечать за то, что вышло."),
]

TRACK_OPTIONS = [
    "пока изучаю варианты",
    "вуз",
    "колледж (СПО)",
]


@app.route("/", methods=["GET"])
def index():
    recent = get_recent_assessments(limit=10)
    return render_template(
        "index.html",
        questions=QUESTIONS,
        track_options=TRACK_OPTIONS,
        result=None,
        recent=recent,
        form_data={},
    )


@app.route("/analyze", methods=["POST"])
def analyze():
    student_name = request.form.get("student_name", "Гость из СПб")
    grade = request.form.get("grade", "9 класс")
    track_goal = request.form.get("track_goal", "пока изучаю варианты")
    if track_goal not in TRACK_OPTIONS:
        track_goal = "пока изучаю варианты"
    open_answer = request.form.get("open_answer", "")

    scores = {"it_tech": 0, "science_med": 0, "social_hum": 0, "creative_design": 0, "econ_mgmt": 0}
    answers_map = {}

    for q_id, profile_key, _ in QUESTIONS:
        raw_val = request.form.get(q_id, "3")
        try:
            val = max(1, min(5, int(raw_val)))
        except ValueError:
            val = 3
        answers_map[q_id] = val
        scores[profile_key] += val

    analysis = analyze_student_profile(
        scores=scores,
        open_answer=open_answer,
        track_goal=track_goal,
    )
    save_assessment(
        student_name=student_name,
        grade=f"{grade} · {track_goal}",
        open_answer=open_answer,
        analysis=analysis,
    )
    recent = get_recent_assessments(limit=10)

    return render_template(
        "index.html",
        questions=QUESTIONS,
        track_options=TRACK_OPTIONS,
        result=analysis,
        recent=recent,
        form_data={
            "student_name": student_name,
            "grade": grade,
            "track_goal": track_goal,
            "open_answer": open_answer,
            "answers": answers_map,
        },
    )


@app.route("/clear-history", methods=["POST"])
def clear_history():
    clear_assessments()
    return redirect(url_for("index"))


import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)