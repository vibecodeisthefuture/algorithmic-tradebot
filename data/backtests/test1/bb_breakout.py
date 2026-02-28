"""
Bollinger Band Breakout Strategy Backtest

This strategy uses Bollinger Bands to identify breakout opportunities:

Entry Rules:
- Buy when price breaks above the upper Bollinger Band
- Close position when price crosses back inside bands or hits stop loss

Exit Rules:
- Sell when price crosses below middle Bollinger Band
- Stop loss at specified percentage

Risk Management:
- Position sizing based on available capital
- Stop loss protection
"""

import backtrader as bt
import pandas as pd
import datetime
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== CONFIGURATION ====================

CONFIG = {
    # Data settings - use local CSV files
    'data_files': [
        '../datasets/data_tables/stocks/GOOG-1d-1000wks-data.csv',
        '../datasets/data_tables/stocks/NVDA-1d-1000wks-data.csv',
    ],
    'symbol': 'GOOG',  # Primary symbol to test (GOOG or NVDA)
    'start_date': datetime.datetime(2020, 1, 1),
    'end_date': datetime.datetime(2024, 1, 1),
    
    # Backtest settings
    'initial_cash': 100000.0,
    'commission': 0.001,  # 0.1% per trade
    'slippage': 0.0005,   # 0.05% slippage
    
    # Strategy parameters
    'strategy_params': {
        'bb_period': 20,           # Bollinger Band period
        'bb_dev': 2.0,             # Standard deviations for bands
        'stop_loss_pct': 0.03,     # 3% stop loss
        'position_size_pct': 0.95, # Use 95% of available cash
        'printlog': False,         # Set to False to reduce output noise
    },
    
    # Optimization parameters
    'optimize': False,
    'optimization_params': {
        'bb_period': range(15, 31, 5),      # Test periods: 15, 20, 25, 30
        'bb_dev': [1.5, 2.0, 2.5],          # Test deviations
        'stop_loss_pct': [0.02, 0.03, 0.05], # Test stop losses: 2%, 3%, 5%
    },
    
    # Output settings
    'save_results': True,
    'results_dir': 'test1',
    'plot_results': False,  # Set to False during optimization
}


# ==================== STRATEGY DEFINITION ====================

class BollingerBandBreakout(bt.Strategy):
    """
    Bollinger Band Breakout Strategy
    
    Entry: Price breaks above upper Bollinger Band
    Exit: Price crosses below middle band OR stop loss triggered
    """
    
    params = (
        ('bb_period', 20),
        ('bb_dev', 2.0),
        ('stop_loss_pct', 0.03),
        ('position_size_pct', 0.95),
        ('printlog', True),
    )
    
    def __init__(self):
        """Initialize strategy indicators and variables."""
        # Keep reference to close price
        self.dataclose = self.datas[0].close
        
        # Track pending orders and positions
        self.order = None
        self.buy_price = None
        self.buy_comm = None
        
        # Add Bollinger Bands indicator
        self.bbands = bt.indicators.BollingerBands(
            self.datas[0],
            period=self.params.bb_period,
            devfactor=self.params.bb_dev
        )
        
        # Store references for easier access
        self.top_band = self.bbands.top
        self.mid_band = self.bbands.mid
        self.bot_band = self.bbands.bot
        
        # Additional indicators for context
        self.rsi = bt.indicators.RSI(self.datas[0], period=14)
        self.volume_sma = bt.indicators.SimpleMovingAverage(
            self.datas[0].volume, 
            period=20
        )
        
        logger.info(f"Strategy initialized with bb_period={self.params.bb_period}, "
                   f"bb_dev={self.params.bb_dev}, stop_loss={self.params.stop_loss_pct}")
    
    def notify_order(self, order):
        """Receive notification of order status changes."""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
                self.buy_comm = order.executed.comm
                self.log(
                    f'BUY EXECUTED - Price: {order.executed.price:.2f}, '
                    f'Size: {order.executed.size}, '
                    f'Cost: {order.executed.value:.2f}, '
                    f'Commission: {order.executed.comm:.2f}'
                )
            elif order.issell():
                self.log(
                    f'SELL EXECUTED - Price: {order.executed.price:.2f}, '
                    f'Size: {order.executed.size}, '
                    f'Cost: {order.executed.value:.2f}, '
                    f'Commission: {order.executed.comm:.2f}'
                )
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order Canceled/Margin/Rejected: {order.status}')
        
        self.order = None
    
    def notify_trade(self, trade):
        """Receive notification when a trade is closed."""
        if not trade.isclosed:
            return
        
        self.log(f'TRADE PROFIT - Gross: {trade.pnl:.2f}, Net: {trade.pnlcomm:.2f}')
    
    def next(self):
        """
        Main strategy logic - called for each bar.
        """
        self.log(f'Close: {self.dataclose[0]:.2f}, BB Top: {self.top_band[0]:.2f}, '
                f'BB Mid: {self.mid_band[0]:.2f}, BB Bot: {self.bot_band[0]:.2f}')
        
        # Check if an order is pending
        if self.order:
            return
        
        # Check if we are in the market
        if not self.position:
            # Not in market - look for breakout BUY signal
            # Buy when price breaks above upper Bollinger Band
            if self.dataclose[0] > self.top_band[0]:
                # Additional confirmation: volume above average (optional)
                # We'll keep it simple for now
                
                # Calculate position size
                cash = self.broker.getcash()
                size = int((cash * self.params.position_size_pct) / self.dataclose[0])
                
                if size > 0:
                    self.log(f'BUY SIGNAL - Breakout above BB - Size: {size}')
                    self.order = self.buy(size=size)
        
        else:
            # In market - check exit conditions
            
            # Exit signal 1: Price crosses below middle Bollinger Band
            if self.dataclose[0] < self.mid_band[0]:
                self.log(f'SELL SIGNAL - Price below middle BB')
                self.order = self.sell(size=self.position.size)
            
            # Exit signal 2: Stop loss check
            elif self.buy_price:
                loss_pct = (self.dataclose[0] - self.buy_price) / self.buy_price
                if loss_pct <= -self.params.stop_loss_pct:
                    self.log(f'STOP LOSS TRIGGERED - Loss: {loss_pct*100:.2f}%')
                    self.order = self.sell(size=self.position.size)
    
    def log(self, txt, dt=None):
        """Logging function for strategy."""
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()} - {txt}')
    
    def stop(self):
        """Called when backtest is finished."""
        self.log(
            f'Strategy Finished - BB Period: {self.params.bb_period}, '
            f'BB Dev: {self.params.bb_dev}, '
            f'Stop Loss: {self.params.stop_loss_pct}, '
            f'Final Portfolio Value: {self.broker.getvalue():.2f}',
            dt=None
        )


# ==================== DATA LOADING ====================

def load_data(config):
    """
    Load and prepare data for backtesting from local CSV files.
    
    Args:
        config: Configuration dictionary
    
    Returns:
        Backtrader data feed
    """
    symbol = config.get('symbol', 'GOOG')
    logger.info(f"Loading data for {symbol} from local CSV files")
    
    # Find the appropriate data file for the symbol
    data_file = None
    for file_path in config['data_files']:
        if symbol in file_path:
            data_file = file_path
            break
    
    if not data_file:
        # Default to first file if symbol not found
        data_file = config['data_files'][0]
        logger.warning(f"Symbol {symbol} not found in file list, using {data_file}")
    
    # Read CSV file
    logger.info(f"Reading data from {data_file}")
    df = pd.read_csv(data_file)
    
    # Parse dates
    df['date'] = pd.to_datetime(df['date'], utc=True)
    # Remove timezone information to avoid compatibility issues
    df['date'] = df['date'].dt.tz_localize(None)
    df.set_index('date', inplace=True)
    
    # Filter for the symbol (in case multiple symbols in one file)
    if 'symbol' in df.columns:
        df = df[df['symbol'] == symbol].copy()
        logger.info(f"Filtered for symbol: {symbol}")
    
    # Filter date range
    if config.get('start_date'):
        df = df[df.index >= config['start_date']]
    if config.get('end_date'):

        df = df[df.index <= config['end_date']]
    
    logger.info(f"Data loaded: {len(df)} rows from {df.index.min()} to {df.index.max()}")
    
    # Create Backtrader data feed
    data = bt.feeds.PandasData(dataname=df)
    
    return data


# ==================== BACKTEST EXECUTION ====================

def run_backtest(config, optimize=False):
    """
    Execute backtest with given configuration.
    
    Args:
        config: Configuration dictionary
        optimize: If True, run optimization instead of single backtest
    
    Returns:
        Cerebro instance with results
    """
    logger.info("=" * 80)
    logger.info(f"Starting Backtest - {'OPTIMIZATION MODE' if optimize else 'SINGLE RUN MODE'}")
    logger.info("=" * 80)
    
    # Create cerebro instance
    cerebro = bt.Cerebro()
    
    # Add strategy
    if optimize:
        logger.info("Running parameter optimization...")
        cerebro.optstrategy(
            BollingerBandBreakout,
            bb_period=config['optimization_params']['bb_period'],
            bb_dev=config['optimization_params']['bb_dev'],
            stop_loss_pct=config['optimization_params']['stop_loss_pct'],
            printlog=False  # Disable logging during optimization
        )
    else:
        cerebro.addstrategy(
            BollingerBandBreakout,
            **config['strategy_params']
        )
    
    # Load and add data
    data = load_data(config)
    cerebro.adddata(data)
    
    # Set initial cash
    cerebro.broker.setcash(config['initial_cash'])
    logger.info(f"Initial Portfolio Value: ${config['initial_cash']:,.2f}")
    
    # Set commission
    cerebro.broker.setcommission(commission=config['commission'])
    logger.info(f"Commission: {config['commission']*100}%")
    
    # Add analyzers
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.02)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.SQN, _name='sqn')  # System Quality Number
    
    # Run backtest
    logger.info("\nRunning backtest...\n")
    results = cerebro.run()
    
    if not optimize:
        # Print detailed results for single run
        print_results(cerebro, results[0], config)
        
        # Plot if requested
        if config.get('plot_results', False):
            logger.info("\nGenerating plots...")
            cerebro.plot(style='candlestick', barup='green', bardown='red')
    else:
        # Print optimization results
        print_optimization_results(results, config)
    
    return cerebro, results


def print_results(cerebro, strat, config):
    """Print detailed backtest results."""
    logger.info("=" * 80)
    logger.info("BACKTEST RESULTS")
    logger.info("=" * 80)
    
    # Basic performance
    final_value = cerebro.broker.getvalue()
    total_return = ((final_value - config['initial_cash']) / config['initial_cash']) * 100
    
    print(f"\n{'='*80}")
    print(f"FINAL RESULTS")
    print(f"{'='*80}")
    print(f"Initial Portfolio Value:  ${config['initial_cash']:,.2f}")
    print(f"Final Portfolio Value:    ${final_value:,.2f}")
    print(f"Total Return:             {total_return:.2f}%")
    print(f"Profit/Loss:              ${final_value - config['initial_cash']:,.2f}")
    
    # Sharpe Ratio
    sharpe = strat.analyzers.sharpe.get_analysis()
    sharpe_ratio = sharpe.get('sharperatio', None)
    print(f"\nSharpe Ratio:             {sharpe_ratio if sharpe_ratio else 'N/A'}")
    
    # Drawdown
    drawdown = strat.analyzers.drawdown.get_analysis()
    max_dd = drawdown.get('max', {}).get('drawdown', 0)
    print(f"Max Drawdown:             {max_dd:.2f}%")
    
    # Returns
    returns = strat.analyzers.returns.get_analysis()
    annual_return = returns.get('rnorm100', 0)
    print(f"Annualized Return:        {annual_return:.2f}%")
    
    # SQN (System Quality Number)
    sqn_analysis = strat.analyzers.sqn.get_analysis()
    sqn = sqn_analysis.get('sqn', None)
    print(f"SQN (System Quality):     {sqn if sqn else 'N/A'}")
    
    # Trade statistics
    trades = strat.analyzers.trades.get_analysis()
    total_trades = trades.get('total', {}).get('total', 0)
    won_trades = trades.get('won', {}).get('total', 0)
    lost_trades = trades.get('lost', {}).get('total', 0)
    
    print(f"\n{'='*80}")
    print(f"TRADE STATISTICS")
    print(f"{'='*80}")
    print(f"Total Trades:             {total_trades}")
    
    if total_trades > 0:
        win_rate = (won_trades / total_trades) * 100
        print(f"Winning Trades:           {won_trades}")
        print(f"Losing Trades:            {lost_trades}")
        print(f"Win Rate:                 {win_rate:.2f}%")
        
        # Profit/Loss details
        if won_trades > 0:
            avg_win = trades.get('won', {}).get('pnl', {}).get('average', 0)
            print(f"Average Win:              ${avg_win:.2f}")
        
        if lost_trades > 0:
            avg_loss = trades.get('lost', {}).get('pnl', {}).get('average', 0)
            print(f"Average Loss:             ${avg_loss:.2f}")
        
        # Profit factor
        gross_profit = trades.get('won', {}).get('pnl', {}).get('total', 0)
        gross_loss = abs(trades.get('lost', {}).get('pnl', {}).get('total', 0))
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
            print(f"Profit Factor:            {profit_factor:.2f}")
    
    print(f"{'='*80}\n")


def print_optimization_results(results, config):
    """Print optimization results sorted by final portfolio value."""
    logger.info("=" * 80)
    logger.info("OPTIMIZATION RESULTS")
    logger.info("=" * 80)
    
    # Collect results
    opt_results = []
    for result in results:
        strat = result[0]
        params = {
            'bb_period': strat.params.bb_period,
            'bb_dev': strat.params.bb_dev,
            'stop_loss_pct': strat.params.stop_loss_pct,
        }
        
        # Extract returns from analyzer instead of accessing broker
        returns_analyzer = strat.analyzers.returns.get_analysis()
        total_return = returns_analyzer.get('rtot', 0) * 100  # Convert to percentage
        final_value = config['initial_cash'] * (1 + returns_analyzer.get('rtot', 0))
        
        # Get analyzer results
        sharpe = strat.analyzers.sharpe.get_analysis()
        sharpe_ratio = sharpe.get('sharperatio', None)
        
        drawdown = strat.analyzers.drawdown.get_analysis()
        max_dd = drawdown.get('max', {}).get('drawdown', 0)
        
        trades = strat.analyzers.trades.get_analysis()
        total_trades = trades.get('total', {}).get('total', 0)
        won_trades = trades.get('won', {}).get('total', 0)
        win_rate = (won_trades / total_trades * 100) if total_trades > 0 else 0
        
        opt_results.append({
            'params': params,
            'final_value': final_value,
            'return_pct': total_return,
            'sharpe': sharpe_ratio,
            'max_dd': max_dd,
            'total_trades': total_trades,
            'win_rate': win_rate
        })
    
    # Sort by return percentage
    opt_results.sort(key=lambda x: x['return_pct'], reverse=True)
    
    # Print top 10 results
    print(f"\n{'='*80}")
    print(f"TOP 10 PARAMETER COMBINATIONS (Sorted by Return %)")
    print(f"{'='*80}\n")
    
    for i, res in enumerate(opt_results[:10], 1):
        params = res['params']
        print(f"Rank #{i}")
        print(f"  Parameters: BB Period={params['bb_period']}, BB Dev={params['bb_dev']}, "
              f"Stop Loss={params['stop_loss_pct']*100:.1f}%")
        print(f"  Final Value: ${res['final_value']:,.2f}")
        print(f"  Return: {res['return_pct']:.2f}%")
        print(f"  Sharpe Ratio: {res['sharpe'] if res['sharpe'] else 'N/A'}")
        print(f"  Max Drawdown: {res['max_dd']:.2f}%")
        print(f"  Total Trades: {res['total_trades']}, Win Rate: {res['win_rate']:.2f}%")
        print()
    
    # Print best parameters
    best = opt_results[0]
    print(f"{'='*80}")
    print(f"RECOMMENDED PARAMETERS")
    print(f"{'='*80}")
    print(f"BB Period:      {best['params']['bb_period']}")
    print(f"BB Deviation:   {best['params']['bb_dev']}")
    print(f"Stop Loss:      {best['params']['stop_loss_pct']*100:.1f}%")
    print(f"{'='*80}\n")


# ==================== MAIN EXECUTION ====================

if __name__ == '__main__':
    try:
        # Step 1: Run initial backtest with default parameters
        print("\n" + "="*80)
        print("STEP 1: RUNNING BACKTEST WITH DEFAULT PARAMETERS")
        print("="*80 + "\n")
        
        cerebro, results = run_backtest(CONFIG, optimize=False)
        logger.info("\n✓ Initial backtest completed successfully!\n")
        
        # Step 2: Run optimization
        print("\n" + "="*80)
        print("STEP 2: RUNNING PARAMETER OPTIMIZATION")
        print("="*80 + "\n")
        
        CONFIG['optimize'] = True
        CONFIG['plot_results'] = False  # Disable plotting during optimization
        cerebro_opt, results_opt = run_backtest(CONFIG, optimize=True)
        logger.info("\n✓ Optimization completed successfully!\n")
        
    except Exception as e:
        logger.error(f"\n✗ Backtest failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
