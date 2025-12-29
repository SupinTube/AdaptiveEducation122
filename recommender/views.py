from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from .forms import StudentProfileForm, StudentCoursesForm, CourseForm
from .ml_service import recommend_for_profile, load_model
from .models import Course, StudentProfile, StudentCourseEnrollment, Recommendation


HIGH_GRADE_THRESHOLD = 80


def _priority_tags_for_interests(interests: set[str]) -> set[str]:
    mapping = {
        "ai": {"ai", "math", "programming", "data"},
        "data": {"data", "math", "programming", "optimization"},
        "web": {"web", "programming", "ux"},
        "systems": {"systems", "programming", "architecture"},
        "security": {"security", "systems", "programming"},
        "management": {"management", "soft", "project", "quality"},
        "ux": {"ux", "web", "soft"},
        "science": {"science", "math", "data", "ai"},
    }
    tags: set[str] = set()
    for interest in interests:
        tags |= mapping.get(interest, set())
    return tags


def is_student(user):
    return user.is_superuser or user.groups.filter(name__in=["Student", "Admin"]).exists()


def is_teacher(user):
    return user.is_superuser or user.groups.filter(name__in=["Teacher", "Admin"]).exists()


def is_admin(user):
    return user.is_superuser or user.groups.filter(name="Admin").exists()


def logout_view(request):
    from django.contrib.auth import logout
    logout(request)
    return redirect("/")


def ensure_student_profile(user):
    profile, _ = StudentProfile.objects.get_or_create(user=user)
    return profile


def home(request):
    if request.user.is_authenticated:
        if is_admin(request.user):
            return redirect("admin_dashboard")
        if is_teacher(request.user):
            return redirect("teacher_dashboard")
        if is_student(request.user):
            return redirect("student_dashboard")
    return render(request, "home.html")


# ---------- STUDENT ----------
@login_required
@user_passes_test(is_student)
def student_dashboard(request):
    profile = ensure_student_profile(request.user)
    recos = Recommendation.objects.filter(student=profile)[:5]

    interests = {i.strip() for i in (profile.interests or "").split(",") if i.strip()}
    priority_tags = _priority_tags_for_interests(interests)

    mandatory_qs = Course.objects.all().order_by("semester", "code")
    enrollments = StudentCourseEnrollment.objects.filter(student=profile, status="completed").select_related("course")
    grades_by_code = {code: grade for code, grade in enrollments.values_list("course__code", "grade")}

    focus_courses = []
    for c in mandatory_qs:
        if c.kind != "обов'язкова":
            continue
        tags = {t.strip() for t in (c.tags or "").split(",") if t.strip()}
        if not (tags & priority_tags):
            continue
        grade = grades_by_code.get(c.code)
        focus_courses.append(
            {
                "course": c,
                "grade": grade,
                "needs_high_grade": grade is None or grade < HIGH_GRADE_THRESHOLD,
            }
        )

    return render(
        request,
        "student/dashboard.html",
        {
            "profile": profile,
            "recommendations": recos,
            "focus_courses": focus_courses,
            "high_grade_threshold": HIGH_GRADE_THRESHOLD,
        },
    )


@login_required
@user_passes_test(is_student)
def student_profile_view(request):
    profile = ensure_student_profile(request.user)
    if request.method == "POST":
        form = StudentProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Профіль оновлено.")
            return redirect("student_dashboard")
    else:
        form = StudentProfileForm(instance=profile)
    return render(request, "student/profile.html", {"form": form})


@login_required
@user_passes_test(is_student)
def student_courses(request):
    profile = ensure_student_profile(request.user)
    courses_qs = Course.objects.prefetch_related("prerequisites").all().order_by("semester", "code")
    prereq_map = {c.code: list(c.prerequisites.values_list("code", flat=True)) for c in courses_qs}
    enrollments_qs = StudentCourseEnrollment.objects.select_related("course").filter(student=profile)
    taken_codes = set(enrollments_qs.values_list("course__code", flat=True))
    grades_by_code = {code: grade for code, grade in enrollments_qs.values_list("course__code", "grade")}
    if request.method == "POST":
        form = StudentCoursesForm(request.POST, courses_qs=courses_qs, prereq_map=prereq_map)
        if form.is_valid():
            new_selection = {c.code for c in form.cleaned_data["courses"]}
            # remove old
            StudentCourseEnrollment.objects.filter(student=profile).exclude(course__code__in=new_selection).delete()
            # add new as completed
            for code in new_selection:
                course = Course.objects.get(code=code)
                StudentCourseEnrollment.objects.update_or_create(
                    student=profile,
                    course=course,
                    defaults={"status": "completed", "grade": form.cleaned_grades.get(code)},
                )
            messages.success(request, "Список пройдених дисциплін оновлено.")
            return redirect("student_courses")

    else:
        form = StudentCoursesForm(
            courses_qs=courses_qs,
            prereq_map=prereq_map,
            initial={"courses": sorted(taken_codes)},
        )

    if request.method == "POST":
        selected_codes = set(form.data.getlist("courses") or [])
        grade_values = {code: (form.data.get(f"grade_{code}") or "").strip() for code in selected_codes}
    else:
        selected_codes = set(form["courses"].value() or [])
        grade_values = {
            code: ("" if grades_by_code.get(code) is None else str(grades_by_code.get(code)))
            for code in selected_codes
        }

    interests = {i.strip() for i in (profile.interests or "").split(",") if i.strip()}
    priority_tags = _priority_tags_for_interests(interests)
    course_rows = []
    for c in courses_qs:
        prereqs = prereq_map.get(c.code, [])
        missing = sorted(set(prereqs) - selected_codes)
        disabled = (c.code not in selected_codes) and bool(missing)
        tags = {t.strip() for t in (c.tags or "").split(",") if t.strip()}
        is_mandatory = c.kind == "обов'язкова"
        highlight_high_grade = is_mandatory and bool(tags & priority_tags)
        course_rows.append(
            {
                "course": c,
                "prereqs": prereqs,
                "missing_prereqs": missing,
                "checked": c.code in selected_codes,
                "disabled": disabled,
                "grade": grade_values.get(c.code, ""),
                "is_mandatory": is_mandatory,
                "highlight_high_grade": highlight_high_grade,
                "high_grade_threshold": HIGH_GRADE_THRESHOLD,
            }
        )

    enrollments = StudentCourseEnrollment.objects.filter(student=profile)
    return render(request, "student/courses.html", {"form": form, "enrollments": enrollments, "course_rows": course_rows})


@login_required
@user_passes_test(is_student)
def student_recommendations(request):
    profile = ensure_student_profile(request.user)
    enrollments = StudentCourseEnrollment.objects.filter(student=profile, status="completed").select_related("course")
    taken = list(enrollments.values_list("course__code", flat=True))
    grades = {code: grade for code, grade in enrollments.values_list("course__code", "grade") if grade is not None}
    try:
        recs = recommend_for_profile(profile, taken, grades, top_k=5)
    except RuntimeError as e:
        messages.error(request, str(e))
        rec_list = Recommendation.objects.filter(student=profile)
        return render(request, "student/recommendations.html", {"recommendations": rec_list})

    codes = [code for code, _ in recs]
    courses_by_code = Course.objects.in_bulk(codes, field_name="code") if codes else {}
    new_recs = []
    for code, score in recs:
        course = courses_by_code.get(code)
        if course is None:
            continue
        new_recs.append(Recommendation(student=profile, course=course, score=score))

    with transaction.atomic():
        Recommendation.objects.filter(student=profile).delete()
        if new_recs:
            Recommendation.objects.bulk_create(new_recs)

    rec_list = Recommendation.objects.filter(student=profile)
    return render(request, "student/recommendations.html", {"recommendations": rec_list})


# ---------- TEACHER ----------
@login_required
@user_passes_test(is_teacher)
def teacher_dashboard(request):
    stats = {
        "courses": Course.objects.count(),
        "students": StudentProfile.objects.count(),
        "recommendations": Recommendation.objects.count(),
    }
    recent_recs = Recommendation.objects.select_related("student", "course")[:10]
    return render(request, "teacher/dashboard.html", {"stats": stats, "recommendations": recent_recs})


@login_required
@user_passes_test(is_teacher)
def teacher_courses(request):
    qs = Course.objects.all()
    semester = request.GET.get("semester")
    kind = request.GET.get("kind")
    block = request.GET.get("block")
    if semester:
        qs = qs.filter(semester=semester)
    if kind:
        qs = qs.filter(kind=kind)
    if block:
        qs = qs.filter(block=block)
    return render(request, "teacher/courses_list.html", {"courses": qs})


@login_required
@user_passes_test(is_teacher)
def teacher_course_detail(request, code):
    course = get_object_or_404(Course, code=code)
    return render(request, "teacher/course_detail.html", {"course": course})


@login_required
@user_passes_test(is_teacher)
def teacher_course_edit(request, code=None):
    instance = Course.objects.get(code=code) if code else None
    if request.method == "POST":
        form = CourseForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Курс збережено.")
            return redirect("teacher_courses")
    else:
        form = CourseForm(instance=instance)
    return render(request, "teacher/course_edit.html", {"form": form})


@login_required
@user_passes_test(is_teacher)
def teacher_students(request):
    students = StudentProfile.objects.select_related("user").annotate(courses_count=Count("enrollments"))
    return render(request, "teacher/students_list.html", {"students": students})


@login_required
@user_passes_test(is_teacher)
def teacher_student_recommendations(request, student_id):
    student = get_object_or_404(StudentProfile, id=student_id)
    enrollments = StudentCourseEnrollment.objects.filter(student=student, status="completed").select_related("course")
    taken = list(enrollments.values_list("course__code", flat=True))
    grades = {code: grade for code, grade in enrollments.values_list("course__code", "grade") if grade is not None}
    recs = recommend_for_profile(student, taken, grades, top_k=5)

    codes = [code for code, _ in recs]
    courses_by_code = Course.objects.in_bulk(codes, field_name="code") if codes else {}
    new_recs = []
    for code, score in recs:
        course = courses_by_code.get(code)
        if course is None:
            continue
        new_recs.append(Recommendation(student=student, course=course, score=score))

    with transaction.atomic():
        Recommendation.objects.filter(student=student).delete()
        if new_recs:
            Recommendation.objects.bulk_create(new_recs)

    rec_list = Recommendation.objects.filter(student=student)
    return render(request, "teacher/student_recommendations.html", {"student": student, "recommendations": rec_list})


# ---------- ADMIN ----------
@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    model, meta = load_model()
    model_exists = model is not None
    return render(
        request,
        "admin_area/dashboard.html",
        {"model_exists": model_exists, "meta": meta},
    )


@login_required
@user_passes_test(is_admin)
def admin_train_model(request):
    if request.method == "POST":
        call_command("train_sbm_model")
        messages.success(request, "Модель натреновано.")
        return redirect("admin_dashboard")
    return render(request, "admin_area/model_train.html")


@login_required
@user_passes_test(is_admin)
def admin_import_catalog(request):
    if request.method == "POST":
        call_command("import_courses")
        messages.success(request, "Каталог імпортовано.")
        return redirect("admin_dashboard")
    return render(request, "admin_area/catalog_import.html")
