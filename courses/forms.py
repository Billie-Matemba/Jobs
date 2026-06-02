from django import forms
from .models import Course, Module
from .file_parsing import SUPPORTED_EXTENSIONS


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        if isinstance(data, (list, tuple)):
            return [super(MultipleFileField, self).clean(item, initial) for item in data]
        return [super().clean(data, initial)]


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ["code", "name", "university_name", "country", "description"]
        widgets = {
            "code": forms.TextInput(attrs={"placeholder": "e.g. HRD101"}),
            "name": forms.TextInput(attrs={"placeholder": "e.g. Human Resource Development"}),
            "university_name": forms.TextInput(attrs={"placeholder": "e.g. University of Johannesburg"}),
            "country": forms.TextInput(attrs={"placeholder": "e.g. South Africa"}),
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Brief overview of the course"}),
        }


class ModuleForm(forms.ModelForm):
    content_files = MultipleFileField(
        required=False,
        label="Upload content files",
        help_text="Optional. Upload PDF, Word, text, or PowerPoint files to append parsed text to the module content.",
        widget=MultipleFileInput(attrs={
            "accept": ".pdf,.docx,.txt,.pptx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "multiple": True,
        }),
    )

    class Meta:
        model = Module
        fields = ["name", "university_name", "country", "content", "order"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Introduction to Excel"}),
            "university_name": forms.TextInput(attrs={"placeholder": "e.g. Johannesburg Business School"}),
            "country": forms.TextInput(attrs={"placeholder": "e.g. South Africa"}),
            "content": forms.Textarea(attrs={
                "rows": 10,
                "placeholder": "Paste the full module content, syllabus, or learning outcomes here.\n\nThe more detail you provide, the better the skill matching will be.\n\nExample:\n- Microsoft Excel: formulas, pivot tables, VLOOKUP\n- Data cleaning and validation\n- Chart creation and formatting"
            }),
            "order": forms.NumberInput(attrs={"placeholder": "1"}),
        }

    def __init__(self, *args, **kwargs):
        course = kwargs.pop("course", None)
        super().__init__(*args, **kwargs)
        self.order_fields(["name", "university_name", "country", "content", "content_files", "order"])
        if course and not self.instance.pk:
            self.fields["university_name"].initial = course.university_name
            self.fields["country"].initial = course.country
        self.fields["content"].required = False
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        self.fields["content_files"].help_text = f"Optional. Supported files: {supported}."

    def clean(self):
        cleaned_data = super().clean()
        content = (cleaned_data.get("content") or "").strip()
        files = cleaned_data.get("content_files") or []
        existing_content = getattr(self.instance, "content", "") if self.instance else ""
        if not content and not files and not existing_content:
            raise forms.ValidationError("Paste module content or upload at least one supported file.")
        return cleaned_data
