from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("<slug:category>/", views.category_index, name="category_index"),
    path("<path:page_path>/", views.knowledge_page, name="knowledge_page"),
]
