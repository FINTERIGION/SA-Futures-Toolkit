import pandas as pd
import urllib.request
from datetime import datetime
import os
import shutil

class DataUpdate:
    def __init__(self, category:str):
        self.map_category = {
            'SA': ('CZCE', 2019),
        }
        self.category = category
        self.exchange = self.map_category[category][0]
        self.start_year = self.map_category[category][1]
        self.year = int(datetime.now().strftime('%Y'))

    def update(self):
        '''
        Update data from the exchange.
        '''
        if self.exchange == 'CZCE':
            # Create directory if it does not exist
            if not os.path.exists('cache'):
                os.makedirs('cache')
            if not os.path.exists('data'):
                os.makedirs('data')
            
            # Download data from exchange
            for year in range(self.start_year, self.year + 1):
                url = f"http://www.czce.com.cn/cn/DFSStaticFiles/Future/{year}/FutureDataAllHistory/{self.category}FUTURES{year}.txt"
                if year < 2020:
                    url = f"http://www.czce.com.cn/cn/DFSStaticFiles/Future/{year}/FutureDataAllHistory/{self.category}.txt"
                path = f"cache/{self.category}{year}.txt"
                try:
                    urllib.request.urlretrieve(url, path)
                    print(f"{self.category}{year} Update Done.")
                except (urllib.error.HTTPError, urllib.error.URLError):
                    print(f"{self.category}{year} Update Error.")
            
            # Merge data from cache folder
            all_data = []
            for year in range(self.start_year, self.year + 1):
                path = f"cache/{self.category}{year}.txt"
                if not os.path.exists(path):
                    print(f"Warning: {path} does not exist, skipping ...")
                    continue
                df = pd.read_csv(path, sep='|', skiprows=2, header=None)
                columns = ['date', 'contract', 'prev_settle', 'open', 'high', 'low', 'close', 'settle', 'change1', 'change2', 'volume', 'oi', 'oi_change', 'turnover', 'delivery_settle']
                if len(df.columns) >= len(columns):
                    df.columns = columns + [f'unknown_{i}' for i in range(len(df.columns) - len(columns))]
                else:
                    df.columns = columns[:len(df.columns)]
                all_data.append(df)
            data = pd.concat(all_data, ignore_index=True)
            
            # Wash data and save csv file
            data = data.map(lambda x: x.strip() if isinstance(x, str) else x)
            data = data.map(lambda x: x.replace(',', '') if isinstance(x, str) else x)
            for col in data.columns:
                try:
                    data[col] = pd.to_numeric(data[col])
                except (ValueError, TypeError):
                    pass
            data = data[['date', 'contract', 'open', 'high', 'low', 'close', 'oi', 'volume', 'settle']]
            data.to_csv(f"data/{self.category}.csv", index=False)
            
            # Calculate weighted data
            weighted_data = data.dropna(subset=['oi', 'volume', 'open', 'high', 'low', 'close', 'settle'])
            weighted_data = weighted_data[(weighted_data['oi'] > 0) & (weighted_data['volume'] > 0)]
            grouped = weighted_data.groupby('date')
            weighted_result = pd.DataFrame()
            weighted_result['date'] = grouped['date'].first()
            weighted_result['open'] = grouped.apply(lambda x: (x['open'] * x['oi']).sum() / x['oi'].sum())
            weighted_result['high'] = grouped.apply(lambda x: (x['high'] * x['oi']).sum() / x['oi'].sum())
            weighted_result['low'] = grouped.apply(lambda x: (x['low'] * x['oi']).sum() / x['oi'].sum())
            weighted_result['close'] = grouped.apply(lambda x: (x['close'] * x['oi']).sum() / x['oi'].sum())
            weighted_result['settle'] = grouped.apply(lambda x: (x['settle'] * x['oi']).sum() / x['oi'].sum())
            weighted_result['oi'] = grouped['oi'].sum()
            weighted_result['volume'] = grouped['volume'].sum()
            weighted_result.to_csv(f"data/{self.category}_weighted.csv", index=False)
            
            # Clean up cache folder
            if os.path.exists('cache'):
                shutil.rmtree('cache')
                print("Cache folder cleaned up.")

            return data
