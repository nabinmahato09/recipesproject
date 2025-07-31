from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.text import slugify
from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from textwrap import wrap
import random
import calendar
from pathlib import Path
from django.contrib.auth import login

from .models import Recipe, Category, Region, Comment, Festival, Ingredient, Profile
import qrcode
import io
from .forms import UserRegisterForm, ProfileForm, EditProfileForm
from django.utils.translation import gettext as _
from django.contrib.auth.models import User 
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity



def recipe_list(request):
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    region_id = request.GET.get('region', '')
    festival_id = request.GET.get('festival', '')
   
    #  Start with all recipes
    recipes = Recipe.objects.all()
    
    # Filter by title/description for basic search
    if query:
        recipes = recipes.filter(title__icontains=query) | recipes.filter(description__icontains=query)
        
    # Apply filters
    if category_id:
        recipes = recipes.filter(category__id=category_id)
    if region_id:
        recipes = recipes.filter(region__id=region_id)
    if festival_id:
        recipes = recipes.filter(festivals__id=festival_id)
        
        
     # TF-IDF Ranking (only if query and recipes found)
    if query and recipes.exists():
        corpus = [f"{r.title} {r.description}" for r in recipes]

        if corpus and any(len(doc.strip()) > 0 for doc in corpus):
            try:
                tfidf = TfidfVectorizer(stop_words='english')
                tfidf_matrix = tfidf.fit_transform(corpus)
                query_vec = tfidf.transform([query])
                similarity = cosine_similarity(query_vec, tfidf_matrix).flatten()

                scored_recipes = sorted(zip(recipes, similarity), key=lambda x: x[1], reverse=True)
                recipes = [r for r, score in scored_recipes if score > 0.1]

                if not recipes:
                    messages.warning(request, "No relevant recipes found for your search.")
            except ValueError:
                recipes = []
                messages.warning(request, "Search input is too generic or invalid.")
        else:
            recipes = []
            messages.warning(request, "No searchable content available in recipes.")
    elif query and not recipes.exists():
        messages.warning(request, "No recipes match your search or filters.")

    # static data
    categories = Category.objects.all()
    regions = Region.objects.all()
    festivals = Festival.objects.all()

    popular_recipes = list(
        Recipe.objects.annotate(like_count=Count('likes')).order_by('-like_count')[:10]
    )
    random.shuffle(popular_recipes)
    popular_recipes = popular_recipes[:3]

    # Exclude logged-in user if authenticated
    if request.user.is_authenticated:
        users = User.objects.exclude(id=request.user.id)
    else:
        users = User.objects.filter(profile__is_chef=True)
    
    
    return render(request, 'recipes/recipe_list.html', {
        'recipes': recipes,
        'query': query,
        'categories': categories,
        'regions': regions,
        'festivals': festivals,
        'selected_category': category_id,
        'selected_region': region_id,
        'selected_festival': festival_id,
        'popular_recipes': popular_recipes,
        'users': users,
    })


@login_required
def upload_recipe(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        category_id = request.POST.get('category')
        region_id = request.POST.get('region')
        image = request.FILES.get('image')
        video = request.FILES.get('video')
        festival_ids = request.POST.getlist('festivals')

        # Check if category and region selected
        if not category_id or not region_id:
            return render(request, 'recipes/upload_recipe.html', {
                'categories': Category.objects.all(),
                'regions': Region.objects.all(),
                'festivals': Festival.objects.all(),
                'error': "Please select both a category and a region."
            })

        # ✅ Validate image file type
        if image:
            image_type = image.content_type
            image_ext = Path(image.name).suffix.lower()
            if image_type not in ['image/jpeg', 'image/png', 'image/gif'] or image_ext not in ['.jpg', '.jpeg', '.png', '.gif']:
                return render(request, 'recipes/upload_recipe.html', {
                    'categories': Category.objects.all(),
                    'regions': Region.objects.all(),
                    'festivals': Festival.objects.all(),
                    'error': "❌ Invalid image format. Please upload JPEG, PNG, or GIF only."
                })

        # ✅ Validate video file type
        if video:
            video_type = video.content_type
            video_ext = Path(video.name).suffix.lower()
            if video_type not in ['video/mp4', 'video/webm', 'video/ogg'] or video_ext not in ['.mp4', '.webm', '.ogg']:
                return render(request, 'recipes/upload_recipe.html', {
                    'categories': Category.objects.all(),
                    'regions': Region.objects.all(),
                    'festivals': Festival.objects.all(),
                    'error': "❌ Invalid video format. Please upload MP4, WebM, or OGG only."
                })

        category = Category.objects.get(id=category_id)
        region = Region.objects.get(id=region_id)

        # ✅ Create Recipe
        recipe = Recipe.objects.create(
            title=title,
            description=description,
            category=category,
            region=region,
            image=image,
            video=video,
            created_by=request.user
        )

        if festival_ids:
            recipe.festivals.set(festival_ids)

        # ✅ Add Ingredients
        names = request.POST.getlist('ingredient_name')
        quantities = request.POST.getlist('ingredient_quantity')
        cook_times = request.POST.getlist('ingredient_cook_time')

        for name, qty, time in zip(names, quantities, cook_times):
            if name.strip():
                Ingredient.objects.create(
                    recipe=recipe,
                    name=name.strip(),
                    quantity=qty.strip(),
                    cook_time=time.strip()
                )

        messages.success(request, _("✅ Recipe uploaded successfully!"))
        return redirect('recipe_detail', pk=recipe.pk)

    # GET request — show form
    return render(request, 'recipes/upload_recipe.html', {
        'categories': Category.objects.all(),
        'regions': Region.objects.all(),
        'festivals': Festival.objects.all()
    })


def recipe_detail(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    comments = recipe.comments.filter(parent=None).order_by('-created_at')

    if request.method == 'POST':
        text = request.POST.get('text')
        parent_id = request.POST.get('parent_id')
        parent_comment = Comment.objects.get(id=parent_id) if parent_id else None

        if text:
            Comment.objects.create(recipe=recipe, user=request.user, text=text, parent=parent_comment)
            return redirect('recipe_detail', pk=pk)

    return render(request, 'recipes/recipe_detail.html', {
        'recipe': recipe,
        'comments': comments,
        'user': request.user,
    })


@login_required
def edit_recipe(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)

    if request.user != recipe.created_by:
        return redirect('recipe_detail', pk=pk)

    if request.method == 'POST':
        recipe.title = request.POST.get('title')
        recipe.description = request.POST.get('description')
        recipe.category = Category.objects.get(id=request.POST.get('category'))
        recipe.region = Region.objects.get(id=request.POST.get('region'))

        if 'image' in request.FILES:
            recipe.image = request.FILES['image']
        if 'video' in request.FILES:
            recipe.video = request.FILES['video']

        recipe.save()

        # Delete old ingredients
        recipe.ingredients.all().delete()

        # Get updated ingredients
        names = request.POST.getlist('ingredient_name[]')
        quantities = request.POST.getlist('ingredient_quantity[]')
        cook_times = request.POST.getlist('ingredient_cook_time[]')
        notes = request.POST.getlist('ingredient_note[]') if 'ingredient_note[]' in request.POST else [''] * len(names)

        for name, quantity, cook_time, note in zip(names, quantities, cook_times, notes):
            if name.strip():  # avoid saving empty ingredient rows
                Ingredient.objects.create(
                    recipe=recipe,
                    name=name,
                    quantity=quantity,
                    cook_time=cook_time,
                    note=note
                )

        messages.success(request, _("✅ Recipe updated successfully!"))
        return redirect('recipe_detail', pk=pk)

    return render(request, 'recipes/edit_recipe.html', {
        'recipe': recipe,
        'categories': Category.objects.all(),
        'regions': Region.objects.all(),
    })

@login_required
def delete_recipe(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    if request.user != recipe.created_by:
        return HttpResponseForbidden("You are not allowed to delete this recipe.")

    if request.method == 'POST':
        recipe.delete()
        return redirect('recipe_list')

    return render(request, 'recipes/confirm_delete.html', {'recipe': recipe})


@require_POST
@login_required
def ajax_delete_comment(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    if comment.user != request.user:
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    comment.delete()
    return JsonResponse({'success': True})


@require_POST
@login_required
def toggle_like(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    if request.user in recipe.likes.all():
        recipe.likes.remove(request.user)
        liked = False
    else:
        recipe.likes.add(request.user)
        liked = True
    return JsonResponse({'liked': liked, 'likes_count': recipe.likes.count()})


@require_POST
@login_required
def toggle_bookmark(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    if request.user in recipe.bookmarked_by.all():
        recipe.bookmarked_by.remove(request.user)
        bookmarked = False
    else:
        recipe.bookmarked_by.add(request.user)
        bookmarked = True
    return JsonResponse({'bookmarked': bookmarked})


@login_required
def profile(request):
    user = request.user
    profile = user.profile  # Access profile via OneToOneField

    bookmarked = user.bookmarked_recipes.all()
    my_recipes = Recipe.objects.filter(created_by=user)
    
    context = {
        'user': user,
        'profile': profile,
        'bookmarked': bookmarked,
        'my_recipes': my_recipes,
        'is_own_profile': True,
        'is_following': False,
        'followers_count': profile.total_followers(),
        'following_count': profile.total_following(),
    }

    return render(request, 'recipes/profile.html', context)



def festival_calendar(request):
    month = request.GET.get('month')
    festivals = Festival.objects.all()
    
    if month:
        festivals = festivals.filter(date__month=list(calendar.month_name).index(month))
    
    context = {
        'festivals': festivals,
        'months': list(calendar.month_name)[1:],  # ['January', ..., 'December']
        'selected_month': month,
    }
    return render(request, 'recipes/festival_calendar.html', context)


@require_POST
@login_required
def add_comment_ajax(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    text = request.POST.get('text')
    parent_id = request.POST.get('parent_id')
    parent = Comment.objects.get(pk=parent_id) if parent_id else None

    if text:
        comment = Comment.objects.create(
            recipe=recipe,
            user=request.user,
            text=text,
            parent=parent,
            created_at=timezone.now()
        )
        return JsonResponse({
            'username': comment.user.username,
            'text': comment.text,
            'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M'),
            'id': comment.id,
            'parent_id': parent_id
        })

    return JsonResponse({'error': 'Text is required'}, status=400)



@login_required
def download_recipe_pdf(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)

    # ✅ Increment download count
    recipe.download_count += 1
    recipe.save(update_fields=['download_count'])

    # ✅ Prepare response with a safe filename
    filename = f"{slugify(recipe.title)}.pdf"
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # ✅ Initialize canvas
    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    y = height - 50

    # ✅ Title
    p.setFont("Helvetica-Bold", 18)
    p.drawString(50, y, f"🍽 {recipe.title}")
    y -= 30

    # ✅ Metadata
    p.setFont("Helvetica", 12)
    p.drawString(50, y, f"Category: {recipe.category.name if recipe.category else 'N/A'}")
    y -= 20
    p.drawString(50, y, f"Region: {recipe.region.name if recipe.region else 'N/A'}")
    y -= 20
    p.drawString(50, y, f"Cook Time: {recipe.cook_time} minutes")
    y -= 20
    p.drawString(50, y, f"Uploaded by: {recipe.created_by.username}")
    y -= 30

    # ✅ Image (if exists)
    if recipe.image:
        try:
            img = ImageReader(recipe.image.path)
            p.drawImage(img, 50, y - 200, width=200, height=150, preserveAspectRatio=True)
            y -= 220
        except Exception as e:
            p.setFont("Helvetica-Oblique", 10)
            p.drawString(50, y, f"(Image failed to load: {str(e)})")
            y -= 20

    # ✅ Ingredients
    ingredients = recipe.ingredients.all()
    if ingredients:
        p.setFont("Helvetica-Bold", 13)
        p.drawString(50, y, "🧂 Ingredients:")
        y -= 20
        p.setFont("Helvetica", 11)
        for ing in ingredients:
            line = f"- {ing.quantity} {ing.name}".strip()
            p.drawString(60, y, line)
            y -= 15
            if y < 100:
                p.showPage()
                y = height - 50
                p.setFont("Helvetica", 11)


    # ✅ Description
    y -= 10
    p.setFont("Helvetica-Bold", 13)
    p.drawString(50, y, "📖 Description:")
    y -= 20
    p.setFont("Helvetica", 11)
    desc_lines = wrap(recipe.description or "", 90)
    for line in desc_lines:
        p.drawString(50, y, line)
        y -= 15
        if y < 100:
            p.showPage()
            y = height - 50
            p.setFont("Helvetica", 11)

    # ✅ QR Code linking to the online recipe
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "🔗 View this recipe online:")
    y -= 20
    recipe_url = f"{settings.SITE_DOMAIN}/recipe/{recipe.pk}/"  # SITE_DOMAIN must be defined in settings

    qr = qrcode.make(recipe_url)
    qr_io = io.BytesIO()
    qr.save(qr_io, format='PNG')
    qr_io.seek(0)
    qr_image = ImageReader(qr_io)
    p.drawImage(qr_image, 50, y - 100, width=100, height=100)
    y -= 120

    # ✅ Footer
    p.setFont("Helvetica-Oblique", 10)
    p.drawString(50, 50, "Downloaded from Mitho Khana 🍛")

    # ✅ Finalize and return
    p.showPage()
    p.save()
    return response

# def chef_profile(request, chef_id):
#     user = get_object_or_404(User, id=chef_id)
    
    
#     try:
#         profile = Profile.objects.get(user=user)
#     except Profile.DoesNotExist:
#         return render(request, 'recipes/not_a_chef.html')  # or a custom 404 fallback

#     if not profile.is_chef:
#         messages.warning(request, "That user is not a registered chef.")
#         return redirect('recipe_list')
#     # if not profile.is_chef:
#     #     return render(request, 'recipes/not_a_chef.html')  # Optional fallback
    
    


#     recipes = Recipe.objects.filter(created_by=user)

#     return render(request, 'recipes/chef_profile.html', {
#         'chef': user,
#         'profile': profile,
#         'recipes': recipes
#     })
    
@login_required
def recommended_recipes(request):
    user = request.user

    # Get the recipes this user already liked
    liked_by_user = user.liked_recipes.all()

    # Find other users who liked the same recipes
    similar_users = User.objects.filter(liked_recipes__in=liked_by_user).exclude(id=user.id)

    # Get recipes liked by similar users, but not already liked by this user
    recommended = Recipe.objects.filter(
        likes__in=similar_users
    ).exclude(id__in=liked_by_user.values_list('id', flat=True)).annotate(
        score=Count('likes')
    ).order_by('-score')[:10]  # Limit to 10

    return render(request, 'recipes/recommended.html', {
        'recommended_recipes': recommended
    })
    

def register(request):
    if request.method == 'POST':
        user_form = UserRegisterForm(request.POST)
        profile_form = ProfileForm(request.POST, request.FILES)

        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()

            # ✅ Access the profile created automatically by signal
            profile = user.profile

            # ✅ Update it with form data
            profile_data = profile_form.cleaned_data
            profile.bio = profile_data.get('bio')
            profile.photo = request.FILES.get('photo')
            profile.is_chef = profile_data.get('is_chef')
            profile.experience = profile_data.get('experience')
            profile.specialty = profile_data.get('specialty')
            profile.save()

            login(request, user)
            return redirect('recipe_list')
    else:
        user_form = UserRegisterForm()
        profile_form = ProfileForm()

    return render(request, 'registration/register.html', {
        'user_form': user_form,
        'profile_form': profile_form,
    })
    
from django.contrib.auth.models import User

def chef_list(request):
    chefs = User.objects.filter(profile__is_chef=True)
    return render(request, 'recipes/chef_list.html', {'chefs': chefs})

@login_required
def edit_profile(request):
    profile = request.user.profile
    if request.method == 'POST':
        form = EditProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save(user=request.user)
            return redirect('profile')
    else:
        form = EditProfileForm(instance=profile, initial={'fullname': request.user.first_name})

    return render(request, 'recipes/edit_profile.html', {'form': form})


@login_required
def view_profile(request, username):
    user_obj = get_object_or_404(User, username=username)
    profile = user_obj.profile
    my_recipes = Recipe.objects.filter(created_by=user_obj)
    bookmarked = request.user.bookmarked_recipes.all()

    is_own_profile = (request.user == user_obj)

    is_following = False
    if not is_own_profile:
        is_following = profile.followers.filter(id=request.user.id).exists()

    context = {
        'user': user_obj,
        'profile': profile,
        'my_recipes': my_recipes,
        'bookmarked': bookmarked,
        'is_own_profile': is_own_profile,
        'is_following': is_following,
        'followers_count': profile.total_followers(),
        'following_count': profile.total_following(),
        'show_chef_badge': profile.is_chef,  # New flag for template
    }

    return render(request, 'recipes/profile.html', context)


@login_required
def follow_user(request, username):
    profile = get_object_or_404(Profile, user__username=username)
    if request.user != profile.user and request.user not in profile.followers.all():
        profile.followers.add(request.user)
    return redirect('view_profile', username=username)

@login_required
def unfollow_user(request, username):
    profile = get_object_or_404(Profile, user__username=username)
    if request.user != profile.user and request.user in profile.followers.all():
        profile.followers.remove(request.user)
    return redirect('view_profile', username=username)

@login_required
def followers_list(request, username):
    user_obj = get_object_or_404(User, username=username)
    followers = user_obj.profile.followers.all()
    return render(request, 'recipes/followers_list.html', {
        'user_obj': user_obj,
        'followers': followers,
    })

@login_required
def following_list(request, username):
    user_obj = get_object_or_404(User, username=username)
    following_profiles = user_obj.following.all() 
    following_users = User.objects.filter(profile__in=following_profiles)  # assuming following is on Profile model

    return render(request, 'recipes/following_list.html', {
        'user_obj': user_obj,
        'following_users': following_users,
    })
@require_POST
@login_required
def toggle_follow(request, username):
    if request.user.username == username:
        return JsonResponse({'error': "You cannot follow yourself."}, status=400)

    target_user = get_object_or_404(User, username=username)
    target_profile = get_object_or_404(Profile, user=target_user)

    user_profile = request.user.profile

    if target_profile.followers.filter(id=request.user.id).exists():
        target_profile.followers.remove(request.user)
        following = False
    else:
        target_profile.followers.add(request.user)
        following = True

    return JsonResponse({
        'following': following,
        'followers_count': target_profile.total_followers(),  # optional
    })
    
@login_required
def chef_profile_view(request, username):
    chef = get_object_or_404(User, username=username)
    profile = getattr(chef, 'profile', None)
    recipes = Recipe.objects.filter(author=chef)

    is_following = False
    if profile and request.user.is_authenticated and request.user != chef:
        is_following = profile.followers.filter(id=request.user.id).exists()

    return render(request, 'chef_profile.html', {
        'chef': chef,
        'profile': profile,
        'recipes': recipes,
        'is_following': is_following,
    })
    
def user_profile(request, user_id):
    profile_user = get_object_or_404(User, id=user_id)
    profile = getattr(profile_user, 'profile', None)
    recipes = Recipe.objects.filter(created_by=profile_user)

    is_following = False
    if request.user.is_authenticated:
        is_following = request.user.profile in profile.followers.all() if profile else False

    context = {
        'profile_user': profile_user,
        'profile': profile,
        'recipes': recipes,
        'is_following': is_following,
    }
    return render(request, 'recipes/user_profile.html', context)