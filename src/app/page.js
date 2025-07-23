'use client';
import { useState, useEffect } from 'react';

// ===================================================================
// کامپوننت ۱: وضعیت سیستم (با آدرس صحیح بک‌اند)
// ===================================================================
const StatusIndicator = ({ status }) => (
  <span className={'w-2 h-2 rounded-full ' + (status === 'online' ? 'bg-green-400 animate-pulse' : 'bg-red-500')}></span>
);

function SystemStatus() {
  const [statuses, setStatuses] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchStatuses() {
      try {
        // === این آدرس آپدیت شده است ===
        const response = await fetch('https://aisignalpro-production.up.railway.app/api/status/');
        
        if (!response.ok) {
          throw new Error(`Error: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json();
        setStatuses(data);
      } catch (err) {
        console.error("Failed to fetch statuses:", err);
        setError(err.toString());
      } finally {
        setIsLoading(false);
      }
    }
    fetchStatuses();
  }, []);

  if (error) {
    return (
      <section className="bg-red-800/40 text-red-200 p-3 rounded-lg border border-red-500/50">
        <h3 className="font-bold text-white">Connection Error:</h3>
        <p className="font-mono text-sm mt-2 break-words">{error}</p>
      </section>
    );
  }

  if (isLoading) {
    return (
      <section className="text-center text-gray-400">
        <p>Loading System Status from Railway...</p>
      </section>
    );
  }

  return (
    <section>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-center">
        {statuses.map((ex) => (
          <div key={ex.name} className="bg-gray-800/30 backdrop-blur-lg rounded-lg p-2 border border-yellow-500/10">
            <p className="text-xs font-semibold text-gray-300">{ex.name}</p>
            <div className="flex items-center justify-center gap-2 mt-1">
              <StatusIndicator status={ex.status} />
              <span className="text-xs text-gray-400">{ex.ping}</span>
            </div>
          </div>
        ))}
         <div className="bg-yellow-500/80 text-black p-2 rounded-lg text-sm font-bold flex items-center justify-center cursor-pointer hover:bg-yellow-500 col-span-2 md:col-span-1">
            Test All
        </div>
      </div>
    </section>
  );
}

// ===================================================================
// کامپوننت ۲: نمای کلی بازار (بدون تغییر)
// ===================================================================
const marketData = [
    { label: 'Market Cap', value: '$2.3T', change: '+1.5%' },
    { label: 'Volume 24h', value: '$85B', change: '-5.2%' },
    { label: 'BTC Dominance', value: '51.7%', change: '+0.2%' },
    { label: 'Fear & Greed', value: '72 (Greed)', change: '' },
];

function MarketOverview() {
    return(
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {marketData.map(item => (
                    <div key={item.label}>
                        <p className="text-xs text-gray-400">{item.label}</p>
                        <p className="font-bold text-lg text-white">{item.value}</p>
                        {item.change && <p className={'text-xs ' + (item.change.startsWith('+') ? 'text-green-400' : 'text-red-400')}>{item.change}</p>}
                    </div>
                ))}
            </div>
        </section>
    )
}

// ===================================================================
// کامپوننت ۳: تیکر قیمت (بدون تغییر)
// ===================================================================
const prices = [
    { symbol: 'BTC', price: '68,123.45', change: '+2.1%', source: 'Kucoin' },
    { symbol: 'ETH', price: '3,540.12', change: '+3.5%', source: 'Gate.io' },
    { symbol: 'SOL', price: '165.80', change: '-1.2%', source: 'MEXC' },
    { symbol: 'XRP', price: '0.52', change: '+0.8%', source: 'Kucoin' },
    { symbol: 'DOGE', price: '0.15', change: '-3.4%', source: 'Gate.io' },
]
function PriceTicker() {
    return (
        <section>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                    {prices.slice(0, 3).map(p => (
                        <div key={p.symbol} className="bg-gray-800/30 backdrop-blur-lg rounded-lg p-3 flex justify-between items-center border border-yellow-500/10">
                            <div>
                                <p className="font-bold text-white">{p.symbol}/USDT</p>
                                <p className="text-xs text-gray-500">{p.source}</p>
                            </div>
                            <div>
                                <p className="font-semibold text-white text-right">{p.price}</p>
                                <p className={'text-xs text-right ' + (p.change.startsWith('+') ? 'text-green-400' : 'text-red-400')}>{p.change}</p>
                            </div>
                        </div>
                    ))}
                </div>
                <div className="space-y-2">
                     {prices.slice(3, 5).map(p => (
                        <div key={p.symbol} className="bg-gray-800/30 backdrop-blur-lg rounded-lg p-3 flex justify-between items-center border border-yellow-500/10">
                            <div>
                                <p className="font-bold text-white">{p.symbol}/USDT</p>
                                <p className="text-xs text-gray-500">{p.source}</p>
                            </div>
                            <div>
                                <p className="font-semibold text-white text-right">{p.price}</p>
                                <p className={'text-xs text-right ' + (p.change.startsWith('+') ? 'text-green-400' : 'text-red-400')}>{p.change}</p>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    )
}

// ===================================================================
// کامپوننت اصلی صفحه (بدون تغییر)
// ===================================================================
export default function Home() {
  return (
    <div className="bg-black text-gray-200 min-h-screen">
      <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-br from-gray-900 via-black to-gray-800 -z-10"/>

      <header className="flex justify-between items-center p-4 border-b border-yellow-500/30 sticky top-0 bg-gray-900/70 backdrop-blur-xl z-10">
        <h1 className="text-xl md:text-2xl font-bold text-yellow-500 drop-shadow-[0_2px_2px_rgba(255,215,0,0.5)]">
          🤖 Ai Signal Pro
        </h1>
        <div>
           <button className="w-8 h-8 rounded-full bg-white/10 border border-yellow-500/30 text-yellow-500">
             ☀️
           </button>
        </div>
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
