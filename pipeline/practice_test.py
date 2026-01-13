#!/usr/bin/env python
# coding: utf-8

import pandas as pd

from sqlalchemy import create_engine
pg_user = 'root'
pg_pass = 'root'
pg_host = 'localhost'
pg_port = 5432
pg_db = 'ny_taxi'



df=pd.read_csv(url)

url2= 'https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2025-01.parquet'

df2 = pd.read_parquet(url2)
df.head()


# len(df)

# In[12]:


dtype = {
    "VendorID": "Int64",
    "passenger_count": "Int64",
    "trip_distance": "float64",
    "RatecodeID": "Int64",
    "store_and_fwd_flag": "string",
    "PULocationID": "Int64",
    "DOLocationID": "Int64",
    "payment_type": "Int64",
    "fare_amount": "float64",
    "extra": "float64",
    "mta_tax": "float64",
    "tip_amount": "float64",
    "tolls_amount": "float64",
    "improvement_surcharge": "float64",
    "total_amount": "float64",
    "congestion_surcharge": "float64"
}

parse_dates = [
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime"
]

df = pd.read_csv(
    url,
    dtype=dtype,
    parse_dates=parse_dates
)

get_ipython().system('uv add sqlalchemy')


get_ipython().system('uv add psycopg2-binary')


prefix= 'https://github.com/DataTalksClub/nyc-tlc-data/releases/download/yellow'
url= f'{prefix}/yellow_tripdata_2021-01.csv.gz'
engine = create_engine(f'postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}')
print(pd.io.sql.get_schema(df, name='yellow_taxi_data', con=engine))


# In[22]:


df.head(n=0).to_sql(name='yellow_taxi_data', con=engine, if_exists='replace')


# In[23]:


df


# In[36]:


df.head(0)


# In[51]:


df_iter = pd.read_csv(
    url,
    dtype=dtype,
    parse_dates=parse_dates,
    iterator=True,
    chunksize=100000
)


# In[26]:


df=next(df_iter)


# In[27]:


df


# In[28]:


df


# In[40]:


df=next(df_iter)


# In[41]:


df


# In[32]:


df


# In[33]:


df


# In[49]:


get_ipython().system('uv add tqdm')


# In[45]:


from tqdm.auto import tqdm


# In[52]:


for df_chunk in tqdm(df_iter):
    df_chunk.to_sql(name='yellow_taxi_data', con=engine, if_exists='append')


# In[ ]:



