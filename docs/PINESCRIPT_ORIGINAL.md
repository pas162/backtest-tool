# Original PineScript Strategy

This is the original TradingView PineScript that needs to be converted to Python.

```pinescript
//@version=5
indicator("Combined Strategy: VWAP + SuperTrend + EMA + Stoch RSI (V2)", overlay=true, shorttitle="VWAP+ST+EMA Strat V2")

// ==========================================
// 1. INPUT SETTINGS
// ==========================================
// EMA Settings
grp_ema = "EMA Settings"
len_ema1 = input.int(21, title="EMA 1 Length", group=grp_ema)
len_ema2 = input.int(50, title="EMA 2 Length", group=grp_ema)

// SuperTrend Settings
grp_st = "SuperTrend Settings"
st_len = input.int(12, title="ATR Length", group=grp_st)
st_mul = input.float(3.0, title="Factor", group=grp_st)

// VWAP Settings
grp_vwap = "VWAP Settings"
vwap_anchor = input.string("Session", "Anchor Period", options=["Session", "Week", "Month", "Year"], group=grp_vwap)

// Stoch RSI Settings
grp_stoch = "Stoch RSI Settings"
smoothK = input.int(3, "K", group=grp_stoch)
smoothD = input.int(3, "D", group=grp_stoch)
lengthRSI = input.int(14, "RSI Length", group=grp_stoch)
lengthStoch = input.int(14, "Stochastic Length", group=grp_stoch)
src = input(close, title="RSI Source", group=grp_stoch)

// ==========================================
// 2. CALCULATIONS
// ==========================================

// --- EMA ---
ema1 = ta.ema(close, len_ema1)
ema2 = ta.ema(close, len_ema2)

// --- VWAP ---
vwap_val = ta.vwap(hlc3)

// --- SuperTrend ---
[st_val, st_dir] = ta.supertrend(st_mul, st_len)

// --- Stoch RSI ---
rsi1 = ta.rsi(src, lengthRSI)
k = ta.sma(ta.stoch(rsi1, rsi1, rsi1, lengthStoch), smoothK)
d = ta.sma(k, smoothD)

// ==========================================
// 3. LOGIC DEFINITIONS
// ==========================================

// --- Item 1: Trend Identification ---
uptrend_1 = (ema1 > ema2)
uptrend_2 = st_dir < 0
uptrend_3 = (ema1 > vwap_val) and (ema2 > vwap_val)
score_uptrend = (uptrend_1 ? 1 : 0) + (uptrend_2 ? 1 : 0) + (uptrend_3 ? 1 : 0)
is_uptrend_zone = score_uptrend >= 2

downtrend_1 = (ema1 < ema2)
downtrend_2 = st_dir > 0
downtrend_3 = (ema1 < vwap_val) and (ema2 < vwap_val)
score_downtrend = (downtrend_1 ? 1 : 0) + (downtrend_2 ? 1 : 0) + (downtrend_3 ? 1 : 0)
is_downtrend_zone = score_downtrend >= 2

// --- Helper: Price "Near" Lines ---
lowest_recent = ta.lowest(low, 4)
is_touching_support = (lowest_recent <= ema2) or (lowest_recent <= vwap_val) or (lowest_recent <= st_val)

highest_recent = ta.highest(high, 4)
is_touching_resis = (highest_recent >= ema2) or (highest_recent >= vwap_val) or (highest_recent >= st_val)

// --- Helper: Multi-Candle Reversal Pattern ---

// For BUY: Find recent RED candle to beat
float open_to_beat_buy = na
if close[1] < open[1]
    open_to_beat_buy := open[1]
else if close[2] < open[2]
    open_to_beat_buy := open[2]
else if close[3] < open[3]
    open_to_beat_buy := open[3]

is_bullish_rev_candle = (close > open) and not na(open_to_beat_buy) and (close > open_to_beat_buy)

// For SELL: Find recent GREEN candle to beat
float open_to_beat_sell = na
if close[1] > open[1]
    open_to_beat_sell := open[1]
else if close[2] > open[2]
    open_to_beat_sell := open[2]
else if close[3] > open[3]
    open_to_beat_sell := open[3]

is_bearish_rev_candle = (close < open) and not na(open_to_beat_sell) and (close < open_to_beat_sell)


// --- Item 2a: PULL-BACK SIGNALS ---
signal_pullback_buy = is_uptrend_zone and is_touching_support and is_bullish_rev_candle and (k < 20)
signal_pullback_sell = is_downtrend_zone and is_touching_resis and is_bearish_rev_candle and (k > 80)

// --- Item 2b: REVERSAL SIGNALS (SuperTrend Flip) ---
st_new_buy = ta.change(st_dir) < 0
st_new_sell = ta.change(st_dir) > 0

confirm_buy = (close > ema1) and (close > ema2) and (close > vwap_val)
confirm_sell = (close < ema1) and (close < ema2) and (close < vwap_val)

signal_reversal_buy = st_new_buy and confirm_buy
signal_reversal_sell = st_new_sell and confirm_sell

// ==========================================
// 4. PLOTTING & VISUALS
// ==========================================

plot(ema1, title="EMA 21", color=color.yellow, linewidth=2)
plot(ema2, title="EMA 50", color=color.orange, linewidth=2)
plot(vwap_val, title="VWAP", color=color.blue, linewidth=2)
plot(st_val, title="SuperTrend", color = st_dir == -1 ? color.green : color.red, linewidth=1)

// Buy Signals
plotshape(signal_pullback_buy, title="Pullback Buy", style=shape.triangleup, location=location.belowbar, color=color.green, size=size.small, text="PB")
plotshape(signal_reversal_buy, title="Reversal Buy", style=shape.triangleup, location=location.belowbar, color=color.lime, size=size.small, text="Rev")

// Sell Signals
plotshape(signal_pullback_sell, title="Pullback Sell", style=shape.triangledown, location=location.abovebar, color=color.red, size=size.small, text="PB")
plotshape(signal_reversal_sell, title="Reversal Sell", style=shape.triangledown, location=location.abovebar, color=color.maroon, size=size.small, text="Rev")

// Trend Zone Background
bgcolor(is_uptrend_zone ? color.new(color.green, 95) : na, title="Uptrend Zone")
bgcolor(is_downtrend_zone ? color.new(color.red, 95) : na, title="Downtrend Zone")

// Alerts
alertcondition(signal_pullback_buy or signal_reversal_buy, title="Buy Signal", message="Buy Signal Detected")
alertcondition(signal_pullback_sell or signal_reversal_sell, title="Sell Signal", message="Sell Signal Detected")
```

## Strategy Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| EMA 1 Length | 21 | Fast EMA period |
| EMA 2 Length | 50 | Slow EMA period |
| ATR Length | 12 | SuperTrend ATR period |
| Factor | 3.0 | SuperTrend multiplier |
| Stoch K | 3 | Stochastic RSI smoothing K |
| Stoch D | 3 | Stochastic RSI smoothing D |
| RSI Length | 14 | RSI period |
| Stochastic Length | 14 | Stochastic period |

## Signal Types

1. **Pullback Buy**: Uptrend + touching support + bullish reversal candle + K < 20
2. **Pullback Sell**: Downtrend + touching resistance + bearish reversal candle + K > 80
3. **Reversal Buy**: SuperTrend flips bullish + price above all EMAs and VWAP
4. **Reversal Sell**: SuperTrend flips bearish + price below all EMAs and VWAP
