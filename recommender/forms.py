from django import forms
from .models import StudentProfile, Course, StudentCourseEnrollment


INTEREST_CHOICES = [
    ("ai", "AI"),
    ("data", "Data"),
    ("web", "Web"),
    ("systems", "Systems"),
    ("security", "Security"),
    ("management", "Management"),
    ("ux", "UX"),
    ("science", "Science"),
]


class StudentProfileForm(forms.ModelForm):
    interests = forms.MultipleChoiceField(
        required=False,
        choices=INTEREST_CHOICES,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = StudentProfile
        fields = ["year", "math_level", "prog_level", "ai_level", "soft_level", "interests"]
        widgets = {
            "year": forms.NumberInput(attrs={"min": 1, "max": 4, "class": "form-control"}),
            "math_level": forms.NumberInput(attrs={"step": 0.1, "min": 0, "max": 1, "class": "form-control"}),
            "prog_level": forms.NumberInput(attrs={"step": 0.1, "min": 0, "max": 1, "class": "form-control"}),
            "ai_level": forms.NumberInput(attrs={"step": 0.1, "min": 0, "max": 1, "class": "form-control"}),
            "soft_level": forms.NumberInput(attrs={"step": 0.1, "min": 0, "max": 1, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.interests:
            self.initial["interests"] = [i.strip() for i in self.instance.interests.split(",") if i.strip()]

    def clean_interests(self):
        vals = self.cleaned_data.get("interests", [])
        return ",".join(vals)


class StudentCoursesForm(forms.Form):
    courses = forms.ModelMultipleChoiceField(
        queryset=Course.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, courses_qs=None, prereq_map=None, **kwargs):
        self.prereq_map = prereq_map or {}
        super().__init__(*args, **kwargs)
        self.fields["courses"].queryset = courses_qs if courses_qs is not None else Course.objects.all()

    def clean_courses(self):
        courses = self.cleaned_data.get("courses") or []
        selected_codes = {c.code for c in courses}

        invalid = []
        for code in sorted(selected_codes):
            prereqs = set(self.prereq_map.get(code, []))
            missing = sorted(prereqs - selected_codes)
            if missing:
                invalid.append((code, missing))

        if invalid:
            parts = [f"{code} (потрібно: {', '.join(missing)})" for code, missing in invalid]
            raise forms.ValidationError(
                "Неможливо обрати дисципліни без пререквізитів: " + "; ".join(parts)
            )

        return courses


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            "code",
            "name",
            "ects",
            "semester",
            "kind",
            "block",
            "req_math",
            "req_prog",
            "req_ai",
            "req_soft",
            "prerequisites",
            "tags",
        ]
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "ects": forms.NumberInput(attrs={"step": 0.5, "class": "form-control"}),
            "semester": forms.NumberInput(attrs={"class": "form-control"}),
            "kind": forms.Select(attrs={"class": "form-control"}),
            "block": forms.Select(attrs={"class": "form-control"}),
            "req_math": forms.NumberInput(attrs={"class": "form-control"}),
            "req_prog": forms.NumberInput(attrs={"class": "form-control"}),
            "req_ai": forms.NumberInput(attrs={"class": "form-control"}),
            "req_soft": forms.NumberInput(attrs={"class": "form-control"}),
            "prerequisites": forms.SelectMultiple(attrs={"class": "form-control"}),
            "tags": forms.TextInput(attrs={"class": "form-control"}),
        }
