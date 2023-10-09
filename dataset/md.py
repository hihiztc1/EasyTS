import logging
from dataset.utils_dataset import download
import pandas as pd
import os
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
from utils.timefeatures import time_features

import warnings
warnings.filterwarnings('ignore')

SubDataset = ['live_huya_shixu.csv', 'FOOD1.csv', 'FOOD2.csv', 'FOOD3.csv', 'MANU1.csv', 'PHAR1.csv', 'PHAR2.csv', 'OFFICE1.csv']
URL_TEMPLATE = 'http://gitlab.fei8s.com/tianchengZhang/dastaset-for-timeseries/-/raw/main/MD/{}.csv'
logging.basicConfig(level=logging.DEBUG)

# Inherit Dataset
class Dataset_MD(Dataset):
    def __init__(self, data_path, size, flag='train',
                 features='S', target='OT', scale=True, timeenc=0, freq='5min'):

        # size [seq_len, label_len, pred_len]
        self.seq_len = size[0]
        self.label_len = size[1]
        self.pred_len = size[2]

        # Set Task Type
        assert flag in ['train', 'test', 'val']
        type_map = {'train': 0, 'val': 1, 'test': 2}
        self.set_type = type_map[flag]

        self.features = features
        self.target = target
        self.scale = scale
        self.timeenc = timeenc
        self.freq = freq
        self.data_path = data_path

        self.__read_data__()

    def __read_data__(self):
        self.scaler = StandardScaler()

        df_raw = pd.read_csv(self.data_path)

        # Reorder columns [date, ...features..., target]
        cols = list(df_raw.columns)
        cols.remove(self.target)
        cols.remove('date')
        df_raw = df_raw[['date'] + cols + [self.target]]

        # Partition Dataset
        num_train = int(len(df_raw) * 0.7)
        num_test = int(len(df_raw) * 0.2)
        num_vali = len(df_raw) - num_train - num_test
        border1s = [0, num_train - self.seq_len, len(df_raw) - num_test - self.seq_len]
        border2s = [num_train, num_train + num_vali, len(df_raw)]
        border1 = border1s[self.set_type]
        border2 = border2s[self.set_type]

        if self.features == 'M' or self.features == 'MS':
            cols_data = df_raw.columns[1:]
            df_data = df_raw[cols_data]
        elif self.features == 'S':
            df_data = df_raw[[self.target]]

        # Standardization
        if self.scale:
            train_data = df_data[border1s[0]:border2s[0]]
            self.scaler.fit(train_data.values)
            data = self.scaler.transform(df_data.values)
        else:
            data = df_data.values

        # Processing timestamp
        df_stamp = df_raw[['date']][border1:border2]
        df_stamp['date'] = pd.to_datetime(df_stamp.date)
        if self.timeenc == 0:
            df_stamp['month'] = df_stamp.date.apply(lambda row: row.month, 1)
            df_stamp['day'] = df_stamp.date.apply(lambda row: row.day, 1)
            df_stamp['weekday'] = df_stamp.date.apply(lambda row: row.weekday(), 1)
            df_stamp['hour'] = df_stamp.date.apply(lambda row: row.hour, 1)
            data_stamp = df_stamp.drop(['date'], 1).values
        elif self.timeenc == 1:
            data_stamp = time_features(pd.to_datetime(df_stamp['date'].values), freq=self.freq)
            data_stamp = data_stamp.transpose(1, 0)

        self.data_x = data[border1:border2]
        self.data_y = data[border1:border2]
        self.data_stamp = data_stamp

    def __getitem__(self, index):
        s_begin = index
        s_end = s_begin + self.seq_len
        r_begin = s_end - self.label_len
        r_end = r_begin + self.label_len + self.pred_len

        seq_x = self.data_x[s_begin:s_end]
        seq_y = self.data_y[r_begin:r_end]
        seq_x_mark = self.data_stamp[s_begin:s_end]
        seq_y_mark = self.data_stamp[r_begin:r_end]

        return seq_x, seq_y, seq_x_mark, seq_y_mark

    def __len__(self):
        return len(self.data_x) - self.seq_len - self.pred_len + 1

    def inverse_transform(self, data):
        return self.scaler.inverse_transform(data)

    @staticmethod
    def download(data_path, dataset_path="./MD"):
        """
        Download MD dataset if doesn't exist.
        """
        if not os.path.isdir(dataset_path):
            os.makedirs(dataset_path)
            logging.info(f' {dataset_path} does not exist, creation successful.')
        assert data_path in SubDataset
        URL_TEMPLATE = 'http://gitlab.fei8s.com/tianchengZhang/dastaset-for-timeseries/-/raw/main/MD/{}'
        URL = URL_TEMPLATE.format(data_path)
        FILE_PATH = os.path.join(dataset_path, data_path)

        download(URL, FILE_PATH)

        return FILE_PATH

#
def data_provider_md(args, flag):
    """
    Provide MD data. list:['FOOD1','FOOD2','FOOD3','MANU1','PHAR1','PHAR2','OFFICE1']
    """
    timeenc = 0 if args.embed != 'timeF' else 1

    if flag == 'test':
        shuffle_flag = False
        drop_last = True
        batch_size = args.batch_size
        freq = args.freq
    elif flag == 'train':
        shuffle_flag = True
        drop_last = True
        batch_size = args.batch_size
        freq = args.freq

    data_set = Dataset_MD(
        dataset_path=args.dataset_path,
        data_path=args.data_path,
        size=[args.seq_len, args.label_len, args.pred_len],
        flag=flag,
        features=args.features,
        target=args.target,
        timeenc=timeenc,
        freq=freq
    )
    print(flag, len(data_set))
    data_loader = DataLoader(
        data_set,
        batch_size=batch_size,
        shuffle=shuffle_flag,
        num_workers=args.num_workers,
        drop_last=drop_last)
    return data_set, data_loader

if __name__ == '__main__':
    Dataset_MD.download('FOOD2.csv')
