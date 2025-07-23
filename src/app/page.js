'use client';
import { useState, useEffect } from 'react';

// تابع فرمت اعداد بزرگ (بدون تغییر)
const formatLargeNumber = (num) => {
  if (!num) return 'N/A';
  if (num >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
  if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
  return `$${(num / 1e6).toFixed(2)}M`;
};

// تابع فرمت قیمت (اصلاح شده برای دقت بیشتر)
const formatPrice = (price) => {
    if (price === null || price === undefined) return 'N/A';
    const options = {
        minimumFractionDigits: 2,
        // اگر قیمت کمتر از ۱۰ دلار بود، ۴ رقم اعشار نشان بده
        maximumFractionDigits: price < 10 ? 4 : 2,
    };
    return price.toLocaleString('en-US', options);
};

// ... (بقیه کامپوننت‌های صفحه مانند SystemStatus, MarketOverview, PriceTicker و Home بدون تغییر) ...
// (شما فقط کافیست کل فایل را جایگزین کنید تا این تابع جدید اعمال شود)
function SystemStatus() { /* ... کد قبلی ... */ }
function MarketOverview() { /* ... کد قبلی ... */ }
function PriceTicker() { /* ... کد قبلی ... */ }
export default function Home() { /* ... کد قبلی ... */ }
