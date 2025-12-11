# Study Reco — система рекомендацій навчальних траєкторій

Проєкт на Django, що на основі навчального каталогу й профілів студентів формує рекомендації вибіркових дисциплін за допомогою простої байєсівської моделі (SBM, Multinomial Naive Bayes).

## Стек
- Python 3, Django 5
- SQLite (за замовчуванням)
- Bootstrap-шаблони (server-rendered)
- ML: модуль `build_sbm_project.py` (кодування ознак, тренування SBM, joblib-модель)

## Структура
- `study_reco/` — налаштування Django.
- `recommender/` — додаток із моделями, формами, в’ю, URL, ML-сервісом, менеджмент-командами.
- `templates/` — базові та рольові шаблони (student/teacher/admin).
- `data/` — вихідні дані: `courses_catalog.csv`, `Дисциплины свободного выбора.xlsx`, `students_current.csv`, `student_enrollments.csv` тощо.
- `var/sbm_model.joblib` — кеш збереженої моделі (шлях конфігурований у `settings.py`).

## Ролі та доступ
- **Admin** — усе, включно з імпортом каталогу, тренуванням моделі, доступом до студентської й викладацької зон.
- **Teacher** — перегляд/редагування курсів, студентів, запуск рекомендацій для студентів.
- **Student** — редагування профілю, відмітка пройдених курсів, отримання рекомендацій.

Перевірки доступу реалізовані через групи Django (`Admin`, `Teacher`, `Student`) та `user_passes_test`.

## Моделі
- `Course`: code, name, ects, semester, kind (обов’язкова/вибіркова), block, req_math/req_prog/req_ai/req_soft, prerequisites (M2M), tags.
- `StudentProfile`: OneToOne до `User`, year, math/prog/ai/soft levels [0–1], interests (comma-separated ai,data,web,systems,security,management,ux,science).
- `StudentCourseEnrollment`: зв’язок студент–курс, статус (completed/in_progress).
- `Recommendation`: збережені рекомендації з score.

## ML
- Кодування та тренування: функції з `build_sbm_project.py` (encode_features, train_sbm_model тощо).
- Сервіс `recommender/ml_service.py`:
  - `load_model()` — читає joblib із `settings.SBM_MODEL_PATH`.
  - `recommend_for_profile(student_profile, taken_codes)` — повертає [(course_code, score)] для вибіркових дисциплін із урахуванням пререквізитів.
  - Використовує дані з БД `Course`/`StudentProfile`.
- Модель зберігається у `var/sbm_model.joblib`; метадані — разом у joblib.

## Менеджмент-команди
- `python manage.py import_courses` — імпорт курсів із `data/courses_catalog.csv` та XLSX (вільний вибір) у БД.
- `python manage.py train_sbm_model` — тренує SBM на синтетичних/збережених студентських даних із `data/` та зберігає у `var/sbm_model.joblib`.

## Установка та запуск
1. Встановити залежності (Django вже інсталювався в ході розробки): `pip install django joblib pandas scikit-learn pdfplumber PyPDF2 openpyxl` (за потреби).
2. Міграції: `python manage.py migrate`.
3. Створити суперкористувача: `python manage.py createsuperuser`.
4. Створити групи `Admin`, `Teacher`, `Student` через `/admin/` і призначити користувачів.
5. Імпорт каталогу: `python manage.py import_courses`.
6. (За потреби) Імпорт студентів з CSV — вручну через Django shell або окрему команду; у `data/` є `students_current.csv` та `student_enrollments.csv`.
7. Тренування моделі: `python manage.py train_sbm_model`.
8. Запуск серверу: `python manage.py runserver`, далі http://127.0.0.1:8000/.

## Використання
- Вхід: `/login/`; вихід: `/logout/` (GET, редірект на головну).
- Студент: `/student/dashboard/`, профіль `/student/profile/`, курси `/student/courses/`, рекомендації `/student/recommendations/`.
- Викладач: `/teacher/dashboard/`, курси `/teacher/courses/`, деталі/редагування курсу, студенти `/teacher/students/`, рекомендації для студента `/teacher/students/<id>/recommendations/`.
- Адмін: `/admin/dashboard/` (статус моделі, швидкі дії), `/admin/model/train/`, `/admin/catalog/import/` + стандартний Django admin `/admin/`.

## Дані та синтетика
- Якщо файли студентів/зарахувань відсутні, `build_sbm_project.py` (через `ensure_student_data`) згенерує синтетичних студентів і збереже в `data/`.
- Вибіркові назви курсу підтягуються з `data/Дисциплины свободного выбора.xlsx`.

## Примітки
- Усі коментарі/тексти коду — українською.
- Щоб перевчити модель після зміни каталогу/студентів: видаліть `var/sbm_model.joblib` і виконайте `python manage.py train_sbm_model`.
- Для кастомних інтересів оновіть `INTEREST_CHOICES` у `recommender/forms.py` (впливає й на admin форму).
