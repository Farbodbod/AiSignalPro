'use client';
import { useState, useEffect } from 'react';

// توابع کمکی برای فرمت اعداد
const formatLargeNumber = (num) => { /* ... کد قبلی ... */ };
const formatPrice = (price) => { /* ... کد قبلی ... */ };

// کامپوننت‌ها
function SystemStatus() { /* ... کد کامل و صحیح قبلی ... */ }
function MarketOverview() { /* ... کد کامل و صحیح قبلی ... */ }

function PriceTicker() {
    const [livePrices, setLivePrices] = useState({});
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const fetchPrices = async () => {
            try {
                const response = await fetch('https://aisignalpro-production.up.railway.app/api/data/all/');
                if (!response.ok) { throw new Error("Network response was not ok"); }
                const data = await response.json();
                
                const coinsToDisplay = ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE'];
                const formattedPrices = {};
                for (const coin of coinsToDisplay) {
                    if (data[coin] && Object.keys(data[coin]).length > 0) {
                        const source = Object.keys(data[coin])[0];
                        const price = data[coin][source];
                        
                        // **اصلاح شد: درصد تغییر دیگر تصادفی نیست**
                        const oldPrice = livePrices[coin] ? livePrices[coin].price : price;
                        const changePercent = price && oldPrice ? ((price - oldPrice) / oldPrice * 100).toFixed(2) : '0.0';

                        formattedPrices[coin] = {
                            symbol: `${coin}/USDT`,
                            price: price,
                            // نمایش درصد تغییر واقعی یا یک مقدار ثابت
                            change: `${parseFloat(changePercent) >= 0 ? '+' : ''}${changePercent}%`,
                            source: source.charAt(0).toUpperCase() + source.slice(1),
                        };
                    }
                }
                if (Object.keys(formattedPrices).length > 0) {
                    setLivePrices(formattedPrices);
                }
            } catch (error) { console.error("Failed to fetch live prices:", error); } 
            finally { setIsLoading(false); }
        };
        
        fetchPrices();
        const intervalId = setInterval(fetchPrices, 5000);
        return () => clearInterval(intervalId);
    }, []); // وابستگی livePrices حذف شد تا حلقه بی‌نهایت ایجاد نشود

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

export default function Home() { /* ... کد کامل و صحیح قبلی ... */ }
