# recipes/urls.py

from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from .views import register, chef_list


urlpatterns = [
    # path('', views.recipe_list, name='home'),  # homepage
    path('', views.recipe_list, name='recipe_list'),
    path('upload/', views.upload_recipe, name='upload_recipe'),
    path('recipe/<int:pk>/', views.recipe_detail, name='recipe_detail'), 
    path('recipe/<int:pk>/edit/', views.edit_recipe, name='edit_recipe'),
    path('recipe/<int:pk>/delete/', views.delete_recipe, name='delete_recipe'),
    
    path('comment/<int:pk>/delete/', views.ajax_delete_comment, name='ajax_delete_comment'),
    
    path('recipe/<int:pk>/like/', views.toggle_like, name='toggle_like'),
    
    path('recipe/<int:pk>/bookmark/', views.toggle_bookmark, name='toggle_bookmark'),
    
    path('festivals/', views.festival_calendar, name='festival_calendar'),
    
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    
    path('logout/', auth_views.LogoutView.as_view(next_page='recipe_list'), name='logout'),
    
    path('recipe/<int:pk>/add_comment/', views.add_comment_ajax, name='add_comment_ajax'),

    path('recipe/<int:pk>/download/', views.download_recipe_pdf, name='download_recipe_pdf'),
    
    # path('chef/<int:chef_id>/', views.chef_profile, name='chef_profile'),

    path('recommended/', views.recommended_recipes, name='recommended_recipes'),
    

    path('register/', register, name='register'),
 
    path('chefs/', chef_list, name='chef_list'),
   
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    
    path('profile/', views.profile, name='profile'),
    
    path('profile/<str:username>/', views.view_profile, name='view_profile'),
   
    path('profile/<str:username>/follow/', views.follow_user, name='follow_user'),
   
    path('profile/<str:username>/unfollow/', views.unfollow_user, name='unfollow_user'),
    
    path('profile/<str:username>/followers/', views.followers_list, name='followers_list'),
    
    path('profile/<str:username>/following/', views.following_list, name='following_list'),

    path('profile/<str:username>/toggle_follow/', views.toggle_follow, name='toggle_follow'),
    
    path('user/<int:user_id>/', views.user_profile, name='user_profile'),

]

