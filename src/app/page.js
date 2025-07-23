'use client';
import { useState, useEffect } from 'react';

function SystemStatus() {
    const [statuses, setStatuses] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    useEffect(() => {
        const fetchStatuses = async () => {
            try {
                const response = await fetch('https://aisignalpro-production.up.railway.app/api/status/');
                if (!response.ok) { throw new Error("Network response was not ok"); }
                const data = await response.json();
                setStatuses(data);
            } catch (error) { setStatuses([]); } finally { setIsLoading(false); }
        };
        fetchStatuses();
        const intervalId = setInterval(fetchStatuses, 30000);
        return () => clearInterval(intervalId);
    }, []);
    if (isLoading) { return <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20 min-h-[96px] flex justify-center items-center"><p className="text-gray-400">Loading System Status...</p></section>; }
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

function MarketOverview() {
    const [marketData, setMarketData] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    useEffect(() => {
        const fetchMarketData = async () => {
            try {
                const response = await fetch('https://aisignalpro-production.up.railway.app/api/market-overview/');
                if (!response.ok) { throw new Error("Network response was not ok"); }
                const data = await response.json();
                setMarketData(data);
            } catch (error) { console.error("Failed to fetch market data:", error); } finally { setIsLoading(false); }
        };
        fetchMarketData();
        const intervalId = setInterval(fetchMarketData, 30000);
        return () => clearInterval(intervalId);
    }, []);
    if (isLoading) { return <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20 h-[96px] flex justify-center items-center"><p className="text-gray-400">Loading Market Overview...</p></section>; }
    return (
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div><p className="text-xs text-gray-400">Market Cap</p><p className="font-bold text-lg text-white">{marketData?.market_cap || 'N/A'}</p></div>
                <div><p className="text-xs text-gray-400">Volume 24h</p><p className="font-bold text-lg text-white">{marketData?.volume_24h || 'N/A'}</p></div>
                <div><p className="text-xs text-gray-400">BTC Dominance</p><p className="font-bold text-lg text-white">{marketData?.btc_dominance || 'N/A'}</p></div>
                <div><p className="text-xs text-gray-400">Fear & Greed</p><p className="font-bold text-lg text-white">{marketData?.fear_and_greed || 'N/A'}</p></div>
            </div>
        </section>
    );
}

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
                        formattedPrices[coin] = {
                            symbol: `${coin}/USDT`,
                            price: price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
                            change: ((Math.random() - 0.5) * 5).toFixed(1) + '%', 
                            source: source.charAt(0).toUpperCase() + source.slice(1),
                        };
                    }
                }
                setLivePrices(formattedPrices);
            } catch (error) { console.error("Failed to fetch live prices:", error); } finally { setIsLoading(false); }
        };
        fetchPrices();
        const intervalId = setInterval(fetchPrices, 10000);
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
                            <div><p className="font-semibold text-white text-right">${p.price}</p><p className={'text-xs text-right ' + (p.change.startsWith('+') ? 'text-green-400' : 'text-red-400')}>{p.change}</p></div>
                        </div>
                    );
                })}
            </div>
        </section>
    );
}

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
