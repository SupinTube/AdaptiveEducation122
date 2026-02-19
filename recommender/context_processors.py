def role_flags(request):
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {"is_student": False, "is_teacher": False, "is_admin": False}

    is_superuser = bool(getattr(user, "is_superuser", False))
    if is_superuser:
        return {"is_student": True, "is_teacher": True, "is_admin": True}

    group_names = set(user.groups.values_list("name", flat=True))
    is_admin = "Admin" in group_names
    
    # Check for profiles to be robust against missing groups
    from .models import StudentProfile
    has_student_profile = StudentProfile.objects.filter(user=user).exists()
    
    return {
        "is_admin": is_admin,
        "is_teacher": is_admin or ("Teacher" in group_names),
        "is_student": is_admin or ("Student" in group_names) or has_student_profile,
    }

