from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.utils import timezone
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from textwrap import wrap
import random
import calendar

from .models import Recipe, Category, Region, Comment, Festival, Chef, Ingredient
from .forms import ChefRegistrationForm
from django.utils.translation import gettext as _
from django.contrib.auth.models import User 
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def recipe_list(request):
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    region_id = request.GET.get('region', '')
    festival_id = request.GET.get('festival', '')

    recipes = Recipe.objects.all()

    if query:
        recipes = recipes.filter(title__icontains=query) | recipes.filter(description__icontains=query)
    if category_id:
        recipes = recipes.filter(category__id=category_id)
    if region_id:
        recipes = recipes.filter(region__id=region_id)
    if festival_id:
        recipes = recipes.filter(festivals__id=festival_id)
        
     # TF-IDF Ranking
    if query:
        corpus = [f"{r.title} {r.description}" for r in recipes]
        tfidf = TfidfVectorizer(stop_words='english')
        tfidf_matrix = tfidf.fit_transform(corpus)
        query_vec = tfidf.transform([query])
        similarity = cosine_similarity(query_vec, tfidf_matrix).flatten()

        # Zip recipes with scores and sort
        scored_recipes = sorted(zip(recipes, similarity), key=lambda x: x[1], reverse=True)
        recipes = [r for r, score in scored_recipes if score > 0.1]  # Threshold to filter weak matches

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
        chefs = User.objects.exclude(id=request.user.id)
    else:
        chefs = User.objects.all()
    
    
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
        'chefs': chefs
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

        if not category_id or not region_id:
            return render(request, 'recipes/upload_recipe.html', {
                'categories': Category.objects.all(),
                'regions': Region.objects.all(),
                'error': "Please select both a category and a region."
            })

        category = Category.objects.get(id=category_id)
        region = Region.objects.get(id=region_id)

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
            
        
            
        # ✅ Add ingredients
        names = request.POST.getlist('ingredient_name')
        quantities = request.POST.getlist('ingredient_quantity')
        cook_times = request.POST.getlist('ingredient_cook_time')

        for name, qty, time in zip(names,quantities, cook_times):
            if name.strip() and qty.strip():
                Ingredient.objects.create(recipe=recipe, name=name.strip(), quantity=qty.strip(), cook_time=time.strip())

        messages.success(request, _("✅ Recipe uploaded successfully!"))
        return redirect('recipe_detail', pk=recipe.pk)

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
        recipe.ingredients.all().delete()

        # ✅ Add updated ingredients
        names = request.POST.getlist('ingredient_name')
        quantities = request.POST.getlist('ingredient_quantity')
        cook_times = request.POST.getlist('ingredient_cook_time')

        for name, qty, time in zip(names, quantities, cook_times):
            if name.strip() and qty.strip():
                Ingredient.objects.create(
                    recipe=recipe,
                    name=name.strip(),
                    quantity=qty.strip(),
                    cook_time=time.strip()
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
    bookmarked = request.user.bookmarked_recipes.all()
    my_recipes = Recipe.objects.filter(created_by=user)
    chef_profile = Chef.objects.filter(user=user).first()  # if they registered as chef
    return render(request, 'recipes/profile.html', {
        'user': user,
        'bookmarked': bookmarked, 'my_recipes': my_recipes, 'chef_profile': chef_profile,
})


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


def register_chef(request):
    if request.method == 'POST':
        form = ChefRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            
            messages.success(request, "Chef account created successfully! Please log in.")
            return redirect('login')
    else:
        form = ChefRegistrationForm()
    return render(request, 'recipes/register_chef.html', {'form': form})


def download_recipe_pdf(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{recipe.title}.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    y = height - 50

    p.setFont("Helvetica-Bold", 18)
    p.drawString(50, y, f"🍽 {recipe.title}")
    y -= 30

    p.setFont("Helvetica", 12)
    p.drawString(50, y, f"Category: {recipe.category.name if recipe.category else 'N/A'}")
    y -= 20
    p.drawString(50, y, f"Region: {recipe.region.name if recipe.region else 'N/A'}")
    y -= 30

    if recipe.image:
        try:
            img_path = recipe.image.path
            img = ImageReader(img_path)
            p.drawImage(img, 50, y - 200, width=200, height=150, preserveAspectRatio=True)
            y -= 220
        except Exception as e:
            p.drawString(50, y, f"(Image load failed: {str(e)})")
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

    p.setFont("Helvetica-Oblique", 10)
    p.drawString(50, 50, "Generated by Mitho Khana 🍛")

    p.showPage()
    p.save()
    return response

def chef_profile(request, chef_id):
    
    chef_user = get_object_or_404(User, id=chef_id)
    recipes = Recipe.objects.filter(created_by=chef_user)
    chef_obj = Chef.objects.filter(user=chef_user).first()  # If you want Chef info like bio, photo

    return render(request, 'recipes/chef_profile.html', {
        'chef': chef_user,
        'chef_obj': chef_obj,  # Optional: pass this if you want bio, specialty, photo
        'recipes': recipes
    })
    
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

