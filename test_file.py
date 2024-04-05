import pandas as pd

items = pd.read_csv('DonoList.csv')



a = [item for item in items['name']]
    
print(a)