from rest_framework.routers import DefaultRouter

from library.views import BookViewSet

app_name = "library"

router = DefaultRouter()
router.register("books", BookViewSet, basename="book")

urlpatterns = router.urls
