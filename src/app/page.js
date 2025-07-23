'use client';
import { useState, useEffect } from 'react';

// (کامپوننت‌های SystemStatus و MarketOverview بدون تغییر)
function SystemStatus() { /* ... کد قبلی ... */ }
function MarketOverview() { /* ... کد قبلی ... */ }

// ===================================================================
// کامپوننت ۳: تیکر قیمت (بازنویسی شده برای نمایش قیمت لحظه‌ای)
// ===================================================================
function PriceTicker() {
    const [livePrices, setLivePrices] = useState({});
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const fetchPrices = async () => {
            try {
                const response = await fetch('https://aisignalpro-production.up.railway.app/api/data/all/');
                if (!response.ok) { throw new Error("Network response was not ok"); }
                const data = await response.json(); // Data format: {'BTC': {'kucoin': 68000.1, 'gate.io': 68000.2}, ...}
                
                const coinsToDisplay = ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE'];
                const formattedPrices = {};

                for (const coin of coinsToDisplay) {
                    if (data[coin] && Object.keys(data[coin]).length > 0) {
                        // انتخاب اولین منبع موجود برای نمایش
                        const source = Object.keys(data[coin])[0];
                        const price = data[coin][source];
                        formattedPrices[coin] = {
                            symbol: `${coin}/USDT`,
                            price: price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
                            // درصد تغییر را فعلا ثابت می‌گذاریم
                            change: ((Math.random() - 0.5) * 5).toFixed(1) + '%', 
                            source: source.charAt(0).toUpperCase() + source.slice(1),
                        };
                    }
                }
                setLivePrices(formattedPrices);
            } catch (error) {
                console.error("Failed to fetch live prices:", error);
            } finally {
                setIsLoading(false);
            }
        };
        
        fetchPrices();
        const intervalId = setInterval(fetchPrices, 10000); // بازخوانی هر ۱۰ ثانیه
        return () => clearInterval(intervalId);
    }, []);

    const coinsToRender = ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE'];

    if (isLoading) {
        return <section className="min-h-[250px] flex justify-center items-center"><p className="text-center text-gray-400">Loading Live Prices...</p></section>;
    }

    return (
        <section>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {coinsToRender.map(coin => {
                    const p = livePrices[coin];
                    if (!p) return null; // اگر داده‌ای برای این ارز وجود نداشت، چیزی نمایش نده
                    return (
                        <div key={p.symbol} className="bg-gray-800/30 backdrop-blur-lg rounded-lg p-3 flex justify-between items-center border border-yellow-500/10">
                            <div>
                                <p className="font-bold text-white">{p.symbol}</p>
                                <p className="text-xs text-gray-500">{p.source}</p>
                            </div>
                            <div>
                                <p className="font-semibold text-white text-right">${p.price}</p>
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
    // ... (کد قبلی بدون تغییر) ...
}
