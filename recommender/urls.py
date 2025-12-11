from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    # student
    path("student/dashboard/", views.student_dashboard, name="student_dashboard"),
    path("student/profile/", views.student_profile_view, name="student_profile"),
    path("student/courses/", views.student_courses, name="student_courses"),
    path("student/recommendations/", views.student_recommendations, name="student_recommendations"),
    # teacher
    path("teacher/dashboard/", views.teacher_dashboard, name="teacher_dashboard"),
    path("teacher/courses/", views.teacher_courses, name="teacher_courses"),
    path("teacher/courses/new/", views.teacher_course_edit, name="teacher_course_new"),
    path("teacher/courses/<str:code>/", views.teacher_course_detail, name="teacher_course_detail"),
    path("teacher/courses/<str:code>/edit/", views.teacher_course_edit, name="teacher_course_edit"),
    path("teacher/students/", views.teacher_students, name="teacher_students"),
    path("teacher/students/<int:student_id>/recommendations/", views.teacher_student_recommendations, name="teacher_student_recommendations"),
    # admin area
    path("admin/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin/model/train/", views.admin_train_model, name="admin_train_model"),
    path("admin/catalog/import/", views.admin_import_catalog, name="admin_import_catalog"),
]
