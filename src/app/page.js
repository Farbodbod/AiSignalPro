'use client';
import React from 'react';

// ------------------- Components -------------------

const SystemStatus = () => {
  const services = [ { name: 'Kucoin', status: 'online', ping: '120ms' }, { name: 'Gate.io', status: 'online', ping: '180ms' }, { name: 'MEXC', status: 'online', ping: '210ms' }, { name: 'Telegram', status: 'online', ping: 'OK' }, ];
  const StatusIndicator = ({ status }) => (<span className={'w-2 h-2 rounded-full ' + (status === 'online' ? 'bg-green-400 animate-pulse' : 'bg-red-500')}></span>);
  return ( <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-3 border border-yellow-500/10"> <div className="grid grid-cols-3 md:grid-cols-5 gap-2 text-center"> {services.map((ex) => ( <div key={ex.name} className="bg-black/30 p-2 rounded-lg"> <p className="text-xs font-semibold text-gray-300">{ex.name}</p> <div className="flex items-center justify-center gap-2 mt-1"><StatusIndicator status={ex.status} /><span className="text-xs text-gray-400">{ex.ping}</span></div> </div> ))} <div className="bg-yellow-500/80 text-black p-2 rounded-lg text-sm font-bold flex items-center justify-center cursor-pointer hover:bg-yellow-500 col-span-3 md:col-span-1">Test All</div> </div> </section> );
};

const MarketOverview = () => {
    const marketData = [ { label: 'Market Cap', value: '$2.3T', change: '+1.5%' }, { label: 'Volume 24h', value: '$85B', change: '-5.2%' }, { label: 'BTC Dominance', value: '51.7%' }, { label: 'Fear & Greed', value: '72' }, ];
    return( <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20"> <div className="grid grid-cols-2 md:grid-cols-4 gap-4"> {marketData.map(item => ( <div key={item.label}> <p className="text-xs text-gray-400">{item.label}</p> <p className="font-bold text-lg text-white">{item.value}</p> {item.change && <p className={'text-xs ' + (item.change.startsWith('+') ? 'text-green-400' : 'text-red-400')}>{item.change}</p>} </div> ))} </div> </section> )
};

const PriceTicker = () => {
    const prices = [ { symbol: 'BTC/USDT', price: '68,123.45', change: '+2.1%', source: 'Kucoin' }, { symbol: 'ETH/USDT', price: '3,540.12', change: '+3.5%', source: 'Gate.io' }, { symbol: 'SOL/USDT', price: '165.80', change: '-1.2%', source: 'MEXC' }, { symbol: 'XRP/USDT', price: '0.52', change: '+0.8%', source: 'Kucoin' }, { symbol: 'DOGE/USDT', price: '0.15', change: '-3.4%', source: 'Gate.io' }, ];
    return ( <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20"> <div className="grid grid-cols-1 md:grid-cols-2 gap-4"> {prices.map(p => ( <div key={p.symbol} className="flex justify-between items-center bg-black/20 p-2 rounded-md"> <div><p className="font-bold text-white">{p.symbol}</p><p className="text-xs text-gray-500">{p.source}</p></div> <div className="text-right"><p className="font-semibold text-white">{p.price}</p><p className={'text-sm ' + (p.change.startsWith('+') ? 'text-green-400' : 'text-red-400')}>{p.change}</p></div> </div> ))} </div> </section> )
};

const SignalCard = ({ signal }) => {
    const colors = { buy: { border: 'border-green-500/50', text: 'text-green-400', bg: 'bg-green-500/10' }, sell: { border: 'border-red-500/50', text: 'text-red-400', bg: 'bg-red-500/10' }, hold: { border: 'border-yellow-500/50', text: 'text-yellow-400', bg: 'bg-yellow-500/10' }, };
    const color = colors[signal.type] || colors.hold;
    return ( <div className={'rounded-xl p-4 border ' + color.border + ' ' + color.bg}> <div className="flex justify-between items-center pb-3 border-b border-gray-700/50"> <span className="font-bold text-xl text-white">{signal.symbol}</span> <span className={'font-bold text-xl ' + color.text}>{signal.type.toUpperCase()}</span> <span className="text-sm text-gray-400">{signal.timeframe}</span> </div> <div className="grid grid-cols-2 gap-x-4 gap-y-3 pt-3 text-sm"> <div><p className="text-gray-400">Entry Zone</p><p className="font-mono text-white">{signal.entry}</p></div> <div className="text-right"><p className="text-gray-400">Stop-Loss</p><p className="font-mono text-red-400">{signal.sl}</p></div> <div><p className="text-gray-400">Targets</p><div className="flex flex-wrap gap-x-3">{signal.targets.map(t => <span key={t} className="text-green-400 font-mono">{t}</span>)}</div></div> <div className="text-right"><p className="text-gray-400">Accuracy</p><p className="font-mono text-white">{signal.accuracy}</p></div> <div><p className="text-gray-400">Support</p><div className="flex flex-wrap gap-x-3">{signal.support.map(s => <span key={s} className="text-white font-mono">{s}</span>)}</div></div> <div className="text-right"><p className="text-gray-400">Resistance</p><div className="flex flex-wrap gap-x-3 justify-end">{signal.resistance.map(r => <span key={r} className="text-white font-mono">{r}</span>)}</div></div> </div> <div className="pt-3 mt-3 border-t border-gray-700/50 text-xs space-y-1"> <p className="text-gray-400">Reasons: <span className="text-gray-200">{signal.reasons.join(', ')}</span></p> </div> <div className="pt-3 mt-3 border-t border-gray-700/50 flex justify-between items-center"> <div className="text-xs text-gray-400">Confidence: <span className="font-bold text-white">{signal.confidence}%</span> | AI Score: <span className="font-bold text-white">{signal.ai_score}%</span></div> <button className="bg-yellow-500 text-black text-sm font-bold py-2 px-4 rounded-lg hover:bg-yellow-400">Enter Trade</button> </div> </div> );
};

const Signals = () => {
    const sampleSignals = [ { type: 'buy', symbol: 'BTC/USDT', timeframe: '4h', entry: '68k-68.2k', sl: '67.5k', targets: ['69k','70k','71k'], confidence: 85, ai_score: 88, reasons: ['Bullish Engulfing', 'RSI Divergence'], accuracy: "78%", support: ['67.8k', '67.2k'], resistance: ['69.1k', '70k'] }, { type: 'sell', symbol: 'ETH/USDT', timeframe: '1h', entry: '3550-3560', sl: '3600', targets: ['3500','3450'], confidence: 92, ai_score: 90, reasons: ['Bearish MACD Cross'], accuracy: "81%", support: ['3510', '3480'], resistance: ['3580', '3600'] }, ];
    return ( <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20"> <div className="flex justify-between items-center mb-3"> <h3 className="text-yellow-500 font-bold text-lg">Signals</h3> <button className="bg-gray-700/50 text-yellow-400 text-xs font-bold py-1 px-3 rounded hover:bg-gray-700">Generate Manual</button> </div> <div className="space-y-4 h-96 overflow-y-auto pr-2">{sampleSignals.map((sig, i) => <SignalCard key={i} signal={sig} />)}</div> </section> );
};

const ActiveTradeCard = ({ trade }) => {
    const denominator = Math.abs(trade.targets[0] - trade.entry_price);
    const progress = denominator !== 0
      ? Math.min(Math.abs(trade.current_price - trade.entry_price) / denominator * 100, 100)
      : 0;
    const isLong = trade.direction === 'long';
    const isProfit = (isLong && trade.current_price > trade.entry_price) || (!isLong && trade.current_price < trade.entry_price);
    const barGradient = isProfit ? 'bg-gradient-to-r from-green-500/50 to-green-500' : 'bg-gradient-to-r from-red-500/50 to-red-500';
    const progressStyle = { width: `${progress}%` };
    const sl_text = `SL: ${trade.sl}`;
    const tp_text = `TP: ${trade.targets[0]}`;

    return(
        <div className="bg-gray-900/50 rounded-lg p-3 border border-yellow-500/30 space-y-3">
            <div className="flex justify-between items-center">
                <div>
                    <span className="font-bold text-lg text-white">{trade.symbol}</span>
                    <span className={'text-xs ml-2 font-bold ' + (isLong ? 'text-green-400' : 'text-red-400')}>{isLong ? "LONG" : "SHORT"}</span>
                </div>
                <div className="text-right">
                     <span className={'font-mono text-lg ' + (isProfit ? 'text-green-400' : 'text-red-400')}>{trade.pnl}</span>
                     <p className="text-xs text-gray-400">Current: {trade.current_price}</p>
                </div>
            </div>
            <div className="relative h-6 w-full bg-black/30 rounded-lg overflow-hidden border border-gray-700">
                 <div className="absolute top-0 h-full flex items-center justify-between w-full px-2 text-xs font-mono">
                    <span className="text-red-400 font-semibold">{isLong ? sl_text : tp_text}</span>
                    <span className="text-green-400 font-semibold">{isLong ? tp_text : sl_text}</span>
                </div>
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-4 w-0.5 bg-yellow-500"></div>
                <div className={'absolute top-0 h-full ' + barGradient + ' ' + (isLong ? 'left-0' : 'right-0')} style={progressStyle}></div>
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-xs font-bold text-black bg-yellow-500 px-1 rounded-sm">Entry: {trade.entry_price}</div>
            </div>
            <div className="text-xs text-gray-300 bg-black/20 p-2 rounded-md">
                <p><span className="font-bold text-yellow-500">Live AI Score: {trade.ai_score}%</span> | {trade.status_text}</p>
            </div>
        </div>
    );
};

const ActiveTrades = () => {
    const sampleTrades = [
        { direction: 'long', symbol: 'BTC/USDT', timeframe: '4h', entry_price: 68100, current_price: 68500, sl: 67500, targets: [69000, 70000], ai_score: 91, pnl: "+$250.00", status_text: "Trend is strong, hold position." },
        { direction: 'short', symbol: 'ETH/USDT', timeframe: '1h', entry_price: 3555, current_price: 3540, sl: 3600, targets: [3500, 3450], ai_score: 85, pnl: "+$75.00", status_text: "Approaching first target." },
    ];
    return ( <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20"> <h3 className="text-yellow-500 font-bold text-lg mb-3">Active Trades</h3> <div className="space-y-4 h-96 overflow-y-auto pr-2">{sampleTrades.map((trade, i) => <ActiveTradeCard key={i} trade={trade} />)}</div> </section> );
};

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
        <Signals />
        <ActiveTrades />
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
