from django import forms

from goals.models import Goal, Resource


class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)


class GoalForm(forms.Form):
    title = forms.CharField(max_length=200)
    desc = forms.CharField(widget=forms.Textarea, required=False)
    status = forms.ChoiceField(choices=Goal.Status.choices)


class LearningSessionForm(forms.Form):
    goal = forms.ModelChoiceField(queryset=Goal.objects.none())
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    duration = forms.IntegerField(min_value=1, help_text="Duration in minutes")
    notes = forms.CharField(widget=forms.Textarea, required=False)
    tags = forms.CharField(required=False, help_text="Comma-separated tags")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            # Scoped the same way ResourceSerializer/LearningSessionSerializer
            # scope their `goal` field — a foreign goal id is rejected as "not
            # a valid choice", never accepted then checked after the fact.
            self.fields["goal"].queryset = Goal.objects.filter(user=user)

    def clean_tags(self):
        raw = self.cleaned_data.get("tags", "")
        return [tag.strip() for tag in raw.split(",") if tag.strip()]


class ResourceForm(forms.Form):
    goal = forms.ModelChoiceField(queryset=Goal.objects.none())
    title = forms.CharField(max_length=200)
    url = forms.URLField(max_length=500)
    type = forms.ChoiceField(choices=Resource.Type.choices)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["goal"].queryset = Goal.objects.filter(user=user)
