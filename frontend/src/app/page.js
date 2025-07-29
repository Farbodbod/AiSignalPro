'use client';
import React, { useState, useEffect } from 'react';
import { 
    TbLayoutDashboard, TbTarget, TbArrowsRandom, TbMessageCircle, TbChartInfographic, TbHeartRateMonitor, 
    TbSun, TbMoon, TbDeviceDesktopAnalytics, TbBrain, TbStatusChange 
} from "react-icons/tb";

// ------------------- Components -------------------
// هر بخش از داشبورد به یک کامپوننت جداگانه تبدیل شده است

const Header = () => (
    <header className="flex justify-between items-center p-4 border-b border-yellow-500/30 sticky top-0 bg-gray-900/70 backdrop-blur-xl z-10">
        <div className="flex items-center gap-3">
            <TbBrain className="text-yellow-400 text-3xl drop-shadow-[0_0_8px_rgba(250,204,21,0.5)]" />
            <h1 className="text-xl md:text-2xl font-bold bg-gradient-to-r from-yellow-400 to-orange-400 bg-clip-text text-transparent drop-shadow-[0_0_5px_rgba(255,165,0,0.8)]">
                Ai Signal Pro
            </h1>
        </div>
        <div>
            <button className="p-2 rounded-full bg-white/10 border border-yellow-500/30 text-yellow-500 text-xl">
                <TbSun />
            </button>
        </div>
    </header>
);

const SystemStatus = () => {
    const services = [
        { name: 'Kucoin', status: 'online' }, { name: 'OKX', status: 'online' }, 
        { name: 'MEXC', status: 'offline' }, { name: 'Telegram', status: 'online' },
    ];
    const StatusIndicator = ({ status }) => (<span className={`w-2 h-2 rounded-full ${status === 'online' ? 'bg-green-400 animate-pulse' : 'bg-red-500'}`}></span>);
    return (
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-center">
                {services.map((ex) => (
                    <div key={ex.name} className="bg-black/20 p-2 rounded-md">
                        <div className="flex items-center justify-center gap-2">
                            <StatusIndicator status={ex.status} />
                            <p className="text-sm font-semibold text-gray-300">{ex.name}</p>
                        </div>
                    </div>
                ))}
            </div>
        </section>
    );
};

const MarketOverview = () => {
    const marketData = [
        { label: 'Market Cap', value: '$2.3T', change: '+1.5%' },
        { label: 'Volume 24h', value: '$85B', change: '-5.2%' },
        { label: 'BTC Dominance', value: '51.7%' },
        { label: 'Fear & Greed', value: '72 (Greed)' },
    ];
    return(
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {marketData.map(item => (
                    <div key={item.label}>
                        <p className="text-xs text-gray-400">{item.label}</p>
                        <p className="font-bold text-lg text-white">{item.value}</p>
                        {item.change && <p className={`text-xs ${item.change.startsWith('+') ? 'text-green-400' : 'text-red-400'}`}>{item.change}</p>}
                    </div>
                ))}
            </div>
        </section>
    )
};

const PriceTicker = () => {
    const prices = [
        { symbol: 'BTC/USDT', price: '68,123.45', change: '+2.1%', source: 'Kucoin' },
        { symbol: 'ETH/USDT', price: '3,540.12', change: '+3.5%', source: 'OKX' },
        { symbol: 'SOL/USDT', price: '165.80', change: '-1.2%', source: 'MEXC' },
        { symbol: 'XRP/USDT', price: '0.52', change: '+0.8%', source: 'Kucoin' },
        { symbol: 'DOGE/USDT', price: '0.15', change: '-3.4%', source: 'OKX' },
    ];
    return (
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <h3 className="text-yellow-500 font-bold text-lg mb-3 flex items-center gap-2"><TbDeviceDesktopAnalytics/> Live Prices</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {prices.map(p => (
                    <div key={p.symbol} className="flex justify-between items-center bg-black/20 p-2 rounded-md">
                        <div><p className="font-bold text-white">{p.symbol}</p><p className="text-xs text-gray-500">{p.source}</p></div>
                        <div className="text-right"><p className="font-semibold text-white">{p.price}</p><p className={`text-sm ${p.change.startsWith('+') ? 'text-green-400' : 'text-red-400'}`}>{p.change}</p></div>
                    </div>
                ))}
            </div>
        </section>
    )
};

const SignalCard = ({ signal }) => {
    const colors = {
        buy: { border: 'border-green-500/50', text: 'text-green-400', bg: 'bg-green-500/10' },
        sell: { border: 'border-red-500/50', text: 'text-red-400', bg: 'bg-red-500/10' },
    };
    const color = colors[signal.type];
    return (
        <div className={`rounded-xl p-4 border ${color.border} ${color.bg} space-y-3`}>
            <div className="flex justify-between items-center pb-3 border-b border-gray-700/50">
                <span className="font-bold text-xl text-white">{signal.symbol}</span>
                <span className={`font-bold text-xl ${color.text}`}>{signal.type.toUpperCase()}</span>
                <span className="text-sm text-gray-400">{signal.timeframe}</span>
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-3 pt-3 text-sm">
                <div><p className="text-gray-400">Entry Zone</p><p className="font-mono text-white">{signal.entry}</p></div>
                <div className="text-right"><p className="text-gray-400">Stop-Loss</p><p className="font-mono text-red-400">{signal.sl}</p></div>
                <div className="col-span-2"><p className="text-gray-400">Targets</p><div className="flex flex-wrap gap-x-3">{signal.targets.map(t => <span key={t} className="text-green-400 font-mono">{t}</span>)}</div></div>
            </div>
            <div className="pt-3 mt-3 border-t border-gray-700/50 text-xs space-y-1">
                <p className="text-gray-400">Reasons: <span className="text-gray-200">{signal.reasons.join(', ')}</span></p>
            </div>
            <div className="pt-3 mt-3 border-t border-gray-700/50 flex justify-between items-center">
                <div className="text-xs text-gray-400">Confidence: <span className="font-bold text-white">{signal.confidence}%</span> | AI: <span className="font-bold text-white">{signal.ai_score}%</span></div>
                <button className="bg-yellow-500 text-black text-xs font-bold py-1 px-3 rounded-md hover:bg-yellow-400">Enter Trade</button>
            </div>
        </div>
    );
};

const Signals = () => {
    const sampleSignals = [
        { type: 'buy', symbol: 'BTC/USDT', timeframe: '4h', entry: '68k-68.2k', sl: '67.5k', targets: ['69k','70k','71k'], confidence: 85, ai_score: 88, reasons: ['Bullish Engulfing', 'RSI Divergence'] },
        { type: 'sell', symbol: 'ETH/USDT', timeframe: '1h', entry: '3550-3560', sl: '3600', targets: ['3500','3450'], confidence: 92, ai_score: 90, reasons: ['Bearish MACD Cross'] },
    ];
    return (
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <div className="flex justify-between items-center mb-3">
                <h3 className="text-yellow-500 font-bold text-lg flex items-center gap-2"><TbTarget/> AI Signals</h3>
                <button className="bg-gray-700/50 text-yellow-400 text-xs font-bold py-1 px-3 rounded hover:bg-gray-700">Generate Manual</button>
            </div>
            <div className="space-y-4 h-96 overflow-y-auto pr-2">{sampleSignals.map((sig, i) => <SignalCard key={i} signal={sig} />)}</div>
        </section>
    );
};

const ActiveTradeCard = ({ trade }) => {
    // A simplified version for now
    const isLong = trade.direction === 'long';
    return(
        <div className="bg-black/20 rounded-lg p-3 border border-yellow-500/30 space-y-3">
            <div className="flex justify-between items-center">
                <div>
                    <span className="font-bold text-lg text-white">{trade.symbol}</span>
                    <span className={`text-xs ml-2 font-bold ${isLong ? 'text-green-400' : 'text-red-400'}`}>{isLong ? "LONG" : "SHORT"}</span>
                </div>
                <div className="text-right">
                    <span className={`font-mono text-lg ${trade.pnl.startsWith('+') ? 'text-green-400' : 'text-red-400'}`}>{trade.pnl}</span>
                    <p className="text-xs text-gray-400">Entry: {trade.entry_price}</p>
                </div>
            </div>
            <div className="text-xs text-gray-300 bg-black/30 p-2 rounded-md">
                <p><span className="font-bold text-yellow-500">Live AI Score: {trade.ai_score}%</span> | {trade.status_text}</p>
            </div>
        </div>
    );
};

const ActiveTrades = () => {
    const sampleTrades = [
        { direction: 'long', symbol: 'BTC/USDT', entry_price: 68100, ai_score: 91, pnl: "+$250.00", status_text: "Trend is strong, hold position." },
        { direction: 'short', symbol: 'ETH/USDT', entry_price: 3555, ai_score: 85, pnl: "+$75.00", status_text: "Approaching first target." },
    ];
    return (
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <h3 className="text-yellow-500 font-bold text-lg mb-3 flex items-center gap-2"><TbArrowsRandom/> Active Trades</h3>
            <div className="space-y-4 h-96 overflow-y-auto pr-2">{sampleTrades.map((trade, i) => <ActiveTradeCard key={i} trade={trade} />)}</div>
        </section>
    );
};

const Footer = () => (
    <footer className="fixed bottom-0 left-0 right-0 p-2 bg-gray-900/80 backdrop-blur-xl border-t border-yellow-500/30 z-10">
        <div className="flex justify-around text-gray-400">
            <button className="flex flex-col items-center text-yellow-500 font-bold text-xs"><TbLayoutDashboard className="text-xl mb-1"/>Dashboard</button>
            <button className="flex flex-col items-center hover:text-yellow-500 text-xs"><TbTarget className="text-xl mb-1"/>Signals</button>
            <button className="flex flex-col items-center hover:text-yellow-500 text-xs"><TbArrowsRandom className="text-xl mb-1"/>Trades</button>
            <button className="flex flex-col items-center hover:text-yellow-500 text-xs"><TbChartInfographic className="text-xl mb-1"/>Analysis</button>
        </div>
    </footer>
);


// ------------------- Main Page Component -------------------

export default function Home() {
    return (
        <div className="bg-black text-gray-200 min-h-screen">
            <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-br from-gray-900 via-black to-gray-800 -z-10"/>
            <Header />
            <main className="p-4 grid grid-cols-1 lg:grid-cols-2 gap-6 pb-20">
                {/* Column 1 */}
                <div className="space-y-6">
                    <SystemStatus />
                    <MarketOverview />
                    <PriceTicker />
                    {/* Add other components like AI Chat, etc. here */}
                </div>

                {/* Column 2 */}
                <div className="space-y-6">
                    <Signals />
                    <ActiveTrades />
                </div>
            </main>
            <Footer />
        </div>
    )
}
