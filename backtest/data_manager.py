"""
数据管理模块
负责期货数据的加载、处理和更新
"""

import os
import sys
import pandas as pd
import backtrader as bt
from datetime import datetime

# 将项目根目录加入路径，以便调用 update.py
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)


class SAWeightedData(bt.feeds.PandasData):
    """
    SA加权数据 Feed，基于 PandasData 适配 SA_weighted.csv 格式
    列：date, open, high, low, close, settle, oi, volume

    额外自定义 line：
      data.settle  - 结算价
    内置 line 映射：
      openinterest → oi 列
    """
    # 额外添加 settle 自定义 line；oi 映射到内置 openinterest 即可
    lines = ('settle',)

    params = (
        ('datetime',     None),      # 索引即为日期
        ('open',         'open'),
        ('high',         'high'),
        ('low',          'low'),
        ('close',        'close'),
        ('volume',       'volume'),
        ('openinterest', 'oi'),      # 内置 openinterest line 读取 oi 列
        ('settle',       'settle'),  # 自定义 settle line
    )


class DataManager:
    """
    数据管理器
    负责加载、过滤、更新期货加权数据
    """

    DATA_DIR = os.path.join(ROOT_DIR, 'data')

    def __init__(self, symbol: str = 'SA', update: bool = False):
        """
        Parameters
        ----------
        symbol : str
            品种代码，例如 'SA'
        update : bool
            是否从交易所重新下载并更新数据
        """
        self.symbol = symbol
        self.weighted_path = os.path.join(self.DATA_DIR, f'{symbol}_weighted.csv')

        if update:
            self._update_data()

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _update_data(self):
        """调用 update.py 中的 DataUpdate 重新下载并生成加权数据"""
        try:
            from update import DataUpdate
            print(f"[DataManager] 正在更新 {self.symbol} 数据...")
            updater = DataUpdate(self.symbol)
            updater.update()
            print(f"[DataManager] {self.symbol} 数据更新完毕，路径：{self.weighted_path}")
        except Exception as e:
            print(f"[DataManager] 数据更新失败：{e}")
            raise

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    def load_dataframe(
        self,
        start_date: str = None,
        end_date: str = None,
    ) -> pd.DataFrame:
        """
        加载加权 CSV 数据，返回按日期过滤后的 DataFrame

        Parameters
        ----------
        start_date : str, optional
            开始日期，格式 'YYYY-MM-DD'
        end_date : str, optional
            结束日期，格式 'YYYY-MM-DD'

        Returns
        -------
        pd.DataFrame
            列：date(index), open, high, low, close, settle, oi, volume
        """
        if not os.path.exists(self.weighted_path):
            raise FileNotFoundError(
                f"加权数据文件不存在：{self.weighted_path}\n"
                "请先运行 update.py 或将 update=True 传入 DataManager"
            )

        df = pd.read_csv(self.weighted_path, parse_dates=['date'])
        df.set_index('date', inplace=True)
        df.sort_index(inplace=True)

        # 日期过滤
        if start_date:
            df = df[df.index >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df.index <= pd.to_datetime(end_date)]

        if df.empty:
            raise ValueError(
                f"过滤后数据为空，请检查日期范围 [{start_date}, {end_date}] "
                f"是否在数据区间内"
            )

        return df

    def get_bt_feed(
        self,
        start_date: str = None,
        end_date: str = None,
    ) -> SAWeightedData:
        """
        返回可直接传入 backtrader Cerebro 的数据 Feed

        Parameters
        ----------
        start_date : str, optional
        end_date : str, optional

        Returns
        -------
        SAWeightedData
        """
        df = self.load_dataframe(start_date, end_date)
        feed = SAWeightedData(dataname=df)
        return feed

    def get_raw_dataframe(self) -> pd.DataFrame:
        """返回未过滤的完整加权 DataFrame（用于绘图等）"""
        return self.load_dataframe()
