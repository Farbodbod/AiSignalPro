'use client';
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { TbBrain } from "react-icons/tb";

// Helper Functions
const formatLargeNumber = (num) => {
  if (!num || num === 0) return 'N/A';
  if (num >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
  if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
  return `$${(num / 1e6).toFixed(2)}M`;
};
const formatPrice = (price) => {
    if (price === null || price === undefined) return 'N/A';
    const options = { minimumFractionDigits: 2, maximumFractionDigits: price < 10 ? 4 : 2 };
    return price.toLocaleString('en-US', options);
};
const capitalize = (s) => {
    if (typeof s !== 'string' || s.length === 0) return '';
    return s.charAt(0).toUpperCase() + s.slice(1);
};

// Main Components
function SystemStatus() {
    const [statuses, setStatuses] = useState([]);
    const fetchStatuses = useCallback(async () => {
        try {
            const response = await fetch('https://aisignalpro-production.up.railway.app/api/status/');
            if (response.ok) setStatuses(await response.json());
        } catch (error) { console.error("Failed to fetch statuses:", error); }
    }, []);
    useEffect(() => {
        fetchStatuses();
        const intervalId = setInterval(fetchStatuses, 60000);
        return () => clearInterval(intervalId);
    }, [fetchStatuses]);
    return (
        <section className="grid grid-cols-3 md:grid-cols-7 gap-2 text-center">
            {statuses.map((ex) => (
                <div key={ex.name} className="bg-gray-800/30 backdrop-blur-lg rounded-lg p-2 border border-yellow-500/10">
                    <p className="text-xs font-semibold text-gray-300">{ex.name}</p>
                    <div className="flex items-center justify-center gap-2 mt-1">
                        <span className={'w-2 h-2 rounded-full ' + (ex.status === 'online' ? 'bg-green-400 animate-pulse' : 'bg-red-500')}></span>
                        <span className="text-xs text-gray-400">{ex.ping}</span>
                    </div>
                </div>
            ))}
        </section>
    );
}

function MarketOverview() {
    const [marketData, setMarketData] = useState(null);
    useEffect(() => {
        const fetchMarketData = async () => {
            try {
                const response = await fetch('https://aisignalpro-production.up.railway.app/api/market-overview/');
                if (response.ok) setMarketData(await response.json());
            } catch (error) { console.error("Failed to fetch market data:", error); }
        };
        fetchMarketData();
        const intervalId = setInterval(fetchMarketData, 60000);
        return () => clearInterval(intervalId);
    }, []);
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

const SignalCard = ({ signal }) => {
    // ... (محتوای کامل کامپوننت از نسخه کامل قبلی)
};

const Signals = () => {
    // ... (محتوای کامل کامپوننت از نسخه کامل قبلی)
};

const ActiveTradeCard = ({ trade }) => {
    // ... (محتوای کامل کامپوننت از نسخه کامل قبلی)
};

const ActiveTrades = () => {
    // ... (محتوای کامل کامپوننت از نسخه کامل قبلی)
};

const AiChat = () => {
    // ... (محتوای کامل کامپوننت از نسخه کامل قبلی)
};

export default function Home() {
    return (
        <div className="bg-black text-gray-200 min-h-screen">
            <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-br from-gray-900 via-black to-gray-800 -z-10"/>
            <header className="flex justify-between items-center p-4 border-b border-yellow-500/30 sticky top-0 bg-gray-900/70 backdrop-blur-xl z-10">
                <div className="flex items-center gap-3">
                    <TbBrain className="text-yellow-400 text-3xl drop-shadow-[0_0_8px_rgba(250,204,21,0.5)]" />
                    <h1 className="text-xl md:text-2xl font-bold bg-gradient-to-r from-yellow-400 to-orange-400 bg-clip-text text-transparent drop-shadow-[0_0_5px_rgba(255,165,0,0.8)]">
                        Ai Signal Pro
                    </h1>
                </div>
            </header>
            <main className="p-4 space-y-6 pb-20">
                <SystemStatus />
                <MarketOverview />
                <Signals />
                <ActiveTrades />
                <AiChat />
            </main>
        </div>
    )
}
