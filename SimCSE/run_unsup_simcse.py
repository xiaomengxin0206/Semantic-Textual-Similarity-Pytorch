"""
@file   : run_unsup_simcse.py
@author : xiaolu
@email  : luxiaonlp@163.com
@time   : 2021-08-23
"""
import os
import random
import torch
import time
import numpy as np
import pandas as pd
from tqdm import tqdm
from torch import nn
from model import Model
from config import set_args
import torch.nn.functional as F
from einops import repeat, rearrange
from torch.utils.data import Dataset, DataLoader
from utils import l2_normalize, compute_corrcoef, compute_pearsonr
from data_helper import TrainDataSet, collate_train_func, load_test_data, load_data
from transformers import BertTokenizer, get_linear_schedule_with_warmup, AdamW


def pad_to_maxlen(input_ids, max_len, pad_value=0):
    if len(input_ids) >= max_len:
        input_ids = input_ids[:max_len]
    else:
        input_ids = input_ids + [pad_value] * (max_len - len(input_ids))
    return input_ids


def get_sent_id_tensor(s_list):
    input_ids, attention_mask, token_type_ids, labels = [], [], [], []
    max_len = max([len(_)+2 for _ in s_list])   # 这样写不太合适 后期想办法改一下
    for s in s_list:
        inputs = tokenizer.encode_plus(text=s, text_pair=None, add_special_tokens=True, return_token_type_ids=True)
        input_ids.append(pad_to_maxlen(inputs['input_ids'], max_len=max_len))
        attention_mask.append(pad_to_maxlen(inputs['attention_mask'], max_len=max_len))
        token_type_ids.append(pad_to_maxlen(inputs['token_type_ids'], max_len=max_len))
    all_input_ids = torch.tensor(input_ids, dtype=torch.long)
    all_input_mask = torch.tensor(attention_mask, dtype=torch.long)
    all_segment_ids = torch.tensor(token_type_ids, dtype=torch.long)
    return all_input_ids, all_input_mask, all_segment_ids


def evaluate():
    sent1, sent2, label = load_test_data(args.test_data)
    all_a_vecs = []
    all_b_vecs = []
    all_labels = []
    model.eval()
    for s1, s2, lab in tqdm(zip(sent1, sent2, label)):
        input_ids, input_mask, segment_ids = get_sent_id_tensor([s1, s2])
        lab = torch.tensor([lab], dtype=torch.float)
        if torch.cuda.is_available():
            input_ids, input_mask, segment_ids = input_ids.cuda(), input_mask.cuda(), segment_ids.cuda()
            lab = lab.cuda()

        with torch.no_grad():
            output = model(input_ids=input_ids, attention_mask=input_mask, encoder_type='cls')

        all_a_vecs.append(output[0].cpu().numpy())
        all_b_vecs.append(output[1].cpu().numpy())
        all_labels.extend(lab.cpu().numpy())

    all_a_vecs = np.array(all_a_vecs)
    all_b_vecs = np.array(all_b_vecs)
    all_labels = np.array(all_labels)

    a_vecs = l2_normalize(all_a_vecs)
    b_vecs = l2_normalize(all_b_vecs)
    sims = (a_vecs * b_vecs).sum(axis=1)
    corrcoef = compute_corrcoef(all_labels, sims)
    pearsonr = compute_pearsonr(all_labels, sims)
    return corrcoef, pearsonr


def compute_loss(y_pred, tao=0.05, device="cuda"):
    idxs = torch.arange(0, y_pred.shape[0], device=device)
    y_true = idxs + 1 - idxs % 2 * 2
    similarities = F.cosine_similarity(y_pred.unsqueeze(1), y_pred.unsqueeze(0), dim=2)
    similarities = similarities - torch.eye(y_pred.shape[0], device=device) * 1e12
    similarities = similarities / tao
    loss = F.cross_entropy(similarities, y_true)
    return torch.mean(loss)


if __name__ == '__main__':
    args = set_args()
    os.makedirs(args.output_dir, exist_ok=True)

    train_texts = load_data(args.train_data)

    # 2. 构建一个数据加载器
    tokenizer = BertTokenizer.from_pretrained('./roberta_pretrain/vocab.txt')
    train_data = TrainDataSet(train_texts, tokenizer)
    train_data_loader = DataLoader(train_data, batch_size=args.train_batch_size, collate_fn=collate_train_func)
    total_steps = int(len(train_data_loader) * args.num_train_epochs / args.gradient_accumulation_steps)

    print("总训练步数为:{}".format(total_steps))
    model = Model()
    if torch.cuda.is_available():
        model.cuda()

    # 获取模型所有参数
    param_optimizer = list(model.named_parameters())
    no_decay = ['bias', 'LayerNorm.bias', 'LayerNorm.weight']
    optimizer_grouped_parameters = [
        {'params': [p for n, p in param_optimizer if not any(
            nd in n for nd in no_decay)], 'weight_decay': 0.01},
        {'params': [p for n, p in param_optimizer if any(
            nd in n for nd in no_decay)], 'weight_decay': 0.0}
    ]

    # 设置优化器
    optimizer = AdamW(optimizer_grouped_parameters, lr=args.learning_rate, eps=args.adam_epsilon)
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=int(args.warmup_proportion * total_steps),
                                                num_training_steps=total_steps)


    for epoch in range(args.num_train_epochs):
        model.train()
        temp_loss = 0
        count = 0
        for step, batch in enumerate(train_data_loader):
            count += 1
            start_time = time.time()
            input_ids = batch["input_ids"]    # torch.Size([6, 22])
            input_ids = repeat(input_ids, 'b l -> b new_axis l', new_axis=2)
            input_ids = rearrange(input_ids, 'b x l -> (b x) l')

            attention_mask_ids = batch["attention_mask_ids"]
            attention_mask_ids = repeat(attention_mask_ids, 'b l -> b new_axis l', new_axis=2)
            attention_mask_ids = rearrange(attention_mask_ids, 'b x l -> (b x) l')

            # print(input_ids.size())    # torch.Size([12, 22])   # 2 * batch_size, max_len
            # print(attention_mask_ids.size())    # torch.Size([12, 22])   # 2 * batch_size, max_len

            if torch.cuda.is_available():
                input_ids = input_ids.cuda()
                attention_mask_ids = attention_mask_ids.cuda()

            outputs = model(input_ids, attention_mask_ids, encoder_type='cls')
            loss = compute_loss(outputs)
            temp_loss += loss.item()

            # 将损失值放到Iter中，方便观察
            ss = 'Epoch:{}, Step:{}, Loss:{:10f}, Time_cost:{:10f}'.format(epoch, step, loss, time.time() - start_time)
            print(ss)

            if args.gradient_accumulation_steps > 1:
                loss = loss / args.gradient_accumulation_steps

            # 损失进行回传
            loss.backward()
            # torch.nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)

            # 当训练步数整除累积步数时，进行参数优化
            if (step + 1) % args.gradient_accumulation_steps == 0:
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()

        train_loss = temp_loss / count

        corr, pears = evaluate()
        s = 'Epoch:{} | cur_epoch_average_loss:{:10f} |spearmanr: {:10f} | pearsonr: {:10f}'.format(epoch, train_loss, corr, pears)
        logs_path = os.path.join(args.output_dir, 'logs.txt')
        with open(logs_path, 'a+') as f:
            s += '\n'
            f.write(s)

        # 每个epoch进行完，则保存模型
        output_dir = os.path.join(args.output_dir, "Epoch-{}.bin".format(epoch))
        model_to_save = model.module if hasattr(model, "module") else model
        torch.save(model_to_save.state_dict(), output_dir)
        # 清空cuda缓存
        torch.cuda.empty_cache()
