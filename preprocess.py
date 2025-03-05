from torch.utils.data import DataLoader, TensorDataset

def preprocess_data(label_X, target_y):
    preprocessed = TensorDataset(label_X, target_y)
    return preprocessed

def dataloader(dataset, batch_size, shuffle, num_workers):
    dataloader = DataLoader(dataset=dataset, batch_size=batch_size, shuffle=shuffle, num_workers=num_workers)
    return dataloader
