from django.contrib import admin
from django import forms
from .models import Course, StudentProfile, StudentCourseEnrollment, Recommendation
from .forms import INTEREST_CHOICES


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "semester", "kind", "block", "ects")
    search_fields = ("code", "name", "tags")
    list_filter = ("semester", "kind", "block")
    filter_horizontal = ("prerequisites",)


class StudentProfileAdminForm(forms.ModelForm):
    interests = forms.MultipleChoiceField(
        required=False,
        choices=INTEREST_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="Інтереси",
    )

    class Meta:
        model = StudentProfile
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.interests:
            self.initial["interests"] = [i.strip() for i in self.instance.interests.split(",") if i.strip()]

    def clean_interests(self):
        vals = self.cleaned_data.get("interests", [])
        return ",".join(vals)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "year", "math_level", "prog_level", "ai_level", "soft_level", "interests")
    search_fields = ("user__username", "user__email")
    form = StudentProfileAdminForm


@admin.register(StudentCourseEnrollment)
class StudentCourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "status")
    list_filter = ("status",)


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "score", "created_at")
    list_filter = ("created_at",)
