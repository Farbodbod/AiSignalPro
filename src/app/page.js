'use client';
import { useState, useEffect } from 'react';

// ===================================================================
// کامپوننت ۱: وضعیت سیستم (بدون تغییر)
// ===================================================================
function SystemStatus() {
  // ... (این کامپوننت همانطور که بود باقی می‌ماند و به درستی کار می‌کند) ...
  const [statuses, setStatuses] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  useEffect(() => {
    async function fetchStatuses() {
      try {
        const response = await fetch('https://aisignalpro-production.up.railway.app/api/status/');
        if (!response.ok) { throw new Error("Network response was not ok"); }
        const data = await response.json();
        setStatuses(data);
      } catch (error) {
        console.error("Failed to fetch statuses:", error);
      } finally {
        setIsLoading(false);
      }
    }
    fetchStatuses();
  }, []);

  if (isLoading) { return <section><p className="text-gray-400 text-center">Loading System Status...</p></section>; }
  
  return (
    <section>
        {/* JSX for SystemStatus */}
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
function MarketOverview() {
    const marketData = [
        { label: 'Market Cap', value: '$2.3T', change: '+1.5%' },
        { label: 'Volume 24h', value: '$85B', change: '-5.2%' },
        { label: 'BTC Dominance', value: '51.7%', change: '+0.2%' },
        { label: 'Fear & Greed', value: '72 (Greed)', change: '' },
    ];
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
// کامپوننت ۳: تیکر قیمت (آپدیت شده برای دریافت دیتای زنده)
// ===================================================================
function PriceTicker() {
    const [livePrices, setLivePrices] = useState([]);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        async function fetchPrices() {
            try {
                const response = await fetch('https://aisignalpro-production.up.railway.app/api/data/all/');
                if (!response.ok) { throw new Error("Network response was not ok"); }
                const data = await response.json();
                
                const formattedPrices = [];
                // پردازش داده‌های دریافتی از API
                for (const source in data) {
                    if (data[source].length > 0) {
                        const latestData = data[source][data[source].length - 1];
                        formattedPrices.push({
                            symbol: 'BTC/USDT',
                            price: parseFloat(latestData.close).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
                            // درصد تغییر را فعلا ثابت می‌گذاریم
                            change: '+2.1%', 
                            source: source.charAt(0).toUpperCase() + source.slice(1),
                        });
                    }
                }
                setLivePrices(formattedPrices);

            } catch (error) {
                console.error("Failed to fetch live prices:", error);
            } finally {
                setIsLoading(false);
            }
        }
        fetchPrices();
    }, []);

    if (isLoading) {
        return <section><p className="text-center text-gray-400">Loading Live Prices...</p></section>;
    }

    return (
        <section>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* نمایش قیمت‌های زنده دریافت شده */}
                {livePrices.map(p => (
                    <div key={p.source} className="bg-gray-800/30 backdrop-blur-lg rounded-lg p-3 flex justify-between items-center border border-yellow-500/10">
                        <div>
                            <p className="font-bold text-white">{p.symbol}</p>
                            <p className="text-xs text-gray-500">{p.source}</p>
                        </div>
                        <div>
                            <p className="font-semibold text-white text-right">${p.price}</p>
                            <p className={'text-xs text-right ' + (p.change.startsWith('+') ? 'text-green-400' : 'text-red-400')}>{p.change}</p>
                        </div>
                    </div>
                ))}
            </div>
        </section>
    );
}


// ===================================================================
// کامپوننت اصلی صفحه که همه چیز را کنار هم می‌چیند
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
        {/* بقیه کامپوننت‌ها در آینده اینجا اضافه می‌شوند */}
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
