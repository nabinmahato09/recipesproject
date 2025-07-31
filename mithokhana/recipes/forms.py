from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Recipe, Profile
from django.contrib.auth.models import User

from django.core.exceptions import ValidationError

class RecipeForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = ['title', 'description', 'category']

 

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

class ProfileForm(forms.ModelForm):
    is_chef = forms.BooleanField(required=False, label="I am a Chef")

    class Meta:
        model = Profile
        fields = ['bio', 'photo', 'is_chef', 'experience', 'specialty']
        
class EditProfileForm(forms.ModelForm):
    fullname = forms.CharField(max_length=100, required=False)
    is_chef = forms.BooleanField(required=False, label="I am a Chef")

    class Meta:
        model = Profile
        fields = ['photo', 'bio', 'experience', 'specialty', 'is_chef']

    def save(self, user, commit=True):
        profile = super().save(commit=False)
        user.first_name = self.cleaned_data.get('fullname')
        if commit:
            user.save()
            profile.user = user
            profile.save()
        return profile