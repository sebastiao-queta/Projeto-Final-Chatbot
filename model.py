import torch
from torch import nn


class CustomRNNModel(nn.Module):
    def __init__(self, input_dim=1080, hidden_dim=240, output_dim=24, num_layers=1, activation='relu'):
        super(CustomRNNModel, self).__init__()
        self.recurrent_layer = nn.RNN(input_size=input_dim, hidden_size=hidden_dim,
                                      num_layers=num_layers, nonlinearity=activation, bias=True)
        self.fc_layer = nn.Linear(hidden_dim, output_dim)
    def forward(self, input_tensor):
        rnn_output, hidden_state = self.recurrent_layer(input_tensor)
        #print("RNN Output Shape:", rnn_output.shape)
        #print("Hidden State Shape:", hidden_state.shape)

        output = self.fc_layer(rnn_output)
        return output
