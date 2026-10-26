from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, ItemViewSet

router = DefaultRouter()
router.register("categories", CategoryViewSet)
router.register("items", ItemViewSet)

urlpatterns = router.urls
