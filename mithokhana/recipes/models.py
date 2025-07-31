from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

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
    date = models.DateField(null=True, blank=True)  # Optional
    description = models.TextField(blank=True)
    recipes = models.ManyToManyField('Recipe', related_name='festival_set')

    def __str__(self):
        return self.name

class Recipe(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True)
    image = models.ImageField(upload_to='recipes/', blank=True, null=True)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    video = models.FileField(upload_to='video/', blank=True, null=True)
    
    likes = models.ManyToManyField(User, related_name='liked_recipes', blank=True)
    
    bookmarked_by = models.ManyToManyField(User, related_name='bookmarked_recipes', blank=True)
    
    
    # festivals = models.ManyToManyField('Festival', blank=True, related_name="recipes")


    def __str__(self):
        return self.title

        
class Comment(models.Model):
    recipe = models.ForeignKey('Recipe', on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} on {self.text[:30]}"
       
class Chef(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    experience = models.PositiveIntegerField()
    specialty = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to='chef_photos/', blank=True, null=True) 

    def __str__(self):
        return self.user.get_full_name()

class Ingredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='ingredients')
    name = models.CharField(max_length=100)
    quantity = models.CharField(max_length=100)
    cook_time = models.CharField(max_length=50, blank=True)  # e.g., "10 mins", optional

    def __str__(self):
        return f"{self.name} ({self.quantity})"


