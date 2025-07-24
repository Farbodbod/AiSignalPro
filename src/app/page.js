'use client';
import { useState, useEffect, useRef } from 'react';

// ===================================================================
// توابع کمکی
// ===================================================================
const formatLargeNumber = (num) => {
  if (num === null || num === undefined || num === 0) return 'N/A';
  if (num >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
  if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
  if (num >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
  return `$${num.toLocaleString()}`;
};

const formatPrice = (price) => {
    if (price === null || price === undefined) return 'N/A';
    const options = {
        minimumFractionDigits: 2,
        maximumFractionDigits: price < 10 ? 4 : 2,
    };
    return price.toLocaleString('en-US', options);
};

// ===================================================================
// کامپوننت‌های کمکی برای نمایش لودینگ و خطا
// ===================================================================
const ErrorDisplay = ({ componentName, error }) => (
    <section className="bg-red-800/40 text-red-200 p-3 rounded-lg border border-red-500/50">
        <h3 className="font-bold text-white">Error in {componentName}:</h3>
        <p className="font-mono text-sm mt-2 break-words">{error.toString()}</p>
    </section>
);

const StatusSkeleton = () => (
    <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20 min-h-[72px] animate-pulse">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-center">
            {[...Array(5)].map((_, i) => <div key={i} className="h-12 bg-gray-700/50 rounded-lg"></div>)}
        </div>
    </section>
);
const MarketSkeleton = () => (
    <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20 h-[96px] animate-pulse">
        <div className="grid grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => <div key={i} className="h-10 bg-gray-700/50 rounded-lg"></div>)}
        </div>
    </section>
);
const TickerSkeleton = () => (
    <section className="min-h-[250px] animate-pulse">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[...Array(4)].map((_, i) => <div key={i} className="h-16 bg-gray-700/50 rounded-lg"></div>)}
        </div>
    </section>
);


// ===================================================================
// کامپوننت ۱: وضعیت سیستم
// ===================================================================
function SystemStatus() {
    const [statuses, setStatuses] = useState([]);
    const [error, setError] = useState(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const fetchStatuses = async () => {
            try {
                const response = await fetch('https://aisignalpro-production.up.railway.app/api/status/', { headers: { 'Accept': 'application/json' } });
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const data = await response.json();
                setStatuses(data);
                setError(null);
            } catch (e) {
                console.error("Failed to fetch statuses:", e);
                setError(e);
            } finally {
                setIsLoading(false);
            }
        };
        fetchStatuses();
        const intervalId = setInterval(fetchStatuses, 30000);
        return () => clearInterval(intervalId);
    }, []);

    if (isLoading) return <StatusSkeleton />;
    if (error) return <ErrorDisplay componentName="System Status" error={error} />;
    
    return (
        <section>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-center">
                {statuses.map((ex) => (
                    <div key={ex.name} className="bg-gray-800/30 backdrop-blur-lg rounded-lg p-2 border border-yellow-500/10">
                        <p className="text-xs font-semibold text-gray-300">{ex.name}</p>
                        <div className="flex items-center justify-center gap-2 mt-1">
                            <span className={'w-2 h-2 rounded-full ' + (ex.status === 'online' ? 'bg-green-400 animate-pulse' : 'bg-red-500')}></span>
                            <span className="text-xs text-gray-400">{ex.ping}</span>
                        </div>
                    </div>
                ))}
                 <div className="bg-yellow-500/80 text-black p-2 rounded-lg text-sm font-bold flex items-center justify-center cursor-pointer hover:bg-yellow-500 col-span-2 md:col-span-1">Test All</div>
            </div>
        </section>
    );
}

// ===================================================================
// کامپوننت ۲: نمای کلی بازار
// ===================================================================
function MarketOverview() {
    const [marketData, setMarketData] = useState(null);
    const [error, setError] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    
    useEffect(() => {
        const fetchMarketData = async () => {
            try {
                const response = await fetch('https://aisignalpro-production.up.railway.app/api/market-overview/', { headers: { 'Accept': 'application/json' } });
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const data = await response.json();
                if (data && data.market_cap && data.market_cap !== 'N/A') {
                    setMarketData(data);
                    setError(null);
                } else {
                    // This handles cases where the API returns a valid response with "N/A"
                    throw new Error("Received N/A from API. One of the external sources may be down.");
                }
            } catch (e) {
                console.error("Failed to fetch market data:", e);
                setError(e);
            } finally {
                setIsLoading(false);
            }
        };
        fetchMarketData();
        const intervalId = setInterval(fetchMarketData, 30000);
        return () => clearInterval(intervalId);
    }, []);
    
    if (isLoading) return <MarketSkeleton />;
    if (error && !marketData) return <ErrorDisplay componentName="Market Overview" error={error} />;

    return (
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div><p className="text-xs text-gray-400">Market Cap</p><p className="font-bold text-lg text-yellow-500">{formatLargeNumber(marketData?.market_cap)}</p></div>
                <div><p className="text-xs text-gray-400">Volume 24h</p><p className="font-bold text-lg text-yellow-500">{formatLargeNumber(marketData?.volume_24h)}</p></div>
                <div><p className="text-xs text-gray-400">BTC Dominance</p><p className="font-bold text-lg text-yellow-500">{marketData ? `${Number(marketData.btc_dominance).toFixed(1)}%` : 'N/A'}</p></div>
                <div><p className="text-xs text-gray-400">Fear & Greed</p><p className="font-bold text-lg text-yellow-500">{marketData?.fear_and_greed || 'N/A'}</p></div>
            </div>
        </section>
    );
}

// ===================================================================
// کامپوننت ۳: تیکر قیمت
// ===================================================================
function PriceTicker() {
    const [livePrices, setLivePrices] = useState({});
    const [error, setError] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const previousPricesRef = useRef({});

    useEffect(() => {
        const fetchPrices = async () => {
            try {
                const response = await fetch('https://aisignalpro-production.up.railway.app/api/data/all/', { headers: { 'Accept': 'application/json' } });
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const data = await response.json();
                if (!data || typeof data !== 'object') throw new Error("Invalid data format from API.");
                
                const coinsToDisplay = ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE'];
                const formattedPrices = {};
                for (const coin of coinsToDisplay) {
                    if (data[coin] && Object.keys(data[coin]).length > 0) {
                        const source = Object.keys(data[coin])[0];
                        const price = data[coin][source];
                        const oldPrice = previousPricesRef.current[coin] || price;
                        const changePercent = oldPrice ? ((price - oldPrice) / oldPrice * 100).toFixed(2) : '0.00';

                        formattedPrices[coin] = {
                            symbol: `${coin}/USDT`,
                            price: price,
                            change: `${parseFloat(changePercent) >= 0 ? '+' : ''}${changePercent}%`,
                            source: source.charAt(0).toUpperCase() + source.slice(1),
                        };
                    }
                }
                if (Object.keys(formattedPrices).length > 0) {
                    setLivePrices(formattedPrices);
                    previousPricesRef.current = Object.keys(formattedPrices).reduce((acc, coin) => {
                        acc[coin] = formattedPrices[coin].price;
                        return acc;
                    }, {});
                }
                setError(null);
            } catch (e) {
                console.error("Failed to fetch live prices:", e);
                setError(e);
            } finally {
                setIsLoading(false);
            }
        };
        
        fetchPrices();
        const intervalId = setInterval(fetchPrices, 10000);
        return () => clearInterval(intervalId);
    }, []);

    if (isLoading) return <TickerSkeleton />;
    if (error) return <ErrorDisplay componentName="Price Ticker" error={error} />;

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
    return (
        <div className="bg-black text-gray-200 min-h-screen">
            <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-br from-gray-900 via-black to-gray-800 -z-10"/>
            <header className="flex justify-between items-center p-4 border-b border-yellow-500/30 sticky top-0 bg-gray-900/70 backdrop-blur-xl z-10">
                <h1 className="text-xl md:text-2xl font-bold text-yellow-500 drop-shadow-[0_2px_2px_rgba(255,215,0,0.5)]">🤖 Ai Signal Pro</h1>
                <div><button className="w-8 h-8 rounded-full bg-white/10 border border-yellow-500/30 text-yellow-500">☀️</button></div>
            </header>
            <main className="p-4 space-y-6 pb-20">
                <SystemStatus />
                <MarketOverview />
                <PriceTicker />
            </main>
            <footer className="fixed bottom-0 left-0 right-0 p-2 bg-gray-900/70 backdrop-blur-xl border-t border-yellow-500/30">
                <div className="flex justify-around text-gray-400">
                    <button className="text-yellow-500 font-bold">Dashboard</button>
                    <button className="hover:text-yellow-500">Signals</button>
                    <button className="hover:text-yellow-500">Trades</button>
                    <button className="hover:text-yellow-500">Analysis</button>
                </div>
            </footer>
        </div>
    )
}
