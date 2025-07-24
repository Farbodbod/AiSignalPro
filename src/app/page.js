'use client';
import { useState, useEffect } from 'react';

// (توابع کمکی و کامپوننت‌های SystemStatus و MarketOverview بدون تغییر باقی می‌مانند)
const formatPrice = (price) => {
    if (price === null || price === undefined) return 'N/A';
    const options = { minimumFractionDigits: 2, maximumFractionDigits: price < 10 ? 4 : 2 };
    return price.toLocaleString('en-US', options);
};
function SystemStatus() { /* ... کد کامل قبلی ... */ }
function MarketOverview() { /* ... کد کامل قبلی ... */ }

function PriceTicker() {
    const [livePrices, setLivePrices] = useState({});
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const fetchPrices = async () => {
            try {
                const response = await fetch('https://aisignalpro-production.up.railway.app/api/data/all/');
                if (!response.ok) throw new Error("Network response was not ok");
                const data = await response.json();
                if (data && typeof data === 'object') {
                    setLivePrices(data);
                }
            } catch (error) {
                console.error("Failed to fetch live prices:", error);
            } finally {
                setIsLoading(false);
            }
        };
        
        fetchPrices();
        const intervalId = setInterval(fetchPrices, 10000);
        return () => clearInterval(intervalId);
    }, []);

    if (isLoading) {
        return <section className="min-h-[250px] animate-pulse"><div className="grid grid-cols-1 md:grid-cols-2 gap-4">{[...Array(5)].map((_, i) => <div key={i} className="h-16 bg-gray-700/50 rounded-lg"></div>)}</div></section>;
    }
    
    return (
        <section>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {['BTC', 'ETH', 'XRP', 'SOL', 'DOGE'].map(coin => {
                    const p = livePrices[coin];
                    if (!p) return null;
                    
                    const change = p.change_24h || 0;
                    const changeClass = change >= 0 ? 'text-green-400' : 'text-red-400';
                    const changePrefix = change >= 0 ? '+' : '';

                    return (
                        <div key={coin} className="bg-gray-800/30 backdrop-blur-lg rounded-lg p-3 flex justify-between items-center border border-yellow-500/10">
                            <div>
                                <p className="font-bold text-white">{coin}/USDT</p>
                                <p className="text-xs text-gray-500">{p.source ? p.source.charAt(0).toUpperCase() + p.source.slice(1) : ''}</p>
                            </div>
                            <div>
                                <p className="font-semibold text-lg text-yellow-500 text-right">${formatPrice(p.price)}</p>
                                <p className={`text-xs text-right ${changeClass}`}>{changePrefix}{change.toFixed(2)}%</p>
                            </div>
                        </div>
                    );
                })}
            </div>
        </section>
    );
}

export default function Home() { /* ... کد کامل قبلی ... */ }
