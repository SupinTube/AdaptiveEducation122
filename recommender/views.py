from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from .forms import StudentProfileForm, StudentCoursesForm, CourseForm
from .ml_service import recommend_for_profile, taken_courses_for_student, load_model
from .models import Course, StudentProfile, StudentCourseEnrollment, Recommendation


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
    return render(request, "home.html")


# ---------- STUDENT ----------
@login_required
@user_passes_test(is_student)
def student_dashboard(request):
    profile = ensure_student_profile(request.user)
    recos = Recommendation.objects.filter(student=profile)[:5]
    return render(request, "student/dashboard.html", {"profile": profile, "recommendations": recos})


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
    taken_codes = set(StudentCourseEnrollment.objects.filter(student=profile).values_list("course__code", flat=True))
    form = StudentCoursesForm(initial={"courses": Course.objects.filter(code__in=taken_codes)})

    if request.method == "POST":
        form = StudentCoursesForm(request.POST)
        if form.is_valid():
            new_selection = set(form.cleaned_data["courses"].values_list("code", flat=True))
            # remove old
            StudentCourseEnrollment.objects.filter(student=profile).exclude(course__code__in=new_selection).delete()
            # add new as completed
            for code in new_selection:
                course = Course.objects.get(code=code)
                StudentCourseEnrollment.objects.get_or_create(student=profile, course=course, defaults={"status": "completed"})
            messages.success(request, "Список пройдених дисциплін оновлено.")
            return redirect("student_courses")

    enrollments = StudentCourseEnrollment.objects.filter(student=profile)
    return render(request, "student/courses.html", {"form": form, "enrollments": enrollments})


@login_required
@user_passes_test(is_student)
def student_recommendations(request):
    profile = ensure_student_profile(request.user)
    taken = taken_courses_for_student(profile)
    Recommendation.objects.filter(student=profile).delete()
    try:
        recs = recommend_for_profile(profile, taken, top_k=5)
    except RuntimeError as e:
        messages.error(request, str(e))
        recs = []
    for code, score in recs:
        course = Course.objects.get(code=code)
        Recommendation.objects.create(student=profile, course=course, score=score)
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
    taken = taken_courses_for_student(student)
    Recommendation.objects.filter(student=student).delete()
    recs = recommend_for_profile(student, taken, top_k=5)
    for code, score in recs:
        course = Course.objects.get(code=code)
        Recommendation.objects.create(student=student, course=course, score=score)
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
