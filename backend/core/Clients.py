# core/clients.py

from .exchange_fetcher import ExchangeFetcher

# یک نمونه واحد و دائمی از Fetcher که در کل برنامه به اشتراک گذاشته می‌شود
exchange_fetcher = ExchangeFetcher()

# در آینده می‌توانیم اتصالات دیگر (مثلاً به دیتابیس Redis) را نیز در اینجا مدیریت کنیم.
