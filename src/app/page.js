'use client';
import React, { useState, useEffect } from 'react';

// کامپوننت وضعیت سیستم که داده‌ها را از بک‌اند شما می‌گیرد
const SystemStatus = () => {
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await fetch('https://aisignalpro-production.up.railway.app/api/system-status/');
        if (!response.ok) throw new Error('Network response was not ok');
        const data = await response.json();
        setServices(data.services || []);
      } catch (error) {
        console.error("Failed to fetch system status:", error);
        setServices([ { name: 'Backend', status: 'offline', ping: 'Error' } ]);
      } finally {
        setLoading(false);
      }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000); // هر ۳۰ ثانیه یک بار آپدیت می‌شود
    return () => clearInterval(interval);
  }, []);

  const StatusIndicator = ({ status }) => (<span className={'w-2 h-2 rounded-full ' + (status === 'online' ? 'bg-green-400 animate-pulse' : 'bg-red-500')}></span>);
  
  return (
    <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-3 border border-yellow-500/10">
      <div className="grid grid-cols-3 md:grid-cols-5 gap-2 text-center">
        {loading ? <div className="col-span-full text-xs text-gray-400">Loading Status...</div> : services.map((ex) => (
          <div key={ex.name} className="bg-black/30 p-2 rounded-lg">
            <p className="text-xs font-semibold text-gray-300">{ex.name}</p>
            <div className="flex items-center justify-center gap-2 mt-1"><StatusIndicator status={ex.status} /><span className="text-xs text-gray-400">{ex.ping}</span></div>
          </div>
        ))}
      </div>
    </section>
  );
};

// بقیه کامپوننت‌ها فعلاً با داده نمونه باقی می‌مانند
const MarketOverview = () => {
    const marketData = [ { label: 'Market Cap', value: '$2.3T', change: '+1.5%' }, { label: 'Volume 24h', value: '$85B', change: '-5.2%' }, { label: 'BTC Dominance', value: '51.7%' }, { label: 'Fear & Greed', value: '72' }, ];
    return( <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20"> <div className="grid grid-cols-2 md:grid-cols-4 gap-4"> {marketData.map(item => ( <div key={item.label}> <p className="text-xs text-gray-400">{item.label}</p> <p className="font-bold text-lg text-white">{item.value}</p> {item.change && <p className={'text-xs ' + (item.change.startsWith('+') ? 'text-green-400' : 'text-red-400')}>{item.change}</p>} </div> ))} </div> </section> )
};
const PriceTicker = () => {
    const prices = [ { symbol: 'BTC/USDT', price: '68,123.45', change: '+2.1%', source: 'Kucoin' }, { symbol: 'ETH/USDT', price: '3,540.12', change: '+3.5%', source: 'Gate.io' }, { symbol: 'SOL/USDT', price: '165.80', change: '-1.2%', source: 'MEXC' }, { symbol: 'XRP/USDT', price: '0.52', change: '+0.8%', source: 'Kucoin' }, { symbol: 'DOGE/USDT', price: '0.15', change: '-3.4%', source: 'Gate.io' }, ];
    return ( <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20"> <div className="grid grid-cols-1 md:grid-cols-2 gap-4"> {prices.map(p => ( <div key={p.symbol} className="flex justify-between items-center bg-black/20 p-2 rounded-md"> <div><p className="font-bold text-white">{p.symbol}</p><p className="text-xs text-gray-500">{p.source}</p></div> <div className="text-right"><p className="font-semibold text-white">{p.price}</p><p className={'text-sm ' + (p.change.startsWith('+') ? 'text-green-400' : 'text-red-400')}>{p.change}</p></div> </div> ))} </div> </section> )
};

// کامپوننت اصلی صفحه
export default function Home() {
  return (
    <div className="bg-black text-gray-200 min-h-screen">
      <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-br from-gray-900 via-black to-gray-800 -z-10"/>
      <header className="flex justify-between items-center p-4 border-b border-yellow-500/30 sticky top-0 bg-gray-900/70 backdrop-blur-xl z-10">
        <h1 className="text-xl md:text-2xl font-bold text-yellow-500 drop-shadow-[0_2px_2px_rgba(255,215,0,0.5)]">🤖 Ai Signal Pro</h1>
        <div><button className="w-8 h-8 rounded-full bg-white/10 border border-yellow-500/30 text-yellow-500">☀️</button></div>
      </header>
      <main className="p-4 space-y-4 pb-20">
        <SystemStatus />
        <MarketOverview />
        <PriceTicker />
        {/* Placeholder for Signals and Active Trades */}
        <div className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20 min-h-96">
          <h3 className="text-yellow-500 font-bold text-lg">Signals & Active Trades</h3>
        </div>
      </main>
      <footer className="fixed bottom-0 left-0 right-0 p-2 bg-gray-900/70 backdrop-blur-xl border-t border-yellow-500/30">
         <div className="flex justify-around text-gray-400">
            <button className="text-yellow-500 font-bold">Dashboard</button>
            <button className="hover:text-yellow-500">Signals</button>
            <button className="hover:text-yellow-500">Trades</button>
         </div>
      </footer>
    </div>
  )
}
