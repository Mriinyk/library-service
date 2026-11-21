from rest_framework import viewsets

from library.models import Book
from library.serializers import BookSerializer
from library.permissions import ReadOnlyOrAdminPermission


class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    permission_classes = (ReadOnlyOrAdminPermission,)
