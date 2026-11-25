import os
from flask import Flask, render_template, request, redirect, url_for, session
from ai_analyzer import analyze_student_profile
from database import (
    AVATAR_ANIMALS,
    init_db,
    normalize_login,
    get_user_by_id,
    get_user_by_login,
    register_user,
    authenticate_user,
    update_user_settings,
    create_classroom,
    get_teacher_classroom,
    get_classroom_by_code,
    join_or_leave_classroom,
    set_student_guidance,
    get_guidance_for_student,
    get_classroom_students_overview,
    save_assessment,
    get_assessment_by_id,
    get_user_assessments,
    get_recent_assessments,
    clear_assessments,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "profstart-spb-secret-key-2026")
init_db()

QUESTIONS = [
    ("q1", "it_tech", "Если что-то глючит или не работает, мне охота докопаться до самой причины, а не тыкать наугад."),
    ("q2", "it_tech", "Мне норм, когда правила игры жёсткие и понятные, а вот сам путь к решению нужно собрать из кусочков."),
    ("q3", "it_tech", "Я могу спокойно залипнуть в одной задаче на пару часов в тишине, если вижу, что всё начинает сходиться."),

    ("q4", "science_med", "В споре или сомнениях я скорее поверю фактам и проверке, чем громким словам или догадкам."),
    ("q5", "science_med", "Меня не бесит кропотливая возня с мелочами — я понимаю, что одна ошибка в детали портит весь итог."),
    ("q6", "science_med", "Мне реально интересно, как устроены живые организмы, химия и здоровье — хочется понимать, что внутри."),

    ("q7", "social_hum", "Я быстро считываю настроение человека и обычно знаю, как поддержать, чтобы стало легче."),
    ("q8", "social_hum", "Мне любопытно, почему люди поступают так, а не иначе, как устроены отношения, культура или законы."),
    ("q9", "social_hum", "Через разговор, переписку или текст мне проще всего разложить мысли по полочкам и помочь другому."),

    ("q10", "creative_design", "Я сразу замечаю кривую вёрстку, странные цвета, неудобную кнопку или красивый фасад дома по дороге."),
    ("q11", "creative_design", "Пустой холст или чистый документ меня скорее заводят на придумку, чем ставят в тупик."),
    ("q12", "creative_design", "Мне хочется делать вещи не «как у всех», а со своим вкусом, подачей и характером."),

    ("q13", "econ_mgmt", "Когда дело стоит на месте, мне часто хочется взять руль: кто что делает, какие сроки и что в итоге."),
    ("q14", "econ_mgmt", "Перед тем как вложиться временем или деньгами, я люблю прикинуть выгоду, риски и смысл затеи."),
    ("q15", "econ_mgmt", "Меня прёт от идеи запустить своё дело или проект и самому отвечать за то, что вышло."),
]

TRACK_OPTIONS = [
    "пока изучаю варианты",
    "вуз",
    "колледж (СПО)",
]

GRADE_OPTIONS = ["8 класс", "9 класс", "10 класс", "11 класс", "СПО"]


def _current_user():
    return get_user_by_id(session.get("user_id"))


def _avatar_map():
    return {item["id"]: item for item in AVATAR_ANIMALS}


def _common_context(active_page: str):
    user = _current_user()
    return {
        "active_page": active_page,
        "user": user,
        "avatars": AVATAR_ANIMALS,
        "avatar_map": _avatar_map(),
        "track_options": TRACK_OPTIONS,
        "grade_options": GRADE_OPTIONS,
        "auth_error": session.pop("auth_error", None),
        "notice": session.pop("notice", None),
    }


@app.route("/", methods=["GET"])
def index():
    ctx = _common_context("entry")
    return render_template("entry.html", **ctx)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_val = request.form.get("login", "").strip()
        password = request.form.get("password", "").strip()

        user = authenticate_user(login=login_val, password=password)
        if not user:
            session["auth_error"] = "Неверный логин или пароль."
            return redirect(url_for("login"))

        session["user_id"] = user["id"]
        role_label = "учителя" if user["role"] == "teacher" else "ученика"
        session["notice"] = f"Вход выполнен в кабинет {role_label}: {user['full_name']}."
        return redirect(url_for("cabinet"))

    ctx = _common_context("login")
    return render_template("login.html", **ctx)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        login_val = normalize_login(request.form.get("login", ""))
        password = request.form.get("password", "").strip()
        password_confirm = request.form.get("password_confirm", "").strip()
        role = request.form.get("role", "student").strip()

        if len(login_val) < 3:
            session["auth_error"] = "Логин должен содержать минимум 3 символа."
            return redirect(url_for("register"))

        if len(password) < 4:
            session["auth_error"] = "Пароль должен быть не короче 4 символов."
            return redirect(url_for("register"))

        if password != password_confirm:
            session["auth_error"] = "Пароли не совпадают."
            return redirect(url_for("register"))

        if get_user_by_login(login_val):
            session["auth_error"] = f"Логин «{login_val}» уже занят. Выбери другой или войди."
            return redirect(url_for("register"))

        user = register_user(login=login_val, password=password, role=role, full_name=full_name)
        session["user_id"] = user["id"]
        role_label = "учителя" if user["role"] == "teacher" else "ученика"
        session["notice"] = f"Создан аккаунт {role_label}: {user['full_name']} (@{user['login']})."
        return redirect(url_for("cabinet"))

    ctx = _common_context("register")
    return render_template("register.html", **ctx)


@app.route("/cabinet", methods=["GET"])
def cabinet():
    user = _current_user()
    if not user:
        session["auth_error"] = "Сначала войди в аккаунт или пройди тест в гостевом режиме."
        return redirect(url_for("login"))

    expanded_id = request.args.get("open_result", type=int)
    user_assessments = get_user_assessments(user["id"], limit=20) if user["role"] == "student" else []
    guidance = (
        get_guidance_for_student(user["id"], user.get("classroom_code"))
        if user["role"] == "student"
        else None
    )
    joined_room = (
        get_classroom_by_code(user.get("classroom_code"))
        if user["role"] == "student"
        else None
    )

    teacher_room = get_teacher_classroom(user["id"]) if user["role"] == "teacher" else None
    classroom_students = get_classroom_students_overview(teacher_room["code"]) if teacher_room else []

    expanded_assessment = None
    if expanded_id:
        candidate = get_assessment_by_id(expanded_id)
        if candidate and (
            candidate.get("user_id") == user["id"]
            or (teacher_room and candidate.get("classroom_code") == teacher_room["code"])
        ):
            expanded_assessment = candidate

    ctx = _common_context("cabinet")
    ctx.update(
        {
            "user_assessments": user_assessments,
            "expanded_assessment": expanded_assessment,
            "guidance": guidance,
            "joined_room": joined_room,
            "teacher_room": teacher_room,
            "classroom_students": classroom_students,
        }
    )
    return render_template("cabinet.html", **ctx)


@app.route("/test", methods=["GET"])
def test_page():
    ctx = _common_context("test")
    ctx.update(
        {
            "questions": QUESTIONS,
            "form_data": {},
        }
    )
    return render_template("test.html", **ctx)


@app.route("/result", methods=["GET"])
def result_page():
    report_data = session.get("last_result")
    if not report_data:
        return redirect(url_for("test_page"))
    ctx = _common_context("result")
    ctx.update({"result": report_data})
    return render_template("result.html", **ctx)


@app.route("/settings", methods=["GET"])
def settings_page():
    user = _current_user()
    if not user:
        session["auth_error"] = "Настройки профиля доступны после входа в аккаунт."
        return redirect(url_for("login"))
    ctx = _common_context("settings")
    return render_template("settings.html", **ctx)


@app.route("/history", methods=["GET"])
def history_page():
    recent = get_recent_assessments(limit=20)
    ctx = _common_context("history")
    ctx.update({"recent": recent})
    return render_template("history.html", **ctx)


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    session["notice"] = "Ты вышел из аккаунта."
    return redirect(url_for("index"))


@app.route("/settings/profile", methods=["POST"])
def save_profile_settings():
    user = _current_user()
    if not user:
        return redirect(url_for("login"))

    update_user_settings(
        user_id=user["id"],
        full_name=request.form.get("full_name", user["full_name"]),
        email=request.form.get("email", ""),
        grade=request.form.get("grade", user.get("grade", "9 класс")),
        track_goal=request.form.get("track_goal", user.get("track_goal", "пока изучаю варианты")),
        avatar_id=request.form.get("avatar_id", user.get("avatar_id", "owl")),
        notify_updates=bool(request.form.get("notify_updates")),
    )
    session["notice"] = "Настройки профиля и аватарка сохранены."
    return redirect(url_for("settings_page"))


@app.route("/classroom/create", methods=["POST"])
def classroom_create():
    user = _current_user()
    if not user or user["role"] != "teacher":
        return redirect(url_for("index"))

    title = request.form.get("classroom_title", "")
    room = create_classroom(teacher_id=user["id"], title=title)
    session["notice"] = f"Комната «{room['title']}» создана. Код класса: {room['code']}"
    return redirect(url_for("cabinet"))


@app.route("/classroom/join", methods=["POST"])
def classroom_join():
    user = _current_user()
    if not user or user["role"] != "student":
        return redirect(url_for("index"))

    code = request.form.get("classroom_code", "").strip()
    ok = join_or_leave_classroom(student_id=user["id"], code=code)
    if not ok:
        session["auth_error"] = f"Комната с кодом «{code.upper()}» не найдена."
    elif code:
        session["notice"] = f"Ты вступил в комнату класса {code.upper()}."
    else:
        session["notice"] = "Включён независимый режим (без комнаты класса)."
    return redirect(url_for("cabinet"))


@app.route("/classroom/guidance", methods=["POST"])
def classroom_guidance():
    user = _current_user()
    if not user or user["role"] != "teacher":
        return redirect(url_for("index"))

    room = get_teacher_classroom(user["id"])
    if not room:
        return redirect(url_for("cabinet"))

    student_id = request.form.get("student_id", type=int)
    requirement_text = request.form.get("requirement_text", "")
    if student_id:
        set_student_guidance(
            classroom_code=room["code"],
            student_id=student_id,
            teacher_id=user["id"],
            requirement_text=requirement_text,
        )
        session["notice"] = "Индивидуальные требования/рекомендации для ученика обновлены."
    return redirect(url_for("cabinet"))


@app.route("/analyze", methods=["POST"])
def analyze():
    user = _current_user()
    is_guest = request.form.get("is_guest") == "1" or not user

    default_name = user["full_name"] if (user and not is_guest) else "Гость из СПб"
    student_name = request.form.get("student_name", "").strip() or default_name
    grade = request.form.get("grade") or (user.get("grade") if (user and not is_guest) else "9 класс")
    track_goal = request.form.get("track_goal") or (
        user.get("track_goal") if (user and not is_guest) else "пока изучаю варианты"
    )
    if track_goal not in TRACK_OPTIONS:
        track_goal = "пока изучаю варианты"
    open_answer = request.form.get("open_answer", "")

    scores = {"it_tech": 0, "science_med": 0, "social_hum": 0, "creative_design": 0, "econ_mgmt": 0}
    for q_id, profile_key, _ in QUESTIONS:
        raw_val = request.form.get(q_id, "3")
        try:
            val = max(1, min(5, int(raw_val)))
        except ValueError:
            val = 3
        scores[profile_key] += val

    analysis = analyze_student_profile(
        scores=scores,
        open_answer=open_answer,
        track_goal=track_goal,
    )

    owner_id = user["id"] if (user and not is_guest) else None
    room_code = (
        user.get("classroom_code") if (user and not is_guest and user["role"] == "student") else None
    )

    save_assessment(
        student_name=student_name,
        grade=f"{grade} · {track_goal}",
        open_answer=open_answer,
        analysis=analysis,
        user_id=owner_id,
        classroom_code=room_code,
    )

    session["last_result"] = analysis
    session["notice"] = "Тест пройден — отчёт сформирован."
    return redirect(url_for("result_page"))


@app.route("/clear-history", methods=["POST"])
def clear_history():
    clear_assessments()
    session["notice"] = "Журнал прохождений очищен."
    return redirect(url_for("history_page"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
