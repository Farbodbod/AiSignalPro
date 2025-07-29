'use client';
import React, { useState, useEffect, useCallback } from 'react';
import { 
    TbLayoutDashboard, TbTarget, TbArrowsRandom, TbMessageCircle, TbChartInfographic, TbHeartRateMonitor, 
    TbSun, TbMoon, TbDeviceDesktopAnalytics, TbBrain, TbStatusChange 
} from "react-icons/tb";

const Header = () => (
    <header className="flex justify-between items-center p-4 border-b border-yellow-500/30 sticky top-0 bg-gray-900/70 backdrop-blur-xl z-10">
        <div className="flex items-center gap-3">
            <TbBrain className="text-yellow-400 text-3xl drop-shadow-[0_0_8px_rgba(250,204,21,0.5)]" />
            <h1 className="text-xl md:text-2xl font-bold bg-gradient-to-r from-yellow-400 to-orange-400 bg-clip-text text-transparent drop-shadow-[0_0_5px_rgba(255,165,0,0.8)]">
                Ai Signal Pro
            </h1>
        </div>
        <div><button className="p-2 rounded-full bg-white/10 border border-yellow-500/30 text-yellow-500 text-xl"><TbSun /></button></div>
    </header>
);

const SystemStatus = () => {
    const services = [ { name: 'Kucoin', status: 'online' }, { name: 'OKX', status: 'online' }, { name: 'MEXC', status: 'online' }, { name: 'Telegram', status: 'online' }, ];
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
    const marketData = [ { label: 'Market Cap', value: '$2.3T', change: '+1.5%' }, { label: 'Volume 24h', value: '$85B', change: '-5.2%' }, { label: 'BTC Dominance', value: '51.7%' }, { label: 'Fear & Greed', value: '72 (Greed)' }, ];
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
    const [prices, setPrices] = useState([]);
    const [loading, setLoading] = useState(true);

    const fetchPrices = useCallback(async () => {
        if (prices.length === 0) setLoading(true);
        try {
            const response = await fetch('https://aisignalpro-production.up.railway.app/api/price-ticker/');
            if (response.ok) {
                const data = await response.json();
                if (Array.isArray(data) && data.length > 0) {
                    setPrices(data);
                }
            } else {
                console.error("Failed to fetch prices with status:", response.status);
            }
        } catch (error) {
            console.error("Failed to fetch prices:", error);
        } finally {
            setLoading(false);
        }
    }, [prices.length]);

    useEffect(() => {
        fetchPrices();
        const interval = setInterval(fetchPrices, 15000);
        return () => clearInterval(interval);
    }, [fetchPrices]);

    return (
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <h3 className="text-yellow-500 font-bold text-lg mb-3 flex items-center gap-2"><TbDeviceDesktopAnalytics/> Live Prices</h3>
            {loading ? (
                <p className="text-gray-400 text-center py-4">Loading prices...</p>
            ) : prices.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {prices.map(p => (
                        <div key={p.symbol} className="flex justify-between items-center bg-black/20 p-2 rounded-md">
                            <div>
                                <p className="font-bold text-yellow-400 drop-shadow-[0_0_3px_rgba(250,204,21,0.6)]">{p.symbol}/USDT</p>
                                <p className="text-xs text-gray-500 capitalize">{p.source}</p>
                            </div>
                            <div className="text-right">
                                <p className="font-semibold font-mono text-yellow-400 drop-shadow-[0_0_3px_rgba(250,204,21,0.6)]">
                                    ${p.price.toLocaleString('en-US', { 
                                        minimumFractionDigits: 2, 
                                        maximumFractionDigits: p.price < 100 ? 4 : 2 
                                    })}
                                </p>
                                <p className={`text-sm font-bold ${p.change_24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                    {p.change_24h >= 0 ? '+' : ''}{p.change_24h.toFixed(2)}%
                                </p>
                            </div>
                        </div>
                    ))}
                </div>
            ) : (
                 <p className="text-gray-500 text-center py-4">Could not load price data.</p>
            )}
        </section>
    );
};

const SignalCard = ({ signal }) => {
    const colors = { buy: { border: 'border-green-500/50', text: 'text-green-400', bg: 'bg-green-500/10' }, sell: { border: 'border-red-500/50', text: 'text-red-400', bg: 'bg-red-500/10' }, };
    const color = colors[signal.type];
    return ( <div className={`rounded-xl p-4 border ${color.border} ${color.bg} space-y-3`}> <div className="flex justify-between items-center pb-3 border-b border-gray-700/50"> <span className="font-bold text-xl text-white">{signal.symbol}</span> <span className={`font-bold text-xl ${color.text}`}>{signal.type.toUpperCase()}</span> <span className="text-sm text-gray-400">{signal.timeframe}</span> </div> <div className="grid grid-cols-2 gap-x-4 gap-y-3 pt-3 text-sm"> <div><p className="text-gray-400">Entry Zone</p><p className="font-mono text-white">{signal.entry}</p></div> <div className="text-right"><p className="text-gray-400">Stop-Loss</p><p className="font-mono text-red-400">{signal.sl}</p></div> <div className="col-span-2"><p className="text-gray-400">Targets</p><div className="flex flex-wrap gap-x-3">{signal.targets.map(t => <span key={t} className="text-green-400 font-mono">{t}</span>)}</div></div> </div> <div className="pt-3 mt-3 border-t border-gray-700/50 text-xs space-y-1"> <p className="text-gray-400">Reasons: <span className="text-gray-200">{signal.reasons.join(', ')}</span></p> </div> <div className="pt-3 mt-3 border-t border-gray-700/50 flex justify-between items-center"> <div className="text-xs text-gray-400">Confidence: <span className="font-bold text-white">{signal.confidence}%</span> | AI: <span className="font-bold text-white">{signal.ai_score}%</span></div> <button className="bg-yellow-500 text-black text-xs font-bold py-1 px-3 rounded-md hover:bg-yellow-400">Enter Trade</button> </div> </div> );
};

const Signals = () => {
    const sampleSignals = [ { type: 'buy', symbol: 'BTC/USDT', timeframe: '4h', entry: '68k-68.2k', sl: '67.5k', targets: ['69k','70k','71k'], confidence: 85, ai_score: 88, reasons: ['Bullish Engulfing', 'RSI Divergence'] }, { type: 'sell', symbol: 'ETH/USDT', timeframe: '1h', entry: '3550-3560', sl: '3600', targets: ['3500','3450'], confidence: 92, ai_score: 90, reasons: ['Bearish MACD Cross'] }, ];
    return ( <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20"> <div className="flex justify-between items-center mb-3"> <h3 className="text-yellow-500 font-bold text-lg flex items-center gap-2"><TbTarget/> AI Signals</h3> <button className="bg-gray-700/50 text-yellow-400 text-xs font-bold py-1 px-3 rounded hover:bg-gray-700">Generate Manual</button> </div> <div className="space-y-4 h-96 overflow-y-auto pr-2">{sampleSignals.map((sig, i) => <SignalCard key={i} signal={sig} />)}</div> </section> );
};

const ActiveTradeCard = ({ trade }) => {
    const isLong = trade.direction === 'long'; const isProfit = (isLong && trade.current_price > trade.entry_price) || (!isLong && trade.current_price < trade.entry_price); const percentChange = ((trade.current_price - trade.entry_price) / trade.entry_price) * 100; const pnlText = `${isLong ? (isProfit ? '+' : '') : (isProfit ? '' : '+')}${percentChange.toFixed(2)}%`; const totalRange = Math.abs(trade.tp1 - trade.sl); const entryPositionPercent = totalRange > 0 ? (Math.abs(trade.entry_price - trade.sl) / totalRange) * 100 : 50; const currentPositionPercent = totalRange > 0 ? (Math.abs(trade.current_price - trade.sl) / totalRange) * 100 : 50; const progressWidth = Math.abs(currentPositionPercent - entryPositionPercent); const progressLeft = Math.min(entryPositionPercent, currentPositionPercent); const barGradient = isProfit ? 'bg-gradient-to-r from-green-500/50 to-green-500' : 'bg-gradient-to-r from-red-500/50 to-red-500'; const slText = `SL: ${trade.sl}`; const tpText = `TP: ${trade.tp1}`;
    return ( <div className="bg-black/30 rounded-lg p-4 border border-yellow-500/30 space-y-4 shadow-lg shadow-black/20"> <div className="flex justify-between items-start"> <div> <span className="font-bold text-lg text-white">{trade.symbol}</span> <span className={`text-xs ml-2 font-bold px-2 py-0.5 rounded-full ${isLong ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}> {isLong ? "LONG" : "SHORT"} </span> </div> <div className="text-right"> <span className={`font-mono text-xl font-bold ${isProfit ? 'text-green-400' : 'text-red-400'}`}>{pnlText}</span> <p className="text-xs text-gray-400">Current: {trade.current_price}</p> </div> </div> <div className="relative h-6 w-full bg-black/40 rounded-full overflow-hidden border-2 border-gray-700 flex items-center"> <div className={`absolute top-0 h-full ${barGradient}`} style={{ left: `${progressLeft}%`, width: `${progressWidth}%` }}></div> <div className="absolute top-0 h-full flex justify-center items-center" style={{ left: `${entryPositionPercent}%`, transform: 'translateX(-50%)' }}> <div className="h-full w-0.5 bg-yellow-400"></div> <div className="absolute top-1/2 -translate-y-1/2 text-xs font-bold text-black bg-yellow-400 px-1.5 py-0.5 rounded-md shadow-md"> {trade.entry_price} </div> </div> <div className="absolute top-0 h-full flex items-center justify-between w-full px-3 text-xs font-mono"> <span className="font-semibold text-red-400">{isLong ? slText : tpText}</span> <span className="font-semibold text-green-400">{isLong ? tpText : slText}</span> </div> </div> <div className="text-xs text-gray-300 bg-black/20 p-2 rounded-md"> <p> <span className="font-bold text-blue-400">System: {trade.system_confidence}%</span> | <span className="font-bold text-yellow-500 ml-2">Live AI: {trade.ai_score}%</span> | <span className="ml-2">{trade.status_text}</span> </p> </div> </div> );
};

const ActiveTrades = () => {
    const sampleTrades = [ { direction: 'long', symbol: 'BTC/USDT', entry_price: 68100, current_price: 68550, sl: 67500, tp1: 69000, system_confidence: 88, ai_score: 91, status_text: "Trend is strong, hold position." }, { direction: 'short', symbol: 'ETH/USDT', entry_price: 3555, current_price: 3580, sl: 3600, tp1: 3500, system_confidence: 92, ai_score: 85, status_text: "Price is moving against the trade." }, ];
    return ( <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20"> <h3 className="text-yellow-500 font-bold text-lg mb-3 flex items-center gap-2"><TbArrowsRandom/> Active Trades</h3> <div className="space-y-4 h-96 overflow-y-auto pr-2">{sampleTrades.map((trade, i) => <ActiveTradeCard key={i} trade={trade} />)}</div> </section> );
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

export default function Home() {
    return (
        <div className="bg-black text-gray-200 min-h-screen">
            <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-br from-gray-900 via-black to-gray-800 -z-10"/>
            <Header />
            <main className="p-4 grid grid-cols-1 lg:grid-cols-2 gap-6 pb-20">
                <div className="space-y-6">
                    <SystemStatus />
                    <MarketOverview />
                    <PriceTicker />
                </div>
                <div className="space-y-6">
                    <Signals />
                    <ActiveTrades />
                </div>
            </main>
            <Footer />
        </div>
    )
}
