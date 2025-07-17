from django.contrib import admin
from .models import Recipe, Region, Category, Comment, Festival, Ingredient

class FestivalAdmin(admin.ModelAdmin):
    list_display = ('name', 'date')
    search_fields = ('name',)
    filter_horizontal = ('recipes',)  # For easy selection in ManyToMany
class IngredientInline(admin.TabularInline):
    model = Ingredient
    extra = 1

class RecipeAdmin(admin.ModelAdmin):
    inlines = [IngredientInline]

admin.site.register(Ingredient)
# admin.site.unregister(Recipe)
admin.site.register(Recipe, RecipeAdmin)
admin.site.register(Region)
admin.site.register(Category)
admin.site.register(Comment)
admin.site.register(Festival)



