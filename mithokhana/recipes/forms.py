from django import forms
from .models import Recipe
from django.contrib.auth.models import User
from .models import Chef

class RecipeForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = ['title', 'description', 'category']

class ChefRegistrationForm(forms.ModelForm):
    fullname = forms.CharField(max_length=100)
    email = forms.EmailField()
    username = forms.CharField(max_length=100)
    password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())
    photo = forms.ImageField(required=False)
    
    class Meta:
        model = Chef
        fields = ['experience', 'specialty', 'bio', 'photo']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm = cleaned_data.get("confirm_password")

        if password and confirm and password != confirm:
            raise forms.ValidationError("Passwords do not match")

        return cleaned_data

    def save(self, commit=True):
        # Create user
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            password=self.cleaned_data['password'],
            email=self.cleaned_data['email'],
            first_name=self.cleaned_data['fullname']
        )

        # Link Chef to user
        chef = super().save(commit=False)
        chef.user = user
        if commit:
            chef.save()
        return chef