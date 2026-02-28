"""
Backtest Template for Algorithmic Trading Strategies

This template provides a standardized structure for backtesting trading strategies
using the Backtrader framework. It includes:

- Data loading and preparation
- Strategy definition with clear logic separation
- Risk management (position sizing, stop-loss)
- Transaction cost modeling
- Performance analysis and visualization
- Results export

Usage:
    1. Define your strategy logic in the Strategy class
    2. Configure parameters in the CONFIG section
    3. Run the script: python test_template.py
    4. Review results and visualizations

Adapt this template for your specific strategy by modifying the Strategy class.
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
    # Data settings
    'data_file': 'datasets/historical_data.csv',  # Path to your data file
    'symbol': 'AAPL',  # Symbol to backtest (if multiple in file)
    'start_date': datetime.datetime(2020, 1, 1),
    'end_date': datetime.datetime(2024, 1, 1),
    
    # Backtest settings
    'initial_cash': 100000.0,
    'commission': 0.001,  # 0.1% per trade
    'slippage': 0.0005,   # 0.05% slippage
    
    # Strategy parameters
    'strategy_params': {
        'fast_period': 20,
        'slow_period': 50,
        'stop_loss_pct': 0.02,  # 2% stop loss
        'position_size_pct': 0.95,  # Use 95% of available cash
    },
    
    # Output settings
    'save_results': True,
    'results_file': 'backtest_results.csv',
    'plot_results': True,
}


# ==================== STRATEGY DEFINITION ====================

class MovingAverageCrossStrategy(bt.Strategy):
    """
    Simple Moving Average Crossover Strategy
    
    Entry Rules:
    - Buy when fast MA crosses above slow MA
    - Close position when fast MA crosses below slow MA
    
    Risk Management:
    - Position sizing based on available capital
    - Stop loss at specified percentage
    
    Customize this strategy by modifying the __init__, next, and notify_order methods.
    """
    
    params = (
        ('fast_period', 20),
        ('slow_period', 50),
        ('stop_loss_pct', 0.02),
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
        
        # Add indicators
        self.fast_ma = bt.indicators.SimpleMovingAverage(
            self.datas[0],
            period=self.params.fast_period
        )
        self.slow_ma = bt.indicators.SimpleMovingAverage(
            self.datas[0],
            period=self.params.slow_period
        )
        
        # Crossover signal
        self.crossover = bt.indicators.CrossOver(self.fast_ma, self.slow_ma)
        
        # Additional indicators for analysis
        self.rsi = bt.indicators.RSI(self.datas[0])
        
        logger.info(f"Strategy initialized with fast_period={self.params.fast_period}, "
                   f"slow_period={self.params.slow_period}")
    
    def notify_order(self, order):
        """Receive notification of order status changes."""
        if order.status in [order.Submitted, order.Accepted]:
            # Order submitted/accepted - no action required
            return
        
        # Check if order completed
        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
                self.buy_comm = order.executed.comm
                self.log(
                    f'BUY EXECUTED - Price: {order.executed.price:.2f}, '
                    f'Cost: {order.executed.value:.2f}, '
                    f'Commission: {order.executed.comm:.2f}'
                )
            elif order.issell():
                self.log(
                    f'SELL EXECUTED - Price: {order.executed.price:.2f}, '
                    f'Cost: {order.executed.value:.2f}, '
                    f'Commission: {order.executed.comm:.2f}'
                )
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order Canceled/Margin/Rejected: {order.status}')
        
        # Reset order
        self.order = None
    
    def notify_trade(self, trade):
        """Receive notification when a trade is closed."""
        if not trade.isclosed:
            return
        
        self.log(f'TRADE PROFIT - Gross: {trade.pnl:.2f}, Net: {trade.pnlcomm:.2f}')
    
    def next(self):
        """
        Main strategy logic - called for each bar.
        
        Implement your strategy rules here.
        """
        # Log current price
        self.log(f'Close: {self.dataclose[0]:.2f}')
        
        # Check if an order is pending
        if self.order:
            return
        
        # Check if we are in the market
        if not self.position:
            # Not in market - look for buy signal
            if self.crossover > 0:  # Fast MA crossed above slow MA
                # Calculate position size
                cash = self.broker.getcash()
                size = int((cash * self.params.position_size_pct) / self.dataclose[0])
                
                if size > 0:
                    self.log(f'BUY SIGNAL - Size: {size}')
                    # Keep order reference to avoid duplicate orders
                    self.order = self.buy(size=size)
        
        else:
            # In market - check exit conditions
            
            # Exit signal: Fast MA crosses below slow MA
            if self.crossover < 0:
                self.log(f'SELL SIGNAL - Closing position')
                self.order = self.sell(size=self.position.size)
            
            # Stop loss check
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
            f'Strategy Finished - Fast: {self.params.fast_period}, '
            f'Slow: {self.params.slow_period}, '
            f'Final Portfolio Value: {self.broker.getvalue():.2f}',
            dt=None
        )


# ==================== DATA LOADING ====================

def load_data(config):
    """
    Load and prepare data for backtesting.
    
    Args:
        config: Configuration dictionary
    
    Returns:
        Backtrader data feed
    """
    logger.info(f"Loading data from {config['data_file']}")
    
    # Load data from CSV
    df = pd.read_csv(config['data_file'])
    
    # Filter for specific symbol if needed
    if 'symbol' in df.columns and config.get('symbol'):
        df = df[df['symbol'] == config['symbol']].copy()
        logger.info(f"Filtered for symbol: {config['symbol']}")
    
    # Ensure date column is datetime
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
    
    # Standardize column names (Backtrader expects: open, high, low, close, volume)
    column_mapping = {
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'volume': 'volume'
    }
    
    df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
    
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

def run_backtest(config):
    """
    Execute backtest with given configuration.
    
    Args:
        config: Configuration dictionary
    
    Returns:
        Cerebro instance with results
    """
    logger.info("=" * 60)
    logger.info("Starting Backtest")
    logger.info("=" * 60)
    
    # Create cerebro instance
    cerebro = bt.Cerebro()
    
    # Add strategy
    cerebro.addstrategy(
        MovingAverageCrossStrategy,
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
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    
    # Run backtest
    logger.info("\nRunning backtest...\n")
    results = cerebro.run()
    
    # Get strategy instance
    strat = results[0]
    
    # Print results
    logger.info("=" * 60)
    logger.info("Backtest Results")
    logger.info("=" * 60)
    
    final_value = cerebro.broker.getvalue()
    total_return = ((final_value - config['initial_cash']) / config['initial_cash']) * 100
    
    logger.info(f"Final Portfolio Value: ${final_value:,.2f}")
    logger.info(f"Total Return: {total_return:.2f}%")
    
    # Sharpe Ratio
    sharpe = strat.analyzers.sharpe.get_analysis()
    logger.info(f"Sharpe Ratio: {sharpe.get('sharperatio', 'N/A')}")
    
    # Drawdown
    drawdown = strat.analyzers.drawdown.get_analysis()
    logger.info(f"Max Drawdown: {drawdown.get('max', {}).get('drawdown', 'N/A'):.2f}%")
    
    # Returns
    returns = strat.analyzers.returns.get_analysis()
    logger.info(f"Annualized Return: {returns.get('rnorm100', 'N/A'):.2f}%")
    
    # Trade stats
    trades = strat.analyzers.trades.get_analysis()
    total_trades = trades.get('total', {}).get('total', 0)
    won_trades = trades.get('won', {}).get('total', 0)
    lost_trades = trades.get('lost', {}).get('total', 0)
    
    logger.info(f"\nTotal Trades: {total_trades}")
    if total_trades > 0:
        win_rate = (won_trades / total_trades) * 100
        logger.info(f"Won: {won_trades}, Lost: {lost_trades}, Win Rate: {win_rate:.2f}%")
    
    logger.info("=" * 60)
    
    # Plot if requested
    if config.get('plot_results', True):
        logger.info("\nGenerating plots...")
        cerebro.plot(style='candlestick', barup='green', bardown='red')
    
    return cerebro, results


# ==================== MAIN EXECUTION ====================

if __name__ == '__main__':
    try:
        cerebro, results = run_backtest(CONFIG)
        logger.info("\n✓ Backtest completed successfully!")
    except Exception as e:
        logger.error(f"\n✗ Backtest failed: {str(e)}")
        raise