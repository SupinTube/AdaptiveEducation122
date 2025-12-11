from django.db import models
from django.contrib.auth.models import User


class Course(models.Model):
    KIND_CHOICES = [
        ("обов'язкова", "Обов'язкова"),
        ("вибіркова", "Вибіркова"),
    ]
    BLOCK_CHOICES = [
        ("загальна", "Загальна"),
        ("професійна", "Професійна"),
        ("вільний вибір", "Вільний вибір"),
    ]

    code = models.CharField(primary_key=True, max_length=20)
    name = models.CharField(max_length=255)
    ects = models.FloatField()
    semester = models.IntegerField()
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    block = models.CharField(max_length=20, choices=BLOCK_CHOICES)
    req_math = models.IntegerField(default=0)
    req_prog = models.IntegerField(default=0)
    req_ai = models.IntegerField(default=0)
    req_soft = models.IntegerField(default=0)
    prerequisites = models.ManyToManyField('self', symmetrical=False, blank=True)
    tags = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return f"{self.code} - {self.name}"


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    year = models.IntegerField(default=1)
    math_level = models.FloatField(default=0.0)
    prog_level = models.FloatField(default=0.0)
    ai_level = models.FloatField(default=0.0)
    soft_level = models.FloatField(default=0.0)
    interests = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class StudentCourseEnrollment(models.Model):
    STATUS_CHOICES = [
        ("completed", "Завершено"),
        ("in_progress", "В процесі"),
    ]
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="completed")

    class Meta:
        unique_together = ("student", "course")

    def __str__(self):
        return f"{self.student} -> {self.course} ({self.status})"


class Recommendation(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="recommendations")
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student}: {self.course} ({self.score:.3f})"

# Create your models here.
