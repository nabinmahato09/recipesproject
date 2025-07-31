from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

# -------------------------------
# Core Models
# -------------------------------

class Region(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Festival(models.Model):
    name = models.CharField(max_length=100)
    date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    recipes = models.ManyToManyField('Recipe', related_name='festival_set', blank=True)

    def __str__(self):
        return self.name

class Recipe(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True)
    image = models.ImageField(upload_to='recipes/', blank=True, null=True)
    video = models.FileField(upload_to='video/', blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    likes = models.ManyToManyField(User, related_name='liked_recipes', blank=True)
    bookmarked_by = models.ManyToManyField(User, related_name='bookmarked_recipes', blank=True)
    download_count = models.PositiveIntegerField(default=0)
    cook_time = models.PositiveIntegerField(default=0, help_text="Time in minutes")


    def __str__(self):
        return self.title

# -------------------------------
# Supporting Models
# -------------------------------

class Comment(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} on {self.text[:30]}"

class Ingredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='ingredients')
    name = models.CharField(max_length=100)
    quantity = models.CharField(max_length=100, blank=True)
    cook_time = models.CharField(max_length=50, blank=True)
    note = models.CharField(max_length=150, blank=True)

    def __str__(self):
        return f"{self.name} ({self.quantity})"

# -------------------------------
# User Profile
# -------------------------------

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)
    
    # Optional Chef Info
    is_chef = models.BooleanField(default=False)
    experience = models.PositiveIntegerField(blank=True, null=True)
    specialty = models.CharField(max_length=100, blank=True)
    
    #  Followers: users who follow this profile
    followers = models.ManyToManyField(User, related_name='following', blank=True)

    def is_verified_chef(self):
        return self.is_chef and self.experience and self.specialty
    
    def total_followers(self):
        return self.followers.count()

    def total_following(self):
        return self.user.following.count()  # reverse lookup

    def __str__(self):
        return self.user.username

# Automatically create profile when user is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
        
def is_verified_chef(self):
    return self.is_chef and self.experience and self.specialty

