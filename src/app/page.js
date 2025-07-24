'use client';
import { useState, useEffect, useRef } from 'react';

// (توابع کمکی و کامپوننت‌های SystemStatus و MarketOverview بدون تغییر)
const formatLargeNumber = (num) => { /* ... */ };
const formatPrice = (price) => { /* ... */ };
function SystemStatus() { /* ... */ }
function MarketOverview() { /* ... */ }

// ===================================================================
// کامپوننت ۳: تیکر قیمت (بازنویسی نهایی)
// ===================================================================
function PriceTicker() {
    const [livePrices, setLivePrices] = useState({});
    const [isLoading, setIsLoading] = useState(true);
    const previousPricesRef = useRef({});

    useEffect(() => {
        const fetchPrices = async () => {
            try {
                const response = await fetch('https://aisignalpro-production.up.railway.app/api/data/all/');
                if (!response.ok) throw new Error("Network response was not ok");
                const data = await response.json(); // فرمت جدید: {'BTC': {'price': 68000, 'source': 'kucoin'}, ...}
                
                if (!data || typeof data !== 'object') return;

                const coinsToDisplay = ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE'];
                const newLivePrices = {};
                
                for (const coin of coinsToDisplay) {
                    if (data[coin]) {
                        const newPrice = data[coin].price;
                        const oldPrice = previousPricesRef.current[coin] || newPrice;
                        const changePercent = oldPrice ? ((newPrice - oldPrice) / oldPrice * 100).toFixed(2) : '0.00';

                        newLivePrices[coin] = {
                            symbol: `${coin}/USDT`,
                            price: newPrice,
                            change: `${parseFloat(changePercent) >= 0 ? '+' : ''}${changePercent}%`,
                            source: data[coin].source.charAt(0).toUpperCase() + data[coin].source.slice(1),
                        };
                        // آپدیت ref برای استفاده در بازخوانی بعدی
                        previousPricesRef.current[coin] = newPrice;
                    }
                }
                setLivePrices(newLivePrices);
            } catch (error) {
                console.error("Failed to fetch live prices:", error);
            } finally {
                setIsLoading(false);
            }
        };
        
        fetchPrices();
        const intervalId = setInterval(fetchPrices, 5000);
        return () => clearInterval(intervalId);
    }, []);

    if (isLoading) { return <section className="min-h-[250px] flex justify-center items-center"><p className="text-center text-gray-400">Loading Live Prices...</p></section>; }
    
    return (
        <section>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {['BTC', 'ETH', 'XRP', 'SOL', 'DOGE'].map(coin => {
                    const p = livePrices[coin];
                    if (!p) return null;
                    return (
                        <div key={p.symbol} className="bg-gray-800/30 backdrop-blur-lg rounded-lg p-3 flex justify-between items-center border border-yellow-500/10">
                            <div><p className="font-bold text-white">{p.symbol}</p><p className="text-xs text-gray-500">{p.source}</p></div>
                            <div>
                                <p className="font-semibold text-lg text-yellow-500 text-right">${formatPrice(p.price)}</p>
                                <p className={'text-xs text-right ' + (p.change.startsWith('+') ? 'text-green-400' : 'text-red-400')}>{p.change}</p>
                            </div>
                        </div>
                    );
                })}
            </div>
        </section>
    );
}

// ===================================================================
// کامپوننت اصلی صفحه
// ===================================================================
export default function Home() {
    // ... (کد کامل و صحیح قبلی)
}
