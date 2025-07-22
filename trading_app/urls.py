from django.http import HttpResponse

# ما یک ویو ساده را مستقیماً اینجا تعریف می‌کنیم
def test_view(request):
    return HttpResponse("<h1>Server is working! URL routing is OK.</h1>")

# و آن را به آدرس اصلی سایت متصل می‌کنیم
urlpatterns = [
    path('', test_view),
]
