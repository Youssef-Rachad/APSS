# -*- coding: utf-8 -*-
"""GRID1.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1wAASUR_wn21yPMkA5EaAAWE8VR5HKdN0

### GRU and ANN Training

- Here I am going to experiment on the 3bp sequences
- again, I want to see if overfitting can occur
- I am using balancing, and am taking only positive non zero parts of the dataset for now

AUTHORS: Youssef Rachad
DATE: 03/31/2023
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
from copy import deepcopy

from torch.utils.data.sampler import SubsetRandomSampler

use_cuda = True 
device_id = 0  # choose the GPU device ID you want to use
device = torch.device(f'cuda:{device_id}' if torch.cuda.is_available() and use_cuda else 'cpu')
torch.cuda.set_device(device)

"""#### Importing Batching Functions """

# custome made batching files to feed into our network (in file called batching.py)
from batchingv7 import get_data_matrix, get_data_pairings,convert_alpha_sequence, batching_fcn

# THIS IS WHERE THE DATA FILE IS IN THE FOLDER DOCUMENT
data_file_name = 'FileP04_T4_18h_37C.xlsx'

#importing the file and getting pairing
data_pairings = get_data_pairings(get_data_matrix(data_file_name)) 

import random

norm_pairings = data_pairings

# create imbeddings 
embedded = convert_alpha_sequence(norm_pairings)

from datetime import datetime
from pathlib import Path

def get_abs_percent_error(y_pred, y_actual):
  result = torch.mean(torch.abs((y_actual - y_pred) / y_actual))
  #ipdb.set_trace()
  return result

def get_smape(y_pred, y_actual):
  batch_smape = torch.mean(torch.abs(y_actual - y_pred) / ((torch.abs(y_actual) + torch.abs(y_pred))/2.0))
  # STILL POSSIBILITY THAT BOTH y_pred AND y_actual are 0 (e.g., if our model 
  # makes very good predictions), and therefore get inf% error
  # ==> THINK ABOUT HOW TO FIX THIS MORE PERMANENTLY
  return batch_smape

def plot_losses(iterations, training_loss, validation_loss, path):
    plt.title("Training Curve")
    plt.plot(iterations, training_loss, label="Training")
    plt.plot(iterations, validation_loss, label="Validation")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.legend(loc='best')
    plt.savefig(path)
    plt.clf()

# Note: MAPE is Mean Absolute Percentage Error
def plot_SMAPE(iterations, training_SMAPE, validation_SMAPE, path):
    plt.title("Training Curve - SMAPE")
    plt.plot(iterations, training_SMAPE, label="Training")
    plt.plot(iterations, validation_SMAPE, label="Validation")
    plt.xlabel("Epoch")
    plt.ylabel("Symmetric Mean Average Percent Error")
    plt.legend(loc='best')
    plt.savefig(path)
    plt.clf()

def train(modelGru1, modelGru2, modelAnn, training_set, validation_set, batch_size, num_epochs=5, learning_rate=1e-4, plot=True, path="."):
    '''
    modelGru1 : GRU for analysis of the top sequence
    modelGru2 : GRU for analysis of the bottom sequence
    modelAnn: For classiciation of the hidden state of the GRU
    training_set: Batched [formatted properly] training set
    validation_set: Batched [formatted properly] validation data
    '''

    # using mean squared error loss as this is not a classification problem
    criterion = nn.MSELoss()
    # NOTE: Might need to change depending on how the second model plays a role here
    optimizer = optim.Adam(list(modelGru2.parameters()) +list(modelGru1.parameters()) + list(modelAnn.parameters()), lr= learning_rate) ## insert reference? 

    # recording the data
    training_losses, validation_losses = np.zeros(num_epochs), np.zeros(num_epochs)
    training_SMAPE, validation_SMAPE = np.zeros(num_epochs), np.zeros(num_epochs)
    iterations = range(num_epochs)
    
    date_time = datetime.now().strftime("%m_%d_%H_%M")
    Path(path).mkdir(parents=True, exist_ok=True)
    file_data = open(f"{path}/3bp_{date_time}_model_Gru1_hiddensz{modelGru1.hidden_size}_batchsz{batch_size}_lr{learning_rate}_epoch{num_epochs}_dropout{modelAnn.p}.txt", "a")
    file_data.write(f"Chose learning rate {learning_rate}, number of epochs {num_epoch}, hidden_size {hidden_size}, batch size {batch_size}, dropout {dropout_p}\n")

    for epoch in range(num_epochs):
      # first sequence, second sequence, and then the affinity (ie the label)

      train_total_loss = 0
      val_total_loss = 0
      train_total_error = 0
      val_total_error = 0

      num_train_batches = 0
      num_val_batches = 0

      # TRAINING LOOP
      for seq1, seq2, label in training_set:
        num_train_batches += 1
      
        # Forward pass through the two GRU (applied to the first and second sequency)
        out, h1 = modelGru1(seq1.float().to(device))
        out, h2 = modelGru2(seq2.float().to(device))
        h1, h2 = h1.squeeze(0), h2.squeeze(0)

        # concatenate the hidden output
        h = torch.cat((h1, h2), dim=1).to(device)

        # Forward pass through the ANN (which will be 256 inputs)
        y_pred = modelAnn(h).squeeze().to(device)
        # Compute the loss
        loss = criterion(y_pred, label.float().squeeze().to(device))
        train_total_loss += loss.item()
        # ipdb.set_trace() # y_pred.shape: [10000], label.shape: [10000]
        #if y_pred.shape != label.shape:
          #ipdb.set_trace()
        # train_total_error += get_abs_percent_error(y_pred, label.float())
        train_total_error += get_smape(y_pred, label.float().to(device))
 
        # Zero the gradients and perform backpropagation
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        # I am going to only track one of them for ease here
        # print("         True Label: " + str(label) + " Predicted Output: " + str(y_pred))
      
      training_losses[epoch] = train_total_loss/num_train_batches # /
      training_SMAPE[epoch] = train_total_error/num_train_batches


      # VALIDATION LOOP
      for seq1, seq2, label in validation_set:
        num_val_batches += 1
        # Forward pass through the two GRU (applied to the first and second sequency)
        out, h1 = modelGru1(seq1.float().to(device))
        out, h2 = modelGru2(seq2.float().to(device))
        h1, h2 = h1.squeeze(0), h2.squeeze(0)

        # concatenate the hidden output
        h = torch.cat((h1, h2), dim=1).to(device)

        # Forward pass through the ANN (which will be 256 inputs)
        y_pred = modelAnn(h).squeeze().to(device)
        # Compute the loss
        loss = criterion(y_pred, label.float().squeeze().to(device))
        val_total_loss += loss.item()
        #ipdb.set_trace()
        val_total_error += get_smape(y_pred, label.float().to(device))
      
      validation_losses[epoch] = val_total_loss/num_val_batches
      validation_SMAPE[epoch] = val_total_error/num_val_batches
      
      #print(f"Epoch {epoch} | Current Training Loss: {training_losses[epoch]} | Error: {training_SMAPE[epoch] * 100.0}%")
      #print(f"Epoch {epoch} | Current Validation Loss: {validation_losses[epoch]} | Error: {validation_SMAPE[epoch] * 100.0}%")
      file_data.write(f"Epoch {epoch} | Current Training Loss: {training_losses[epoch]} | Error: {training_SMAPE[epoch] * 100.0}%\n")
      file_data.write(f"Epoch {epoch} | Current Validation Loss: {validation_losses[epoch]} | Error: {validation_SMAPE[epoch] * 100.0}%\n")
      if epoch in [10, 50, 100]:
        modelGru1_path = f"{path}/3bp_{date_time}_model_Gru1_hiddensz{modelGru1.hidden_size}_batchsz{batch_size}_lr{learning_rate}_epoch{epoch}_dropout{modelAnn.p}"
        torch.save(modelGru1.state_dict(), modelGru1_path)
        modelGru2_path = f"{path}/3bp_{date_time}_model_Gru2_hiddensz{modelGru2.hidden_size}_batchsz{batch_size}_lr{learning_rate}_epoch{epoch}_dropout{modelAnn.p}"
        torch.save(modelGru2.state_dict(), modelGru2_path)       
        modelAnn_path = f"{path}/3bp_{date_time}_model_Ann_hiddensz{modelGru2.hidden_size}_batchsz{batch_size}_lr{learning_rate}_epoch{epoch}_dropout{modelAnn.p}" 
        torch.save(modelAnn.state_dict(), modelAnn_path)
        
        plot_losses(iterations, training_losses, validation_losses, f"{path}/3bp_{date_time}_model_Gru1_hiddensz{modelGru1.hidden_size}_batchsz{batch_size}_lr{learning_rate}_epoch{epoch}_dropout{modelAnn.p}_loss.png")
        plot_SMAPE(iterations, training_SMAPE, validation_SMAPE, f"{path}/3bp_{date_time}_model_Gru1_hiddensz{modelGru1.hidden_size}_batchsz{batch_size}_lr{learning_rate}_epoch{epoch}_dropout{modelAnn.p}_SMAPE.png")

   
    file_data.close()
    # Save the current model (checkpoint) to a file
    
    modelGru1_path = f"{path}/3bp_{date_time}_model_Gru1_hiddensz{modelGru1.hidden_size}_batchsz{batch_size}_lr{learning_rate}_epoch{epoch}_dropout{modelAnn.p}"
    torch.save(modelGru1.state_dict(), modelGru1_path)
    modelGru2_path = f"{path}/3bp_{date_time}_model_Gru2_hiddensz{modelGru2.hidden_size}_batchsz{batch_size}_lr{learning_rate}_epoch{epoch}_dropout{modelAnn.p}"
    torch.save(modelGru2.state_dict(), modelGru2_path)       
    modelAnn_path = f"{path}/3bp_{date_time}_model_Ann_hiddensz{modelGru2.hidden_size}_batchsz{batch_size}_lr{learning_rate}_epoch{epoch}_dropout{modelAnn.p}" 
    torch.save(modelAnn.state_dict(), modelAnn_path)
    
    plot_losses(iterations, training_losses, validation_losses, f"{path}/3bp_{date_time}_model_Gru1_hiddensz{modelGru1.hidden_size}_batchsz{batch_size}_lr{learning_rate}_epoch{epoch}_dropout{modelAnn.p}_loss.png")
    plot_SMAPE(iterations, training_SMAPE, validation_SMAPE, f"{path}/3bp_{date_time}_model_Gru1_hiddensz{modelGru1.hidden_size}_batchsz{batch_size}_lr{learning_rate}_epoch{epoch}_dropout{modelAnn.p}_SMAPE.png")

class GRU(nn.Module):
    def __init__(self, input_size, hidden_size):
        super(GRU, self).__init__()
        self.hidden_size = hidden_size
        self.gru = nn.GRU(input_size, hidden_size, num_layers=1, batch_first=True)
        
    
    def forward(self, x):
        # x shape: (batch_size, sequence_length, input_size)
        h0 = torch.zeros(1, x.size(0), self.hidden_size)  # initial hidden state
        out, hn = self.gru(x)  # out shape: (batch_size, sequence_length, hidden_size), hn shape: (1, batch_size, hidden_size)
        return out, hn
        #return out[:, -1, :]  # return the last hidden state, shape: (batch_size, hidden_size)

class ANN(nn.Module):
    def __init__(self, input_size):
        super(ANN, self).__init__()
        self.fc1 = nn.Linear(input_size, 20)  # 1st hidden layer with 64 nodes
        self.fc2 = nn.Linear(20, 10)  # 1st hidden layer with 64 nodes
        self.output_layer = nn.Linear(10, 1)  # Output layer with 1 node
        self.p = 0
    def forward(self, x):
        x = nn.functional.relu(self.fc1(x))  # Apply ReLU activation to 1st hidden layer output
        x = nn.functional.relu(self.fc2(x))  # Apply ReLU activation to 1st hidden layer output
        output = self.output_layer(x)        # Output layer
        return output

class ANN_dropout(nn.Module):
  def __init__(self, input_size, p):
        super(ANN_dropout, self).__init__()
        self.fc1 = nn.Linear(input_size, 20)  # 1st hidden layer with 64 nodes
        self.fc2 = nn.Linear(20, 10)  # 1st hidden layer with 64 nodes
        self.p = p
        self.dropout = nn.Dropout(p=p)
        self.output_layer = nn.Linear(10, 1)  # Output layer with 1 node
        
  def forward(self, x):
    x = nn.functional.relu(self.fc1(x))  # Apply ReLU activation to 1st hidden layer output
    x = nn.functional.relu(self.fc2(x))  # Apply ReLU activation to 1st hidden layer output
    x = self.dropout(x)
    output = self.output_layer(x)  # Output layer
    return output

def normalized_data_pairings_log(list_pairs):
    '''INPUT: A list of the data in full dataset, of the form:
            [["AAA", "TTT", num_binding_events0],
                            ...
             ["AAC", "TTG", num_binding_events1]]
     OUTPUT: a normalized tuple array of the data (helps with comparision)'''
    norm_list_pairs = []
    # doing fancy log stuff
    total_binding_events = np.log(np.array(list_pairs)[:,2].astype(int).sum())
    for pair in list_pairs:
      # doing fancy log stuff
      affinity = float(np.log(pair[2] + 1)/total_binding_events) 
      assert type(affinity) == float
      norm_list_pairs.append([pair[0], pair[1], affinity])
    return norm_list_pairs

"""Inputting Data and Training"""

def to_device(data, device):
    """Move tensor(s) to chosen device"""
    if isinstance(data, (list,tuple)):
        return [to_device(x, device) for x in data]
    return data.to(device, non_blocking=True)

"""# Grid Search"""

learning_rates = [1.0e-5]
num_epoch = 250
# GRU params
input_size = 2 # size of the encoding
hidden_sizes = [15, 30, 50] # number of hidden states in the GRU
# ANN params
dropout = [0.3]
batch_sizes = [1, 5, 10] # batches in each

for batch_size in batch_sizes:
    i = 200
    # create imbeddings 
    embedded = convert_alpha_sequence(normalized_data_pairings_log(data_pairings))
    embedded = embedded.to('cuda')
    # create data loader, we will train on the same one for consistency
    train_loader, val_loader, test_loader = batching_fcn(dataset = embedded, split_proportion = [0.80, 0.18, 0.02], batch_size = batch_size, split_seed=30, batching_seed=42, balance = True)
    for dropout_p in dropout:
        for hidden_size in hidden_sizes:
            for learning_rate in learning_rates:
                print(f"Chose learning rate {learning_rate}, number of epochs {num_epoch}, hidden_size {hidden_size}, batch size {batch_size}, dropout {dropout_p}")
                # creating the structures required for model
                gru1 = GRU(input_size, hidden_size).to('cuda')
                gru2 = GRU(input_size, hidden_size).to('cuda')
                ann = ANN_dropout(hidden_size*2, dropout_p).to('cuda')
                ann_noD = ANN(hidden_size*2).to('cuda')
                # train
                train(gru1, gru2, ann, train_loader, val_loader, batch_size=batch_size, num_epochs=num_epoch, learning_rate=learning_rate, plot=True, path=f"./series{i:02d}")
                train(gru1, gru2, ann_noD, train_loader, val_loader, batch_size=batch_size, num_epochs=num_epoch, learning_rate=learning_rate, plot=True, path=f"./series{i:02d}_nodropout")
    i += 1