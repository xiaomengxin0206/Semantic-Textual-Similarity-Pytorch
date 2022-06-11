# 中文文本语义匹配模型集锦
## 数据说明
|  | 训练集(数量) | 验证集(数量) | 测试集(数量) | 
| :-: | :-: | :-: | :-: | 
| ATEC | 62477 | 20000 | 20000 | 
| BQ |  100000 | 10000 | 10000 |   
| LCQMC | 238766 | 8802 | 12500 | 
| PAWSX |  49401 | 2000 | 2000 | 
| STS-B |  5231 | 1458 | 1361 |

## 评价指标的说明
- **皮尔逊系数(pearsonr)**: 是衡量两个连续型变量的线性相关关系。 
- **斯皮尔曼相关系数(spearmanr)**: 是衡量两变量之间的单调关系，两个变量同时变化，但是并非同样速率变化，即并非一定是线性关系。

## 实验结果: 
目前没有gpu，实验后续补充吧。 代码在本地已调通。gpu训练应该也适配，可直接训练。

### 斯皮尔曼系数(spearmanr)对比:

|  | ATEC | BQ | LCQMC | PAWSX | STS-B |  Avg |
| :-: | :-: | :-: | :-: | :-: | :-: | :-: | 
| SimCSE (unsup) | 30.8634 | ** | ** | ** | ** | ** |  
| PromptBERT (unsup) |  27.9526 | ** | ** | ** | ** | ** | 
| SimCSE (sup) |  ** | ** | ** | ** | ** | ** |  
| CoSENT (sup) | 50.6160 | 72.8400 | ** | ** | ** | ** |  
| SentenceBert (sup)| ** | ** | ** | ** | ** | ** | 
| GS-infoNCE |  ** | ** | ** | ** | ** | ** |   
| ESimCSE |  ** | ** | ** | ** | ** | ** |  

注: PromptBERT效果比论文差一点。大家可以看看代码，帮忙review一下。


### 皮尔逊相关系数(pearsonr)对比:

|  | ATEC | BQ | LCQMC | PAWSX | STS-B |  Avg |
| :-: | :-: | :-: | :-: | :-: | :-: | :-: | 
| SimCSE (unsup) |  33.1678 | ** | ** | ** | ** | ** | 
| PromptBERT (unsup) |  29.7527 | ** | ** | ** | ** | ** | 
| SimCSE (sup) |  ** | ** | ** | ** | ** | ** |   
| CoSENT (sup)| 49.8967 | 73.1022 | ** | ** | ** | ** |  
| SentenceBert (sup) |  ** | ** | ** | ** | ** | ** |  
| GS-infoNCE | ** | ** | ** | ** | ** | ** |   
| ESimCSE | ** | ** | ** | ** | ** | ** |   
 

